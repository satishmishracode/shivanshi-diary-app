import streamlit as st
import sqlite3
from datetime import date
from PIL import Image
import io
from fpdf import FPDF
import base64
import os

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
def save_entry(entry_date, entry_text, images):
    c.execute('INSERT INTO diary_entries (entry_date, entry_text) VALUES (?, ?)', (entry_date, entry_text))
    entry_id = c.lastrowid
    for img in images:
        img_bytes = img.read()
        c.execute('INSERT INTO diary_images (entry_id, image) VALUES (?, ?)', (entry_id, img_bytes))
    conn.commit()

# --- Helper: Fetch entry by date ---
def fetch_entry(entry_date):
    c.execute('SELECT id, entry_text FROM diary_entries WHERE entry_date=?', (entry_date,))
    row = c.fetchone()
    if not row:
        return None, []
    entry_id, entry_text = row
    c.execute('SELECT image FROM diary_images WHERE entry_id=?', (entry_id,))
    images = []
    for img_tuple in c.fetchall():
        try:
            img = Image.open(io.BytesIO(img_tuple[0]))
            images.append(img)
        except:
            continue
    return entry_text, images

# --- Helper: Export to PDF ---
def export_pdf(entry_date, entry_text, images):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Diary Entry: {entry_date}", ln=True, align='C')
    pdf.ln(10)
    pdf.multi_cell(0, 10, entry_text)
    pdf.ln(5)
    for img in images:
        # Save to a temporary file (FPDF needs a file path)
        temp_path = "temp_img.jpg"
        img.save(temp_path)
        pdf.image(temp_path, w=100)
        os.remove(temp_path)
        pdf.ln(10)
    return pdf.output(dest='S').encode('latin1')

# --- Streamlit UI ---
st.set_page_config(page_title="Shivanshi Diary App", layout="centered")
st.title("Shivanshi Diary App")

tab1, tab2 = st.tabs(["Write Entry", "View Entry"])

with tab1:
    st.subheader("New Diary Entry")
    entry_date = st.date_input("Select Date", value=date.today())
    entry_text = st.text_area("Write your diary entry here:")
    images = st.file_uploader("Upload up to 3 images (optional)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
    if images and len(images) > 3:
        st.warning("You can upload up to 3 images only.")
        images = images[:3]
    if st.button("Save Entry"):
        if not entry_text.strip():
            st.error("Entry text cannot be empty.")
        else:
            save_entry(str(entry_date), entry_text, images)
            st.success("Entry saved successfully!")

with tab2:
    st.subheader("View Diary Entry")
    view_date = st.date_input("Select Date to View", value=date.today(), key="view_date")
    if st.button("Fetch Entry"):
        entry_text, images = fetch_entry(str(view_date))
        if entry_text:
            st.markdown(f"### Entry for {view_date}")
            st.write(entry_text)
            for idx, img in enumerate(images):
                st.image(img, width=300, caption=f"Image {idx+1}")
            if st.button("Download as PDF"):
                pdf_bytes = export_pdf(view_date, entry_text, images)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="diary_entry_{view_date}.pdf">Download PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No entry found for this date.")
