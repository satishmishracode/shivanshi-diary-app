import streamlit as st
import sqlite3
from datetime import date
from PIL import Image
import io
from fpdf import FPDF
import base64
import os
import random
import pickle
import openai
import requests

# --- OPENAI API KEY SETUP ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)
if not OPENAI_API_KEY:
    st.error("OpenAI API key not set! Please set OPENAI_API_KEY in Streamlit Secrets.")
openai.api_key = OPENAI_API_KEY

# --- Generate 1 sticker sheet image with 10 sticker ideas ---
def openai_generate_sticker_sheet(prompt_ideas):
    sticker_prompt = (
        f"A 1024x1024 white background sticker sheet with 10 cute cartoon stickers: "
        f"{prompt_ideas}. Each sticker should be separated with lots of whitespace, "
        f"arranged in a 2x5 grid for easy cropping, no text, no shadows, no overlap."
    )
    response = openai.images.generate(
        model="dall-e-3",
        prompt=sticker_prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    img_url = response.data[0].url
    return img_url

# --- Split the 1024x1024 image into 10 stickers (2 rows x 5 columns) ---
def split_sticker_sheet(img_url):
    response = requests.get(img_url)
    img = Image.open(io.BytesIO(response.content)).convert("RGBA")
    w, h = img.size
    grid_rows = 2
    grid_cols = 5
    stickers = []
    sw = w // grid_cols
    sh = h // grid_rows
    for row in range(grid_rows):
        for col in range(grid_cols):
            left = col * sw
            upper = row * sh
            right = left + sw
            lower = upper + sh
            crop = img.crop((left, upper, right, lower))
            stickers.append(crop)
    return stickers

# --- PINK THEME ---
st.markdown("""
    <style>
        body, .stApp { background-color: #ffe6f2; }
        .stTextInput>div>div>input, .stTextArea>div>textarea {
            background: #fff0f6;
        }
        .stButton>button {
            background-color: #ffb3d1;
            color: white;
            font-weight: bold;
            border-radius: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #ffe6f2;
        }
        .stTitle { color: #ff3385 !important; }
    </style>
""", unsafe_allow_html=True)

# --- INSPIRATIONAL QUOTES ---
quotes = [
    "Dream big, little one! 💕",
    "Every day is a new page in your story.",
    "You are magic, Shivanshi!",
    "Shine bright like the stars! 🌟",
    "Keep your heart open and your dreams wild."
]

# --- SQLite setup ---
DB = "diary.db"
def get_connection():
    return sqlite3.connect(DB, check_same_thread=False)
conn = get_connection()
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS diary_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date TEXT,
        entry_text TEXT
    )
''')
try:
    c.execute('ALTER TABLE diary_entries ADD COLUMN mood_emoji TEXT')
except sqlite3.OperationalError:
    pass
try:
    c.execute('ALTER TABLE diary_entries ADD COLUMN stickers BLOB')
except sqlite3.OperationalError:
    pass
c.execute('''
    CREATE TABLE IF NOT EXISTS diary_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER,
        image BLOB,
        FOREIGN KEY (entry_id) REFERENCES diary_entries (id)
    )
''')
conn.commit()

# --- Helper: Save entry ---
def save_entry(entry_date, entry_text, mood_emoji, images, stickers):
    c.execute('INSERT INTO diary_entries (entry_date, entry_text, mood_emoji, stickers) VALUES (?, ?, ?, ?)', 
        (entry_date, entry_text, mood_emoji, stickers))
    entry_id = c.lastrowid
    for img in images:
        img_bytes = img.read()
        c.execute('INSERT INTO diary_images (entry_id, image) VALUES (?, ?)', (entry_id, img_bytes))
    conn.commit()

# --- Helper: Fetch entry by date ---
def fetch_entry(entry_date):
    c.execute('SELECT id, entry_text, mood_emoji, stickers FROM diary_entries WHERE entry_date=?', (entry_date,))
    row = c.fetchone()
    if not row:
        return None, None, [], []
    entry_id, entry_text, mood_emoji, stickers_blob = row
    c.execute('SELECT image FROM diary_images WHERE entry_id=?', (entry_id,))
    images = []
    for img_tuple in c.fetchall():
        try:
            img = Image.open(io.BytesIO(img_tuple[0]))
            images.append(img)
        except:
            continue
    selected_stickers = []
    if stickers_blob:
        try:
            selected_stickers = pickle.loads(stickers_blob)
        except:
            selected_stickers = []
    return entry_text, mood_emoji, images, selected_stickers

# --- Helper: Export to PDF ---
def export_pdf(entry_date, entry_text, mood_emoji, images, stickers):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.set_text_color(255, 51, 133)
    pdf.cell(200, 10, f"Diary Entry: {entry_date}", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.set_text_color(0,0,0)
    pdf.cell(200, 10, f"Mood: {mood_emoji}", ln=True)
    pdf.ln(10)
    pdf.multi_cell(0, 10, entry_text)
    pdf.ln(5)
    # Stickers (show as images in PDF)
    for sidx, sticker in enumerate(stickers):
        temp_path = f"temp_sticker{sidx}.png"
        sticker.save(temp_path)
        pdf.image(temp_path, w=30)
        os.remove(temp_path)
    if stickers:
        pdf.ln(10)
    for img in images:
        temp_path = "temp_img.jpg"
        img.save(temp_path)
        pdf.image(temp_path, w=100)
        os.remove(temp_path)
        pdf.ln(10)
    return pdf.output(dest='S').encode('latin1')

# --- Helper: Get All Entries ---
def get_all_entries():
    c.execute('SELECT id, entry_date, mood_emoji, entry_text, stickers FROM diary_entries ORDER BY entry_date DESC')
    return c.fetchall()

# --- Helper: Delete Entry ---
def delete_entry(entry_id):
    c.execute('DELETE FROM diary_entries WHERE id=?', (entry_id,))
    c.execute('DELETE FROM diary_images WHERE entry_id=?', (entry_id,))
    conn.commit()

# --- Helper: Edit Entry ---
def edit_entry(entry_id, new_text, new_mood, new_stickers_blob):
    c.execute('UPDATE diary_entries SET entry_text=?, mood_emoji=?, stickers=? WHERE id=?', (new_text, new_mood, new_stickers_blob, entry_id))
    conn.commit()

# --- UI ---
st.title("📔 Shivanshi's Pink Diary")
st.markdown(f"<h3 style='color:#ff3385'>Welcome, Shivanshi! 💖</h3>", unsafe_allow_html=True)
st.markdown(f"<i>{random.choice(quotes)}</i>")

tab1, tab2, tab3 = st.tabs(["Write Entry", "View Entry", "All Entries"])

with tab1:
    st.subheader("New Diary Entry")
    entry_date = st.date_input("Select Date", value=date.today())
    entry_text = st.text_area("What's on your mind?")
    mood_emoji = st.selectbox("How are you feeling today?", ["😊 Happy", "🥰 Loved", "😴 Sleepy", "🤩 Excited", "😢 Sad", "😎 Cool", "😇 Grateful"])
    images = st.file_uploader("Upload up to 3 images (optional)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
    if images and len(images) > 3:
        st.warning("You can upload up to 3 images only.")
        images = images[:3]
    
    st.markdown("---")
    st.subheader("Decorate your diary with stickers!")
    sticker_ideas = st.text_input(
        "Enter 10 sticker ideas (comma-separated, e.g., unicorn, rainbow, pizza, cat, heart, cupcake, sun, cloud, flower, star):"
    )
    sticker_images = []
    selected_stickers = []
    if 'sticker_cache' not in st.session_state:
        st.session_state.sticker_cache = {}
    if st.button("Generate Sticker Sheet"):
        if not sticker_ideas.strip():
            st.warning("Please enter your 10 sticker ideas!")
        else:
            try:
                img_url = openai_generate_sticker_sheet(sticker_ideas)
                stickers = split_sticker_sheet(img_url)
                st.session_state.sticker_cache[entry_date] = stickers
            except Exception as e:
                st.warning(f"Sticker generation failed: {e}")
    # Show sticker grid if available
    if entry_date in st.session_state.sticker_cache:
        stickers = st.session_state.sticker_cache[entry_date]
        st.write("Choose up to 5 stickers:")
        cols = st.columns(5)
        picked = []
        for idx, img in enumerate(stickers):
            with cols[idx % 5]:
                st.image(img, width=80)
                chk = st.checkbox(f"Pick", key=f"sticker_{idx}")
                if chk:
                    picked.append(img)
        if len(picked) > 5:
            st.warning("You can pick up to 5 stickers only. Only first 5 will be saved.")
            picked = picked[:5]
        selected_stickers = picked

    stickers_blob = pickle.dumps(selected_stickers) if selected_stickers else None

    if st.button("Save Entry", key="save_btn"):
        if not entry_text.strip():
            st.error("Entry text cannot be empty.")
        else:
            save_entry(str(entry_date), entry_text, mood_emoji, images, stickers_blob)
            st.success("Entry saved successfully!")

with tab2:
    st.subheader("View Diary Entry")
    view_date = st.date_input("Select Date to View", value=date.today(), key="view_date")
    if st.button("Fetch Entry"):
        entry_text, mood_emoji, images, stickers = fetch_entry(str(view_date))
        if entry_text:
            st.markdown(f"### Entry for {view_date} | Mood: {mood_emoji}")
            st.write(entry_text)
            if stickers:
                st.write("Stickers:")
                stx = st.columns(5)
                for sidx, sticker in enumerate(stickers):
                    with stx[sidx % 5]:
                        st.image(sticker, width=60)
            for idx, img in enumerate(images):
                st.image(img, width=300, caption=f"Image {idx+1}")
            if st.button("Download as PDF"):
                pdf_bytes = export_pdf(view_date, entry_text, mood_emoji, images, stickers)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="diary_entry_{view_date}.pdf">Download PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No entry found for this date.")

with tab3:
    st.subheader("All Diary Entries")
    entries = get_all_entries()
    if entries:
        for entry in entries:
            entry_id, e_date, mood, text, stickers_blob = entry
            stickers = []
            if stickers_blob:
                try:
                    stickers = pickle.loads(stickers_blob)
                except:
                    stickers = []
            with st.expander(f"{e_date} | Mood: {mood}"):
                st.write(text)
                if stickers:
                    st.write("Stickers:")
                    stx = st.columns(5)
                    for sidx, sticker in enumerate(stickers):
                        with stx[sidx % 5]:
                            st.image(sticker, width=50)
                col1, col2, col3 = st.columns([1,1,2])
                with col1:
                    if st.button("Delete", key=f"del_{entry_id}"):
                        delete_entry(entry_id)
                        st.success("Entry deleted. Refresh to update.")
                with col2:
                    if st.button("Edit", key=f"edit_{entry_id}"):
                        new_text = st.text_area("Edit your entry:", value=text, key=f"ta_{entry_id}")
                        new_mood = st.selectbox("Edit mood:", ["😊 Happy", "🥰 Loved", "😴 Sleepy", "🤩 Excited", "😢 Sad", "😎 Cool", "😇 Grateful"], index=["😊 Happy", "🥰 Loved", "😴 Sleepy", "🤩 Excited", "😢 Sad", "😎 Cool", "😇 Grateful"].index(mood), key=f"sb_{entry_id}")
                        if st.button("Save Changes", key=f"save_{entry_id}"):
                            edit_entry(entry_id, new_text, new_mood, stickers_blob)
                            st.success("Entry updated! Refresh to update.")
    else:
        st.info("No entries yet.")