import streamlit as st
import sqlite3
from datetime import date
from PIL import Image
import io
from fpdf import FPDF
import base64
import os
import random

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
# --- Ensure mood_emoji column exists ---
try:
    c.execute('ALTER TABLE diary_entries ADD COLUMN mood_emoji TEXT')
except sqlite3.OperationalError:
    pass  # Column exists, that's fine.

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
def save_entry(entry_date, entry_text, mood_emoji, images):
    c.execute('INSERT INTO diary_entries (entry_date, entry_text, mood_emoji) VALUES (?, ?, ?)', (entry_date, entry_text, mood_emoji))
    entry_id = c.lastrowid
    for img in images:
        img_bytes = img.read()
        c.execute('INSERT INTO diary_images (entry_id, image) VALUES (?, ?)', (entry_id, img_bytes))
    conn.commit()

# --- Helper: Fetch entry by date ---
def fetch_entry(entry_date):
    c.execute('SELECT id, entry_text, mood_emoji FROM diary_entries WHERE entry_date=?', (entry_date,))
    row = c.fetchone()
    if not row:
        return None, None, []
    entry_id, entry_text, mood_emoji = row
    c.execute('SELECT image FROM diary_images WHERE entry_id=?', (entry_id,))
    images = []
    for img_tuple in c.fetchall():
        try:
            img = Image.open(io.BytesIO(img_tuple[0]))
            images.append(img)
        except:
            continue
    return entry_text, mood_emoji, images

# --- Helper: Export to PDF ---
def export_pdf(entry_date, entry_text, mood_emoji, images):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.set_text_color(255, 51, 133) # Pink
    pdf.cell(200, 10, f"Diary Entry: {entry_date}", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.set_text_color(0,0,0)
    pdf.cell(200, 10, f"Mood: {mood_emoji}", ln=True)
    pdf.ln(10)
    pdf.multi_cell(0, 10, entry_text)
    pdf.ln(5)
    for img in images:
        temp_path = "temp_img.jpg"
        img.save(temp_path)
        pdf.image(temp_path, w=100)
        os.remove(temp_path)
        pdf.ln(10)
    return pdf.output(dest='S').encode('latin1')

# --- Helper: Get All Entries ---
def get_all_entries():
    c.execute('SELECT id, entry_date, mood_emoji, entry_text FROM diary_entries ORDER BY entry_date DESC')
    return c.fetchall()

# --- Helper: Delete Entry ---
def delete_entry(entry_id):
    c.execute('DELETE FROM diary_entries WHERE id=?', (entry_id,))
    c.execute('DELETE FROM diary_images WHERE entry_id=?', (entry_id,))
    conn.commit()

# --- Helper: Edit Entry ---
def edit_entry(entry_id, new_text, new_mood):
    c.execute('UPDATE diary_entries SET entry_text=?, mood_emoji=? WHERE id=?', (new_text, new_mood, entry_id))
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
    if st.button("Save Entry", key="save_btn"):
        if not entry_text.strip():
            st.error("Entry text cannot be empty.")
        else:
            save_entry(str(entry_date), entry_text, mood_emoji, images)
            st.success("Entry saved successfully!")

with tab2:
    st.subheader("View Diary Entry")
    view_date = st.date_input("Select Date to View", value=date.today(), key="view_date")
    if st.button("Fetch Entry"):
        entry_text, mood_emoji, images = fetch_entry(str(view_date))
        if entry_text:
            st.markdown(f"### Entry for {view_date} | Mood: {mood_emoji}")
            st.write(entry_text)
            for idx, img in enumerate(images):
                st.image(img, width=300, caption=f"Image {idx+1}")
            if st.button("Download as PDF"):
                pdf_bytes = export_pdf(view_date, entry_text, mood_emoji, images)
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
            entry_id, e_date, mood, text = entry
            with st.expander(f"{e_date} | Mood: {mood}"):
                st.write(text)
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
                            edit_entry(entry_id, new_text, new_mood)
                            st.success("Entry updated! Refresh to update.")
    else:
        st.info("No entries yet.")