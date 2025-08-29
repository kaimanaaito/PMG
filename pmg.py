import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time, os, json, re, sqlite3
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import nltk
from functools import lru_cache

# === Configuration ===
BASE_MANUAL_URL = "https://www.churchofjesuschrist.org/study/manual/preach-my-gospel-a-guide-to-missionary-service?lang=eng"
ALLOWED_DOMAIN = "www.churchofjesuschrist.org"
HEADERS = {"User-Agent": "PMG-DeepStudy-App/1.0"}
RATE_LIMIT_SECONDS = 0.7
DATA_DIR = "data"
DB_JSON = os.path.join(DATA_DIR, "preach_my_gospel_db.json")
SQLITE_FILE = os.path.join(DATA_DIR, "progress.sqlite3")

# === NLTK Setup (for robustness, though not used) ===
def ensure_nltk_resources():
    """Ensure NLTK resources are downloaded."""
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        st.info("Downloading NLTK 'punkt_tab' resource...")
        nltk.download("punkt_tab", quiet=True)

# Initialize NLTK resources
try:
    ensure_nltk_resources()
except Exception as e:
    st.error(f"Failed to initialize NLTK resources: {e}. Functionality unaffected as NLTK is not used.")

# === Enhanced CSS with Updated Styles ===
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #FAFAFA;
        color: #1F2A44;
        max-width: 1400px;
        margin: 0 auto;
        padding: 2rem;
    }
    
    body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 18px;
        color: #1F2A44;
        background-color: #FAFAFA;
        line-height: 1.7;
    }
    
    /* Typography Hierarchy */
    h1 { 
        font-size: 2.5rem; 
        margin-bottom: 2rem; 
        font-weight: 700; 
        color: #1F2A44;
        letter-spacing: -0.025em;
    }
    h2 { 
        font-size: 2rem; 
        margin-bottom: 1.75rem; 
        font-weight: 600; 
        color: #1F2A44;
    }
    h3 { 
        font-size: 1.75rem; 
        margin-bottom: 1.5rem; 
        font-weight: 600; 
        color: #1F2A44;
    }
    h4 {
        font-size: 1.5rem;
        margin-bottom: 1.25rem;
        font-weight: 500;
        color: #1F2A44;
    }
    
    /* Main Text */
    p, li, div { 
        font-size: 1.125rem; 
        line-height: 1.8; 
        margin-bottom: 1.5rem; 
        color: #1F2A44;
        text-align: justify;
        hyphens: auto;
    }
    
    /* Sidebar Styles */
    .css-1d391kg {
        background-color: #D8DEE9;
        border-right: 2px solid #B7C0CC;
        padding: 2rem;
        color: #FFFFFF !important;
        z-index: 1000; /* Sidebar above main content */
    }
    
    .css-1d391kg h2, .css-1d391kg h3, .css-1d391kg div, .css-1d391kg p, .css-1d391kg span {
        color: #FFFFFF !important;
    }
    
    /* Enhanced Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 0.5rem;
        background: linear-gradient(135deg, #2C7A7B 0%, #234E52 100%);
        color: #FFFFFF !important;
        font-size: 1.125rem;
        padding: 0.75rem 1.5rem;
        margin-bottom: 1.25rem;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        border: none;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
        z-index: 1001; /* Buttons above sidebar */
    }
    
    .stButton>button span, .stButton>button div, .stButton>button p {
        color: #FFFFFF !important; /* Ensure button text is white */
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #234E52 0%, #1A3C3A 100%);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
        transform: translateY(-2px);
    }
    
    .stButton>button:focus {
        outline: none;
        box-shadow: 0 0 0 3px rgba(44, 122, 123, 0.3);
    }
    
    /* Status Messages (Success, Info, Warning, Error) */
    div[class*="stAlert"] > div, div[class*="stAlert"] p, div[class*="stAlert"] span {
        color: #FFFFFF !important;
        z-index: 1002; /* Status messages above buttons */
    }
    
    /* Enhanced Section Box */
    .section-box {
        border: 1px solid #CBD5E0;
        padding: 2rem;
        border-radius: 0.75rem;
        margin-bottom: 2rem;
        background-color: #FFFFFF;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        position: relative;
    }
    
    .section-box::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        width: 6px;
        background: linear-gradient(180deg, #2C7A7B 0%, #234E52 100%);
        border-radius: 0.75rem 0 0 0.75rem;
    }
    
    /* Enhanced Scripture References */
    .scripture {
        font-style: italic;
        color: #2C7A7B;
        background: #E6FFFA;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        display: inline-block;
        margin: 0.25rem;
        font-weight: 500;
        border-left: 4px solid #2C7A7B;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    /* Enhanced Motivation Text */
    .motivation {
        color: #FFFFFF;
        font-weight: 600;
        font-size: 1.125rem;
        margin-top: 1.5rem;
        padding: 1rem;
        background: #2C7A7B;
        border-radius: 0.5rem;
        border-left: 4px solid #234E52;
    }
    
    /* Enhanced Progress Bar */
    .progress-container {
        margin-bottom: 2rem;
    }
    
    .progress-bar {
        background-color: #CBD5E0;
        border-radius: 0.5rem;
        overflow: hidden;
        height: 2rem;
        margin-bottom: 1.5rem;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    .progress-fill {
        background: linear-gradient(90deg, #2F855A 0%, #276749 100%);
        height: 100%;
        transition: width 0.5s ease;
        position: relative;
    }
    
    .progress-fill::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, transparent 30%, rgba(255, 255, 255, 0.2) 50%, transparent 70%);
    }
    
    /* Enhanced Form Elements */
    .stTextArea textarea {
        font-size: 1.125rem;
        background-color: #FFFFFF;
        color: #1F2A44;
        border: 2px solid #CBD5E0;
        border-radius: 0.5rem;
        font-family: 'Inter', sans-serif;
        line-height: 1.6;
        padding: 1rem;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    
    .stTextArea textarea:focus {
        border-color: #2C7A7B;
        box-shadow: 0 0 0 3px rgba(44, 122, 123, 0.2);
        outline: none;
    }
    
    .stSelectbox select {
        font-size: 1.125rem;
        font-family: 'Inter', sans-serif;
        color: #FFFFFF !important;
        background-color: #2C7A7B;
        border: 2px solid #B7C0CC;
        border-radius: 0.5rem;
        padding: 0.75rem;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
        font-weight: 500;
    }
    
    .stSelectbox select:focus {
        border-color: #234E52;
        box-shadow: 0 0 0 3px rgba(44, 122, 123, 0.2);
        outline: none;
    }
    
    /* Chapter/Section Selection Dropdown Options */
    .stSelectbox div[role="option"], .stSelectbox option, .stSelectbox optgroup {
        color: #FFFFFF !important; /* White text for dropdown options */
        background-color: #234E52 !important; /* Darker background for contrast */
        padding: 0.75rem 1rem; /* Button-like padding */
        margin: 0.2rem 0; /* Space between options */
        border-radius: 0.5rem; /* Rounded corners */
        border: 1px solid #B7C0CC; /* Button-like border */
        cursor: pointer; /* Pointer cursor for interactivity */
        transition: background-color 0.2s ease, transform 0.2s ease;
    }
    
    .stSelectbox div[role="option"]:hover, .stSelectbox option:hover {
        background-color: #1A3C3A !important; /* Darker hover effect */
        transform: translateY(-1px); /* Slight lift on hover */
    }
    
    /* Enhanced Chapter/Section Selection */
    .chapter-selector {
        background: #CBD5E0;
        border: 1px solid #B7C0CC;
        border-radius: 0.75rem;
        padding: 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
        color: #FFFFFF !important; /* Match main body text */
    }
    
    .chapter-selector h3, .chapter-selector h4 {
        color: #1F2A44 !important; /* Match main body text */
        white-space: nowrap; /* Prevent line breaks */
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .section-selector {
        background: #E2E8F0;
        border: 1px solid #B7C0CC;
        border-radius: 0.75rem;
        padding: 1.5rem;
        margin-top: 1.25rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.03);
        color: #1F2A44 !important; /* Match main body text */
    }
    
    .section-selector h4, .section-selector h5 {
        color: #1F2A44 !important; /* Match main body text */
        white-space: nowrap; /* Prevent line breaks */
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* Status Indicators */
    .status-completed {
        color: #2F855A;
        font-weight: 600;
        background: #F0FFF4;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2F855A;
    }
    
    .status-in-progress {
        color: #D97706;
        font-weight: 600;
        background: #FFF7ED;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #D97706;
    }
    
    /* Enhanced Caption */
    .stCaption {
        font-size: 1rem;
        color: #718096;
        font-style: italic;
        text-align: center;
        margin-top: 3rem;
        padding: 1.5rem;
        border-top: 1px solid #CBD5E0;
    }
    
    /* Notes Section */
    .notes-section {
        background: #F7FAFC;
        border: 1px solid #CBD5E0;
        border-radius: 0.75rem;
        padding: 2rem;
        margin-top: 2rem;
    }
    
    /* Checkbox Enhancement */
    .stCheckbox {
        font-size: 1.125rem;
        margin-bottom: 1.5rem;
    }
    
    /* Reading Content */
    .reading-content {
        max-width: 900px;
        margin: 0 auto;
        padding: 0 1rem;
    }
    
    .reading-content p {
        font-size: 1.25rem;
        font-weight: 400; /* Lighter font for readability */
        line-height: 1.8;
        color: #1F2A44;
        margin-bottom: 1.5rem; /* Ensure consistent paragraph spacing */
        padding: 0.5rem 0; /* Add padding for visual separation */
    }
    
    /* Ensure paragraph containers maintain spacing */
    .reading-content .section-box p {
        margin-bottom: 1.5rem;
        padding: 0.5rem 0;
    }
    
    /* Responsive Design */
    @media (max-width: 768px) {
        body { font-size: 1rem; }
        h1 { font-size: 2rem; }
        h2 { font-size: 1.75rem; }
        h3 { font-size: 1.5rem; }
        h4 { font-size: 1.25rem; }
        p, li, div { font-size: 1rem; }
        .reading-content p { 
            font-size: 1.125rem; 
            margin-bottom: 1.25rem; 
            padding: 0.4rem 0;
        }
        .stButton>button { font-size: 1rem; padding: 0.5rem 1rem; }
        .stApp { padding: 1rem; }
        .reading-content { padding: 0 0.5rem; }
        .stSelectbox div[role="option"], .stSelectbox option {
            padding: 0.5rem 0.75rem;
            font-size: 1rem;
        }
    }
    
    @media (max-width: 480px) {
        body { font-size: 0.875rem; }
        h1 { font-size: 1.75rem; }
        h2 { font-size: 1.5rem; }
        h3 { font-size: 1.25rem; }
        p, li, div { font-size: 0.875rem; }
        .reading-content p { 
            font-size: 1rem; 
            margin-bottom: 1rem; 
            padding: 0.3rem 0;
        }
        .stButton>button { font-size: 0.875rem; }
        .stSelectbox div[role="option"], .stSelectbox option {
            padding: 0.4rem 0.6rem;
            font-size: 0.875rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# === Utilities ===
def is_allowed_url(url: str) -> bool:
    """Check if URL is from the allowed domain."""
    p = urlparse(url)
    return p.netloc == ALLOWED_DOMAIN and p.scheme in ("http", "https")

@lru_cache(maxsize=100)
def fetch_url(url: str, retries=2) -> str:
    """Fetch URL with retries and caching."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            time.sleep(1)
        except requests.RequestException as e:
            if attempt == retries - 1:
                st.error(f"Failed to fetch {url}: {e}. Check your internet connection.")
                raise
    raise Exception(f"Failed to fetch {url}")

def save_json(path, obj):
    """Save JSON data to file."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Failed to save JSON: {e}")

def load_json(path):
    """Load JSON data from file."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    except Exception as e:
        st.error(f"Failed to load JSON: {e}")
        return None

# === Scraping ===
def extract_chapter_links(index_html: str):
    """Extract chapter links from index page."""
    try:
        soup = BeautifulSoup(index_html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/study/manual/preach-my-gospel" in href:
                abs_url = urljoin("https://www.churchofjesuschrist.org", href)
                if is_allowed_url(abs_url):
                    title = a.get_text(strip=True) or urlparse(abs_url).path.split("/")[-1]
                    links.append((title, abs_url))
        seen = set()
        return [(t, u) for t, u in links if u not in seen and not seen.add(u)]
    except Exception as e:
        st.error(f"Failed to extract chapter links: {e}")
        return []

def scrape_chapter(url: str):
    """Scrape a single chapter's content."""
    try:
        html = fetch_url(url)
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find(["h1", "h2", "title"]) or soup.select_one("header h1, main h1")
        title = title_tag.get_text(strip=True) if title_tag else urlparse(url).path.split("/")[-1]
        article = soup.find("article") or soup.find("main") or soup.find("div", class_="body-block") or soup
        sections = []
        headings = article.find_all(["h2", "h3", "h4"])
        for tag in headings:
            heading = tag.get_text(strip=True)
            texts = []
            for el in tag.find_all_next():
                if el.name and el.name.startswith("h") and el.name <= tag.name:
                    break
                if el.name in ("p", "li", "div"):
                    t = el.get_text(" ", strip=True)
                    if t and len(t) > 10:
                        texts.append(t)
            if texts:
                sections.append({"heading": heading, "text": "\n\n".join(texts)})
        if not sections:
            paragraphs = [p.get_text(" ", strip=True) for p in article.find_all("p") if p.get_text(strip=True)]
            if paragraphs:
                sections = [{"heading": title, "text": "\n\n".join(paragraphs)}]
        return {"url": url, "title": title, "sections": sections}
    except Exception as e:
        st.error(f"Failed to scrape chapter {url}: {e}")
        return {"url": url, "title": "(Failed to Load)", "sections": []}

def scrape_chapters_concurrent(links):
    """Scrape chapters concurrently with rate limiting."""
    chapters = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_url = {executor.submit(scrape_chapter, url): (title, url) for title, url in links}
        for future in tqdm(as_completed(future_to_url), total=len(links), desc="Scraping Chapters"):
            title, url = future_to_url[future]
            try:
                chapters.append(future.result())
                time.sleep(RATE_LIMIT_SECONDS)
            except Exception as e:
                st.error(f"Failed to scrape {title}: {e}")
    return chapters

# === Progress Tracking ===
def init_sqlite(path=SQLITE_FILE):
    """Initialize SQLite database for progress."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY,
            chapter_url TEXT,
            section_index INTEGER,
            completed INTEGER DEFAULT 0,
            notes TEXT,
            last_reviewed TEXT,
            UNIQUE(chapter_url, section_index)
        )
        """)
        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Failed to initialize database: {e}")
        return None

def update_progress(conn, chapter_url, section_index, completed=False, notes=None):
    """Update progress in SQLite."""
    try:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO progress (chapter_url, section_index, completed, notes, last_reviewed) VALUES (?, ?, ?, ?, ?)",
                  (chapter_url, section_index, int(completed), notes or "", datetime.now().isoformat()))
        c.execute("UPDATE progress SET completed=?, notes=?, last_reviewed=? WHERE chapter_url=? AND section_index=?",
                  (int(completed), notes or "", datetime.now().isoformat(), chapter_url, section_index))
        conn.commit()
    except Exception as e:
        st.error(f"Failed to save progress: {e}")

def get_progress(conn, chapter_url, section_index):
    """Retrieve progress for a chapter and section."""
    try:
        c = conn.cursor()
        c.execute("SELECT completed, notes FROM progress WHERE chapter_url=? AND section_index=?",
                  (chapter_url, section_index))
        row = c.fetchone()
        return {"completed": bool(row[0]), "notes": row[1]} if row else None
    except Exception as e:
        st.error(f"Failed to retrieve progress: {e}")
        return None

# === Text Formatting ===
BOOKS = ["John", "Matthew", "Mark", "Luke", "Romans", "Alma", "Mosiah", "Helaman", "3 Nephi", "2 Nephi", "Ether", "Moroni", "Psalms", "Proverbs", "Isaiah", "Genesis", "Exodus", "Doctrine and Covenants", "1 Corinthians", "2 Corinthians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation"]
BOOK_RE = r'(' + r'|'.join([re.escape(b) for b in BOOKS]) + r')\s+\d+[:]\d+(-\d+)?'

def format_text(text):
    """Format text with highlighted scripture references, preserving paragraph breaks."""
    try:
        def replace_scripture(match):
            return f"<span class='scripture'>{match.group(0)}</span>"
        # Split by double newline to preserve paragraphs
        paragraphs = text.split("\n\n")
        # Apply scripture formatting to each paragraph and clean up
        formatted_paragraphs = [re.sub(BOOK_RE, replace_scripture, p.strip()) for p in paragraphs if p.strip()]
        return formatted_paragraphs
    except Exception as e:
        st.error(f"Failed to format text: {e}")
        return [text] if text else []

# === Streamlit UI ===
st.set_page_config(page_title="📖 Preach My Gospel Study", layout="wide", initial_sidebar_state="expanded")

# Display Streamlit version for debugging
st.markdown(f"<div style='font-size: 0.875rem; color: #718096; text-align: center;'>Streamlit Version: {st.__version__}</div>", unsafe_allow_html=True)

# Header
st.markdown("""
<div style="text-align: center; margin-bottom: 3rem;">
    <h1>📖 Preach My Gospel Study</h1>
    <p style="font-size: 1.25rem; color: #718096; font-style: italic;">
        Study with clarity and focus
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar: Controls
with st.sidebar:
    st.markdown("<h2 style='color: #FFFFFF; margin-bottom: 1.5rem;'>📚 Study Controls</h2>", unsafe_allow_html=True)
    
    if st.button("🔄 Scrape Official Manual"):
        with st.spinner("📥 Fetching *Preach My Gospel* content..."):
            try:
                idx_html = fetch_url(BASE_MANUAL_URL)
                links = extract_chapter_links(idx_html)
                if not links:
                    st.error("No chapters found. The website structure may have changed.")
                    st.stop()
                st.info(f"Found {len(links)} chapters.")
                chapters = scrape_chapters_concurrent(links)
                db = {"source": BASE_MANUAL_URL, "scraped_at": time.asctime(), "chapters": chapters}
                save_json(DB_JSON, db)
                st.success(f"✅ Saved {len(chapters)} chapters to database.")
                st.markdown("<div class='motivation'>🎉 You're ready to dive in!</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"❌ Failed to scrape: {e}. Check your connection or try again later.")

    if st.button("📂 Load Local Database"):
        db = load_json(DB_JSON)
        if db:
            st.success(f"✅ Loaded {len(db.get('chapters', []))} chapters.")
            st.markdown("<div class='motivation'>📖 Begin your study journey!</div>", unsafe_allow_html=True)
        else:
            st.warning("⚠️ No local database found. Please scrape the manual first.")

    st.markdown("<hr style='border-color: #B7C0CC; margin: 1.5rem 0;'>", unsafe_allow_html=True)
    
    # Progress Section
    st.markdown("<h3 style='color: #FFFFFF; margin-bottom: 1.25rem;'>📊 Your Progress</h3>", unsafe_allow_html=True)
    conn = init_sqlite()
    if conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM progress WHERE completed=1")
        completed = c.fetchone()[0]
        total_sections = sum(len(c.get("sections", [])) for c in load_json(DB_JSON).get("chapters", [])) if load_json(DB_JSON) else 0
        progress = (completed / total_sections * 100) if total_sections > 0 else 0
        
        st.markdown(f"<div style='font-size: 1.125rem; margin-bottom: 1rem; color: #FFFFFF;'><strong>Completed Sections:</strong> {completed}/{total_sections}</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class='progress-container'>
            <div class='progress-bar'>
                <div class='progress-fill' style='width: {progress}%'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"<div class='motivation'>🌟 You've completed {progress:.1f}%! Amazing progress!</div>", unsafe_allow_html=True)
    else:
        st.error("❌ Database not initialized. Progress tracking unavailable.")

# Main Content
db = load_json(DB_JSON)
if not db:
    st.markdown("""
    <div style="text-align: center; padding: 3rem; background: #D8DEE9; border-radius: 0.75rem; margin: 2rem 0;">
        <h3 style='color: #FFFFFF;'>📚 No Database Found</h3>
        <p style="font-size: 1.125rem; color: #FFFFFF;">Use the sidebar to scrape the official manual and start your study journey.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

chapters = db.get("chapters", [])
if not chapters:
    st.warning("⚠️ No chapters available. Try scraping again.")
    st.stop()

# Enhanced Layout
col1, col2 = st.columns([1, 3], gap="large")

with col1:
    st.markdown("<div class='chapter-selector'>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-bottom: 1.25rem; color: #1F2A44; font-weight: 600; display: inline-flex; align-items: center; gap: 0.2rem; white-space: nowrap;'>📖 Select Chapter</h3>", unsafe_allow_html=True)
    
    titles = [c.get("title", "(No Title)") for c in chapters]
    sel_idx = st.selectbox(
        "Choose a Chapter", 
        options=list(range(len(titles))), 
        format_func=lambda i: f"{i+1}. {titles[i]}", 
        label_visibility="collapsed"
    )
    
    ch = chapters[sel_idx]
    st.markdown(f"<h4 style='color: #1F2A44; margin-top: 1rem; font-weight: 600;'>{ch.get('title')}</h4>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Section Selection
    st.markdown("<div class='section-selector'>", unsafe_allow_html=True)
    st.markdown("<h4 style='margin-bottom: 1rem; color: #1F2A44; font-weight: 600; display: inline-flex; align-items: center; gap: 0.2rem; white-space: nowrap;'>📄 Select Section</h4>", unsafe_allow_html=True)
    
    sec_titles = [s.get("heading", "(No Heading)") for s in ch.get("sections", [])]
    if not sec_titles:
        st.warning("⚠️ No sections found in this chapter.")
        st.stop()
        
    sec_idx = st.selectbox(
        "Choose a Section", 
        options=list(range(len(sec_titles))), 
        format_func=lambda i: f"{i+1}. {sec_titles[i][:50]}{'...' if len(sec_titles[i]) > 50 else ''}", 
        label_visibility="collapsed"
    )
    
    # Progress Display
    prog = get_progress(conn, ch.get("url"), sec_idx) if conn else None
    if prog:
        if prog['completed']:
            st.markdown("<div class='status-completed'>✅ Completed</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='status-in-progress'>🔄 In Progress</div>", unsafe_allow_html=True)
        
        if prog.get("notes"):
            st.markdown("<h5 style='margin-top: 1rem; margin-bottom: 0.5rem; color: #FFFFFF; font-weight: 600;'>📝 Your Notes:</h5>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size: 1rem; color: #FFFFFF; font-style: italic; padding: 1rem; background: #2C7A7B; border-radius: 0.5rem;'>{prog['notes']}</div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='reading-content'>", unsafe_allow_html=True)
    
    # Section Content
    section = ch.get("sections", [])[sec_idx]
    heading = section.get("heading", "No Heading")
    text = section.get("text", "")
    paragraphs = format_text(text)
    
    st.markdown(f"""
    <div class='section-box'>
        <h3 style="color: #1F2A44; margin-bottom: 1.5rem;">{heading}</h3>
    """, unsafe_allow_html=True)
    
    for p in paragraphs:
        # Wrap each paragraph in a div to ensure spacing is respected
        st.markdown(f"<div style='margin-bottom: 1.5rem;'><p>{p}</p></div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Progress and Notes Section
    st.markdown("<div class='notes-section'>", unsafe_allow_html=True)
    st.markdown("<h3 style='color: #1F2A44; margin-bottom: 1.25rem;'>📝 Progress & Notes</h3>", unsafe_allow_html=True)
    
    current_notes = prog.get("notes", "") if prog else ""
    note = st.text_area(
        "Add your thoughts and insights for this section:", 
        value=current_notes, 
        height=150,
        key=f"notes_{sel_idx}_{sec_idx}",
        placeholder="What insights did you gain? How can you apply this section?"
    )
    
    current_completed = prog.get("completed", False) if prog else False
    complete = st.checkbox("✅ Mark this section as completed", value=current_completed, key=f"complete_{sel_idx}_{sec_idx}")
    
    if st.button("💾 Save Progress", key=f"save_{sel_idx}_{sec_idx}"):
        try:
            if conn:
                update_progress(conn, ch.get("url"), sec_idx, completed=complete, notes=note)
                st.success("✅ Progress saved successfully!")
                st.markdown("<div class='motivation'>🎉 Great job studying this section!</div>", unsafe_allow_html=True)
                time.sleep(1)
                st.experimental_rerun()
            else:
                st.error("❌ Database not available. Progress not saved.")
        except Exception as e:
            st.error(f"❌ Failed to save progress: {e}")
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("""
<div class="stCaption" style="margin-top: 3rem;">
    📚 Content sourced from the official <em>Preach My Gospel</em> manual<br>
    Copyright © The Church of Jesus Christ of Latter-day Saints
</div>
""", unsafe_allow_html=True)