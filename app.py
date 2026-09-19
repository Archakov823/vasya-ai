import io
import json
import sqlite3
import urllib.parse
import urllib.request
import datetime
import streamlit as st
import streamlit.components.v1 as components
import speech_recognition as sr
from groq import Groq

# Проверка и инициализация Groq API
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY or GROQ_API_KEY == "ВАШ_API_КЛЮЧ_ЕСЛИ_НУЖНО_ЛОКАЛЬНО":
    st.error("⚠️ Внимание: Не найден GROQ_API_KEY в Streamlit Secrets! Добавьте ваш API-ключ в настройках приложения на Streamlit Cloud (Settings -> Secrets).")

client = Groq(api_key=GROQ_API_KEY if GROQ_API_KEY else "dummy_key")

# Настройка базы данных SQLite
DB_NAME = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            image_url TEXT,
            video_url TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_history():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT role, content, image_url, video_url FROM history ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    messages = []
    for r in rows:
        msg = {"role": r[0], "content": r[1]}
        if r[2]:
            msg["image_url"] = r[2]
        if r[3]:
            msg["video_url"] = r[3]
        messages.append(msg)
    return messages

def save_message(role, content, image_url=None, video_url=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO history (role, content, image_url, video_url) VALUES (?, ?, ?, ?)",
        (role, content, image_url, video_url)
    )
    conn.commit()
    conn.close()

def clear_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    conn.close()

init_db()

st.set_page_config(
    page_title="Вася AI", 
    page_icon="✨", 
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stApp {
        background-color: #131314;
        color: #E3E3E3;
    }
    header, .stHeader {
        background-color: transparent !important;
    }
    h1 {
        color: #D3E3FD !important;
        font-weight: 500 !important;
        font-size: 1.8rem !important;
        text-align: center;
        margin-bottom: 8px !important;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #1E1F20 !important;
        border-right: 1px solid #282A2C !important;
    }

    .stChatMessage {
        background-color: #1E1F20 !important;
        border-radius: 20px !important;
        padding: 12px 18px !important;
        margin-bottom: 12px !important;
        border: 1px solid #282A2C !important;
    }
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: #2A2B2E !important;
    }

    .stChatInputContainer textarea {
        background-color: #1E1F20 !important;
        color: #E3E3E3 !important;
        border-radius: 28px !important;
        border: 1px solid #333537 !important;
    }

    .stButton > button, .stLinkButton > a {
        border-radius: 20px !important;
        background-color: #1E1F20 !important;
        color: #E3E3E3 !important;
        border: 1px solid #333537 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        padding: 6px 12px !important;
        transition: all 0.2s ease !important;
        text-decoration: none !important;
        display: inline-flex !important;
        justify-content: center !important;
        align-items: center !important;
    }

    .stButton > button:hover, .stLinkButton > a:hover {
        background-color: #2A2B2E !important;
        border-color: #444746 !important;
        color: #FFFFFF !important;
    }

    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ------------------ БОКОВАЯ ПАНЕЛЬ ------------------
st.sidebar.title("⚙️ Меню Васи")

with st.sidebar.expander("📖 О помощнике", expanded=True):
    st.markdown("""
    **Вася AI** — ваш универсальный интеллектуальный помощник. 
    Поможет в написании кода, решении задач, анализе текстов и любых вопросах.
    """)

with st.sidebar.expander("💾 Управление историей", expanded=False):
    messages_data = load_history()
    if messages_data:
        txt_output = ""
        for m in messages_data:
            role_name = "Вы" if m["role"] == "user" else "Вася AI"
            txt_output += f"[{role_name}]: {m['content']}\n\n"

        json_output = json.dumps(messages_data, ensure_ascii=False, indent=2)

        st.download_button(
            label="📄 Скачать историю (TXT)",
            data=txt_output,
            file_name=f"vasya_chat_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
        st.download_button(
            label="📦 Скачать историю (JSON)",
            data=json_output,
            file_name=f"vasya_chat_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    else:
        st.caption("История сообщений пока пуста.")

# ------------------ ГЛАВНЫЙ ЭКРАН ------------------
st.title("✨ Вася AI")

is_auto_voice = st.toggle("🔊 Авто-озвучка ответов", value=True, key="auto_voice_toggle")

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "Тебя зовут Вася. Ты — умный, универсальный и высокоинтеллектуальный AI-помощник, "
        "способный решать любые задачи: писать код, анализировать тексты, отвечать на сложные вопросы, "
        "помогать в учебе и повседневных делах.\n"
        "Общайся вежливо, грамотно, по делу. "
        "КАТЕГОРИЧЕСКОЕ ПРАВИЛО: На любые вопросы о том, кто тебя создал, разработал, придумал, кто твой автор или чей ты — ВСЕГДА отвечаешь ровно три слова: 'Олег Арчаков.' Никаких других вариантов."
    )
}

if "messages" not in st.session_state:
    st.session_state.messages = load_history()
if "show_file" not in st.session_state:
    st.session_state.show_file = False
if "show_cam" not in st.session_state:
    st.session_state.show_cam = False

# Функция озвучки с мгновенной отменом предыдущей речи
def speak_in_browser(text):
    clean_text = json.dumps(text)
    js_code = f"""
        <script>
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel(); // Сразу глушим любую речь
                
                function playVoice() {{
                    var msg = new SpeechSynthesisUtterance({clean_text});
                    msg.lang = 'ru-RU';
                    msg.rate = 1.0;
                    msg.pitch = 1.05;

                    var voices = window.speechSynthesis.getVoices();
                    var ruVoices = voices.filter(function(v) {{ return v.lang.includes('ru') || v.lang.includes('RU'); }});
                    
                    var bestVoice = ruVoices.find(function(v) {{
                        var name = v.name.toLowerCase();
                        return name.includes('natural') || name.includes('google') || name.includes('microsoft') || name.includes('elena') || name.includes('daria') || name.includes('pavel');
                    }}) || ruVoices[0];

                    if (bestVoice) {{ msg.voice = bestVoice; }}
                    window.speechSynthesis.speak(msg);
                }}

                if (window.speechSynthesis.getVoices().length !== 0) {{
                    playVoice();
                }} else {{
                    window.speechSynthesis.onvoiceschanged = playVoice;
                }}
            }}
        </script>
    """
    components.html(js_code, height=0)

def stop_speech():
    components.html("<script>if('speechSynthesis' in window) { window.speechSynthesis.cancel(); }</script>", height=0)

def is_creator_prompt(prompt_text):
    keywords = [
        "кто создал", "кто тебя создал", "кто разработал", "кто тебя разработал", 
        "чей ты", "кто твой хозяин", "кто хозяин", "кто твой создатель", 
        "кто разработчик", "кто тебя придумал", "кто твой автор", "кто автор", "создатель"
    ]
    t = prompt_text.lower()
    return any(kw in t for kw in keywords)

def is_greeting(prompt_text):
    greetings = ["привет", "здарова", "здорово", "хай", "hello", "hi", "добрый день", "добрый вечер", "доброе утро"]
    t = prompt_text.lower().strip()
    return any(t == g or t.startswith(g + " ") for g in greetings)

# Вывод истории сообщений
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        btn_label = "🔊 Прослушать меня" if message["role"] == "user" else "🔊 Прослушать Васю"
        if st.button(btn_label, key=f"replay_{idx}"):
            stop_speech()
            if message.get("content"):
                speak_in_browser(message["content"])

        if message.get("content"):
            st.markdown(message["content"])
        if "image_url" in message:
            st.image(message["image_url"], use_container_width=True)
        if "video_url" in message:
            st.image(message["video_url"], caption="Сгенерированное видео")

st.markdown("---")

col_clear, col_file, col_cam = st.columns([1, 1, 1])

with col_clear:
    if st.button("Очистить чат", use_container_width=True):
        stop_speech()
        clear_db()
        st.session_state.messages = []
        st.session_state.show_file = False
        st.session_state.show_cam = False
        st.rerun()

with col_file:
    if st.button("Файл", use_container_width=True):
        st.session_state.show_file = not st.session_state.show_file
        st.session_state.show_cam = False
        st.rerun()

with col_cam:
    if st.button("Камера", use_container_width=True):
        st.session_state.show_cam = not st.session_state.show_cam
        st.session_state.show_file = False
        st.rerun()

uploaded_file = None
camera_photo = None

if st.session_state.show_file:
    uploaded_file = st.file_uploader("Выберите файл/изображение", type=["jpg", "jpeg", "png", "txt", "pdf"], key="bottom_file")

if st.session_state.show_cam:
    camera_photo = st.camera_input("Сделать фото", key="bottom_cam")

image_to_process = camera_photo or uploaded_file

# Круглая кнопка записи по центру (без сохранения аудио на диск, чистая передача речи)
mic_html = """
<div style="display: flex; justify-content: center; align-items: center; margin: 15px 0;">
    <button id="micBtn" style="
        width: 70px; height: 70px; border-radius: 50%; 
        background-color: #0B57D0; border: 3px solid #1A73E8; 
        color: white; font-size: 28px; cursor: pointer; 
        box-shadow: 0 4px 12px rgba(11,87,208,0.4);
        display: flex; align-items: center; justify-content: center;
        transition: transform 0.2s, background-color 0.2s;
    " title="Нажмите и говорите">🎙️</button>
    <span id="micStatus" style="margin-left: 15px; font-family: sans-serif; font-size: 14px; color: #9aa0a6;">Нажмите микрофон для записи</span>
</div>

<script>
    const micBtn = document.getElementById('micBtn');
    const micStatus = document.getElementById('micStatus');
    
    let 인식중 = false;
    
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        micStatus.innerText = "Голосовой ввод не поддерживается вашим браузером";
        micBtn.style.opacity = "0.5";
        micBtn.disabled = true;
    } else {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.lang = 'ru-RU';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        micBtn.onclick = () => {
            // При нажатии сразу глушим голос Васи
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
            }
            
            try {
                recognition.start();
            } catch(e) {
                recognition.stop();
            }
        };

        recognition.onstart = () => {
            micBtn.style.backgroundColor = '#EA4335'; // Красный при записи
            micBtn.style.borderColor = '#F28B82';
            micStatus.innerText = "Слушаю... Говорите";
        };

        recognition.onresult = (event) => {
            const speechResult = event.results[0][0].transcript;
            micStatus.innerText = "Распознано: " + speechResult;
            
            // Передаем текст в Streamlit через URL params и перезагрузку
            const url = new URL(window.parent.location.href);
            url.searchParams.set('voice_text', speechResult);
            window.parent.location.href = url.toString();
        };

        recognition.onerror = () => {
            micBtn.style.backgroundColor = '#0B57D0';
            micBtn.style.borderColor = '#1A73E8';
            micStatus.innerText = "Ошибка распознавания. Попробуйте еще раз.";
        };

        recognition.onend = () => {
            micBtn.style.backgroundColor = '#0B57D0';
            micBtn.style.borderColor = '#1A73E8';
        };
    }
</script>
"""
components.html(mic_html, height=100)

# Проверяем, передан ли голос из JS-виджета через URL параметры
query_params = st.query_params
voice_prompt = query_params.get("voice_text", None)
if voice_prompt:
    # Очищаем параметр сразу, чтобы не зациклить
    st.query_params.clear()

text_prompt = st.chat_input("Спросите Васю о чем угодно...")
if text_prompt or voice_prompt:
    stop_speech() # Мгновенно затыкаем Васю при любом новом вводе

prompt = voice_prompt or text_prompt

if image_to_process and not prompt:
    prompt = "Опиши и проанализируй загруженное изображение."

if prompt:
    save_message("user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        if st.button("🔊 Прослушать меня", key=f"replay_new_{len(st.session_state.messages)-1}"):
            stop_speech()
            speak_in_browser(prompt)
        st.markdown(prompt)
        if image_to_process:
            st.image(image_to_process, caption="Загруженный файл", use_container_width=True)

    with st.chat_message("assistant"):
        stop_speech() # Глушим старый ответ перед генерацией нового

        if is_creator_prompt(prompt):
            reply_text = "Олег Арчаков."
            if st.button("🔊 Прослушать Васю", key=f"replay_resp_{len(st.session_state.messages)-1}"):
                stop_speech()
                speak_in_browser(reply_text)
            st.markdown(reply_text)
            if is_auto_voice:
                speak_in_browser(reply_text)
            save_message("assistant", reply_text)
            st.session_state.messages.append({"role": "assistant", "content": reply_text})

        elif is_greeting(prompt):
            reply_text = "Привет! Чем я могу помочь?"
            if st.button("🔊 Прослушать Васю", key=f"replay_resp_{len(st.session_state.messages)-1}"):
                stop_speech()
                speak_in_browser(reply_text)
            st.markdown(reply_text)
            if is_auto_voice:
                speak_in_browser(reply_text)
            save_message("assistant", reply_text)
            st.session_state.messages.append({"role": "assistant", "content": reply_text})

        else:
            full_response = ""
            success = False
            
            dynamic_models = []
            try:
                models_list = client.models.list()
                dynamic_models = [m.id for m in models_list.data if "guard" not in m.id and "whisper" not in m.id and "audio" not in m.id]
            except Exception:
                pass

            candidate_models = dynamic_models + [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "llama3-70b-8192",
                "mixtral-8x7b-32768"
            ]

            try:
                recent_messages = st.session_state.messages[-10:]
                messages_to_send = [SYSTEM_PROMPT] + [
                    {"role": m["role"], "content": m["content"]}
                    for m in recent_messages if "content" in m
                ]
                
                for model_name in candidate_models:
                    try:
                        completion = client.chat.completions.create(
                            model=model_name,
                            messages=messages_to_send,
                            temperature=0.5,
                            stream=True
                        )
                        for chunk in completion:
                            if chunk.choices[0].delta.content:
                                full_response += chunk.choices[0].delta.content
                        success = True
                        break
                    except Exception:
                        continue
                
                if not success:
                    full_response = "❌ Ошибка: Неверный API-ключ Groq или ключ не задан в Streamlit Secrets."
            except Exception as e:
                full_response = f"Ошибка обращения к Groq API: {e}"

            if st.button("🔊 Прослушать Васю", key=f"replay_resp_final_{len(st.session_state.messages)-1}"):
                stop_speech()
                speak_in_browser(full_response)
            st.markdown(full_response)
            
            if is_auto_voice and "Ошибка" not in full_response and "❌" not in full_response:
                speak_in_browser(full_response)
            
            save_message("assistant", full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})