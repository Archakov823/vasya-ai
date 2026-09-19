import io
import json
import sqlite3
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import datetime
import streamlit as st
import streamlit.components.v1 as components
import ollama
import speech_recognition as sr

try:
    import yfinance as yf
except ImportError:
    yf = None

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
    
    div[data-testid="stToggle"] {
        display: flex;
        justify-content: center;
        margin-bottom: 15px;
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

    div[data-testid="stAudioInput"] {
        width: 85px !important;
        height: 85px !important;
        border-radius: 50% !important;
        margin: 15px auto !important;
        padding: 0 !important;
        background-color: #0B57D0 !important;
        border: 3px solid #1A73E8 !important;
        box-shadow: 0 6px 16px rgba(11, 87, 208, 0.4) !important;
        position: relative !important;
        overflow: hidden !important;
        transition: all 0.3s ease !important;
    }

    div[data-testid="stAudioInput"]:hover {
        background-color: #1B6EF3 !important;
        border-color: #A8C7FA !important;
        transform: scale(1.08);
    }

    div[data-testid="stAudioInput"] * {
        background-color: transparent !important;
        border: none !important;
        color: transparent !important;
        font-size: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        box-shadow: none !important;
    }

    div[data-testid="stAudioInput"] svg {
        position: absolute !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        width: 36px !important;
        height: 36px !important;
        fill: #FFFFFF !important;
        color: #FFFFFF !important;
        z-index: 10 !important;
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

# ------------------ БОКОВАЯ ПАНЕЛЬ (SIDEBAR) ------------------
st.sidebar.title("⚙️ Инструменты Васи")

selected_mode = st.sidebar.radio(
    "Режим работы:",
    ["⚡ Скальпинг / Быстрый сигнал", "🧠 Обучение и аналитика"],
    index=0
)

# 1. ПАПКА: ИНСТРУКЦИЯ ПО ЭКСПЛУАТАЦИИ
with st.sidebar.expander("📖 Инструкция по эксплуатации", expanded=False):
    st.markdown("""
    ### 🤖 Руководство пользователя "Вася AI"
    
    **1. Переключение режимов торговли:**
    - **⚡ Скальпинг:** Краткие ответы, сразу сигналы (*Call/Put*) и ключевые уровни.
    - **🧠 Обучение и аналитика:** Развёрнутый анализ с детальным объяснением индикаторов.

    **2. Разбор индикаторов:**
    - Выберите любой индикатор из списка или укажите свой в поле *"Свой индикатор..."*.
    - Нажмите **💡 Запросить разбор**, чтобы получить параметры и точки входа.

    **3. Управление риском и Мартингейл:**
    - Задайте депозит, % риска и число перекрытий.
    - Калькулятор автоматически покажет размер каждого шага и предупредит при опасном риске.

    **4. Анализ графиков (1 и 2 таймфрейма):**
    - Нажмите **Файл** или **Камера** внизу экрана для загрузки скриншота графика.
    - Для двойного анализа откройте папку **📊 Мультитаймфрейм** и загрузите H1 и M1/M5.

    **5. Голосовые функции и синтез:**
    - Используйте синюю кнопку микрофона для голосовых вопросов.
    - Включите переключатель **🔊 Авто-озвучка ответов** для автоматической речи Васи.

    **6. Генерация визуала:**
    - Отправьте фразы со словами *"нарисуй..."* или *"создай видео..."* для получения картинок/анимаций.
    """)

# 2. Выбор любого индикатора и быстрые вопросы
quick_prompt_clicked = None
with st.sidebar.expander("📉 Выбор индикаторов и вопросов", expanded=False):
    indicator_list = [
        "RSI + MACD",
        "RSI (Relative Strength Index)",
        "MACD",
        "Bollinger Bands (Полосы Боллинджера)",
        "Stochastic Oscillator (Стохастик)",
        "EMA / SMA (Скользящие средние)",
        "Fibonacci Retracement (Фибоначчи)",
        "ATR (Average True Range)",
        "Parabolic SAR",
        "Ichimoku Cloud (Облако Ишимоку)",
        "Supertrend",
        "Volume (Объёмы)",
        "CCI (Commodity Channel Index)",
        "Awesome Oscillator",
        "Свой индикатор..."
    ]
    selected_indicator = st.selectbox("Выберите индикатор:", indicator_list)
    
    if selected_indicator == "Свой индикатор...":
        custom_ind = st.text_input("Введите название индикатора:", "Pivot Points")
        target_ind = custom_ind
    else:
        target_ind = selected_indicator
        
    if st.button("💡 Запросить разбор индикатора", use_container_width=True):
        quick_prompt_clicked = (
            f"Расскажи подробно, как использовать индикатор '{target_ind}': "
            f"какие параметры лучше выбрать для скальпинга и бинарных опционов, "
            f"как правильно находить точки входа (Call/Put) и избегать ложных сигналов."
        )

    st.markdown("---")
    if st.button("📊 Оцени тренд на графике", use_container_width=True):
        quick_prompt_clicked = "Оцени тренд на графике и определи ключевые уровни"
    if st.button("🛡️ Правила депозита", use_container_width=True):
        quick_prompt_clicked = "Расскажи основные правила управления депозитом и риск-менеджмента"

# 3. Калькулятор риск-менеджмента и Мартингейла
with st.sidebar.expander("🧮 Калькулятор риска и Мартингейла", expanded=False):
    deposit = st.number_input("Ваш депозит ($)", min_value=10.0, value=1000.0, step=50.0)
    risk_pct = st.number_input("Риск на 1-ю сделку (%)", min_value=0.5, max_value=20.0, value=2.0, step=0.5)
    martingale_mult = st.number_input("Коэффициент Мартингейла", min_value=1.0, max_value=3.0, value=2.0, step=0.1)
    max_steps = st.slider("Число перекрытий (шагов)", min_value=1, max_value=6, value=3)

    initial_trade = deposit * (risk_pct / 100.0)
    st.write(f"**1-я сделка:** ${initial_trade:.2f}")

    st.caption("Расчёт шагов перекрытия:")
    current_step_amount = initial_trade
    total_risk = 0.0

    for step in range(1, max_steps + 1):
        total_risk += current_step_amount
        st.text(f"Шаг {step}: ${current_step_amount:.2f} (Сумма: ${total_risk:.2f})")
        current_step_amount *= martingale_mult

    risk_of_depo = (total_risk / deposit) * 100.0
    if risk_of_depo > 50:
        st.error(f"⚠️ Общий риск: {risk_of_depo:.1f}% от депозита!")
    else:
        st.success(f"✅ Общий риск: {risk_of_depo:.1f}% от депозита")

# 4. Сравнение двух графиков (Мультитаймфрейм)
multi_prompt_clicked = None
multi_images = []
with st.sidebar.expander("📊 Мультитаймфрейм (2 графика)", expanded=False):
    st.caption("Загрузите 2 скриншота для анализа")
    tf_h1 = st.file_uploader("Старший ТФ (H1/H4)", type=["png", "jpg", "jpeg"], key="tf_h1")
    tf_m1 = st.file_uploader("Младший ТФ (M1/M5)", type=["png", "jpg", "jpeg"], key="tf_m1")

    if tf_h1 and tf_m1:
        if st.button("🔍 Анализ 2-х графиков", use_container_width=True):
            multi_prompt_clicked = (
                "Проанализируй эти два графика: первый — старший таймфрейм (H1/H4), "
                "второй — младший таймфрейм (M1/M5). "
                "Сверь тренд на старшем ТФ и найди точную точку входа на младшем ТФ. Дай итоговую рекомендацию (Call/Put)."
            )
            multi_images = [tf_h1.getvalue(), tf_m1.getvalue()]

# 5. Экономический календарь и новости
with st.sidebar.expander("📅 Новости и Экономический календарь", expanded=False):
    st.caption("Ключевые события и High Impact новости")
    news_loaded = False

    if yf is not None:
        try:
            ticker = yf.Ticker("EURUSD=X")
            news_items = ticker.news
            if news_items:
                for item in news_items[:3]:
                    title = item.get("title", "Новость рынков")
                    publisher = item.get("publisher", "Yahoo Finance")
                    st.markdown(f"🐂🐂🐂 **[High Impact]** {title} _({publisher})_")
                news_loaded = True
        except Exception:
            pass

    if not news_loaded:
        try:
            rss_url = "https://news.google.com/rss/search?q=forex+trading+economy&hl=ru&gl=RU&ceid=RU:ru"
            req = urllib.request.Request(
                rss_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                root = ET.fromstring(response.read())
                items = root.findall('.//item')[:3]
                if items:
                    for item in items:
                        title_elem = item.find('title')
                        title = title_elem.text if title_elem is not None else "Новость финансового рынка"
                        st.markdown(f"🐂🐂 **[Маркет-новость]** {title}")
                    news_loaded = True
        except Exception:
            pass

    if not news_loaded:
        st.info("Мониторинг рынков активен. Перед выходом важных новостей соблюдайте риск-менеджмент.")

# 6. Экспорт истории
with st.sidebar.expander("💾 Скачать историю сессий", expanded=False):
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

# 7. ПАПКА: СВЯЗЬ
with st.sidebar.expander("📲 Связь", expanded=False):
    st.markdown("### 💬 Официальный Telegram")
    st.markdown("Наш канал и поддержка:")
    st.link_button("✈️ Перейти в @T_CLUB_OFFICIAL", "https://t.me/T_CLUB_OFFICIAL", use_container_width=True)

# ------------------ ГЛАВНЫЙ ЭКРАН ------------------
st.title("✨ Вася AI")

is_auto_voice = st.toggle("🔊 Авто-озвучка ответов", value=True, key="auto_voice_toggle")

TEXT_MODEL = "llama3.2:1b"
VISION_MODEL = "llava"

OLLAMA_OPTIONS = {
    "num_ctx": 4096,
    "temperature": 0.3,
}

if "Скальпинг" in selected_mode:
    mode_instruction = "Режим: Скальпинг. Отвечай предельно кратко, чётко, давай сразу суть, уровни и сигнал (Call/Put), без долгих теорий."
else:
    mode_instruction = "Режим: Обучение и аналитика. Отвечай подробно, развёрнуто, объясняй причины движения цены, индикаторы и логику с анализами."

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "Тебя зовут Вася. "
        "Ты — эксперт, трейдер и аналитик финансовых рынков и бинарных опционов.\n"
        f"{mode_instruction}\n"
        "Ты подробно знаешь технический и свечной анализ, индикаторы (RSI, MACD, Bollinger Bands, Stochastic, EMA и др.), риск-менеджмент и стратегии.\n"
        "В обычных ответах и приветствиях НЕ обращайся к пользователю словом 'хозяин'. "
        "На приветствие отвечай просто: 'Привет! Я Вася.'. "
        "На любые вопросы про то, кто тебя создал, разработал, придумал, или чей ты, или кто твой хозяин — всегда строго и кратко отвечай: 'Олег Арчаков.'"
    )
}

if "messages" not in st.session_state:
    st.session_state.messages = load_history()
if "show_file" not in st.session_state:
    st.session_state.show_file = False
if "show_cam" not in st.session_state:
    st.session_state.show_cam = False

def speak_in_browser(text):
    clean_text = json.dumps(text)
    js_code = f"""
        <script>
            function playVoice() {{
                if (!('speechSynthesis' in window)) return;
                window.speechSynthesis.cancel();
                var msg = new SpeechSynthesisUtterance({clean_text});
                msg.lang = 'ru-RU';
                msg.rate = 0.95;
                msg.pitch = 0.98;

                var voices = window.speechSynthesis.getVoices();
                var ruVoices = voices.filter(function(v) {{ return v.lang.includes('ru'); }});
                
                var bestVoice = ruVoices.find(function(v) {{
                    var name = v.name.toLowerCase();
                    return name.includes('natural') || name.includes('google') || name.includes('premium') || name.includes('pavel') || name.includes('dmitry');
                }}) || ruVoices[0];

                if (bestVoice) {{
                    msg.voice = bestVoice;
                }}

                window.speechSynthesis.speak(msg);
            }}

            if (window.speechSynthesis.getVoices().length !== 0) {{
                playVoice();
            }} else {{
                window.speechSynthesis.onvoiceschanged = playVoice;
            }}
        </script>
    """
    components.html(js_code, height=0)

def is_image_prompt(prompt_text):
    keywords = ["нарисуй", "сгенерируй фото", "покажи фото", "создай картинку", "нарисуй картинку", "сгенерируй картинку"]
    return any(kw in prompt_text.lower() for kw in keywords)

def is_video_prompt(prompt_text):
    keywords = ["создай видео", "сгенерируй видео", "сделай видео", "анимаци"]
    return any(kw in prompt_text.lower() for kw in keywords)

def is_creator_prompt(prompt_text):
    keywords = [
        "кто создал", "кто тебя создал", "кто разработал", "кто тебя разработал", 
        "чей ты", "кто твой хозяин", "кто хозяин", "кто твой создатель", 
        "кто разработчик", "кто тебя придумал", "кто твой автор", "кто автор"
    ]
    return any(kw in prompt_text.lower() for kw in keywords)

for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message.get("content"):
            btn_label = "🔊 Прослушать меня" if message["role"] == "user" else "🔊 Прослушать Васю"
            if st.button(btn_label, key=f"replay_{idx}"):
                speak_in_browser(message["content"])

        st.markdown(message["content"])
        
        if "image_url" in message:
            st.image(message["image_url"], use_container_width=True)
        if "video_url" in message:
            st.image(message["video_url"], caption="Сгенерированное видео")

st.markdown("---")

col_clear, col_file, col_cam = st.columns([1, 1, 1])

with col_clear:
    if st.button("Очистить", use_container_width=True):
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
    uploaded_file = st.file_uploader("Выберите изображение из памяти", type=["jpg", "jpeg", "png"], key="bottom_file")

if st.session_state.show_cam:
    camera_photo = st.camera_input("Сделать фото с веб-камеры", key="bottom_cam")

image_to_process = camera_photo or uploaded_file

def transcribe_audio(audio_bytes):
    recognizer = sr.Recognizer()
    try:
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data, language="ru-RU")
    except Exception:
        return None

audio_value = st.audio_input("Голосовой ввод", key="gemini_mic", label_visibility="collapsed")

voice_prompt = None
if audio_value:
    with st.spinner("Распознаю голос..."):
        voice_prompt = transcribe_audio(audio_value.read())
        if not voice_prompt:
            st.warning("Не удалось распознать речь.")

text_prompt = st.chat_input("Спросите Васю...")
prompt = multi_prompt_clicked or quick_prompt_clicked or voice_prompt or text_prompt

if image_to_process and not prompt:
    prompt = "Проанализируй данный торговый график/картинку. Укажи тренд, уровни поддержки и сопротивления и сделку (Call/Put)."

if prompt:
    save_message("user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
        if image_to_process:
            st.image(image_to_process, caption="Загруженное изображение", use_container_width=True)

    with st.chat_message("assistant"):
        if is_creator_prompt(prompt):
            reply_text = "Олег Арчаков."
            st.markdown(reply_text)
            
            if is_auto_voice:
                speak_in_browser(reply_text)

            save_message("assistant", reply_text)
            st.session_state.messages.append({"role": "assistant", "content": reply_text})

        elif multi_images:
            with st.spinner("Вася сравнивает старший и младший таймфреймы..."):
                try:
                    response = ollama.chat(
                        model=VISION_MODEL,
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                                "images": multi_images
                            }
                        ],
                        options=OLLAMA_OPTIONS,
                        keep_alive="1h"
                    )
                    full_response = response["message"]["content"]
                    st.markdown(full_response)
                    
                    if is_auto_voice:
                        speak_in_browser(full_response)
                    
                    save_message("assistant", full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    st.error(f"Ошибка анализа мультитаймфрейма: {e}")

        elif image_to_process:
            with st.spinner("Вася анализирует график..."):
                try:
                    img_bytes = image_to_process.getvalue()
                    response = ollama.chat(
                        model=VISION_MODEL,
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                                "images": [img_bytes]
                            }
                        ],
                        options=OLLAMA_OPTIONS,
                        keep_alive="1h"
                    )
                    full_response = response["message"]["content"]
                    st.markdown(full_response)
                    
                    if is_auto_voice:
                        speak_in_browser(full_response)
                    
                    save_message("assistant", full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    st.error(f"Ошибка модели зрения: {e}")

        elif is_image_prompt(prompt):
            with st.spinner("Рисую картинку..."):
                encoded_prompt = urllib.parse.quote(prompt)
                image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&model=flux&seed=42"
                
                reply_text = "Вот картинка, которую вы просили!"
                st.markdown(reply_text)
                st.image(image_url, use_container_width=True)
                
                if is_auto_voice:
                    speak_in_browser(reply_text)

                save_message("assistant", reply_text, image_url=image_url)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply_text,
                    "image_url": image_url
                })

        elif is_video_prompt(prompt):
            with st.spinner("Создаю видео..."):
                encoded_prompt = urllib.parse.quote(prompt)
                video_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&nologo=true"
                
                reply_text = "Вот сгенерированный видеофрагмент!"
                st.markdown(reply_text)
                st.image(video_url, caption="Сгенерированная анимация")
                
                if is_auto_voice:
                    speak_in_browser(reply_text)

                save_message("assistant", reply_text, video_url=video_url)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply_text,
                    "video_url": video_url
                })

        else:
            response_placeholder = st.empty()
            full_response = ""
            
            try:
                recent_messages = st.session_state.messages[-6:]
                messages_to_send = [SYSTEM_PROMPT] + [
                    {"role": m["role"], "content": m["content"]}
                    for m in recent_messages if "content" in m
                ]
                
                stream = ollama.chat(
                    model=TEXT_MODEL,
                    messages=messages_to_send,
                    stream=True,
                    options=OLLAMA_OPTIONS,
                    keep_alive="1h"
                )
                
                for chunk in stream:
                    full_response += chunk["message"]["content"]
                    response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                
                if is_auto_voice:
                    speak_in_browser(full_response)
                
                save_message("assistant", full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Ошибка: {e}")