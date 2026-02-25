import streamlit as st
import re
import os
import secrets
import hashlib
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.argon2 import Argon2

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Cyfer Pro", layout="centered")

raw_pepper = st.secrets.get("MY_SECRET_PEPPER") or "default_fallback_spice_2026"
PEPPER = str(raw_pepper).encode()
NONCE_SIZE = 12 

@st.cache_data
def get_stable_emoji_list():
    base_list = []
    ranges = [(0x1F300, 0x1F3F0), (0x1F400, 0x1F4FF), (0x1F600, 0x1F64F)]
    for start, end in ranges:
        for codepoint in range(start, end):
            if len(base_list) < 256:
                base_list.append(chr(codepoint))
    return base_list

STABLE_EMOJIS = get_stable_emoji_list()
EMOJI_TO_BYTE = {emoji: i for i, emoji in enumerate(STABLE_EMOJIS)}

def to_emoji(val):
    return STABLE_EMOJIS[val % 256]

def from_emoji_string(s):
    emojis = re.findall(r'.', s, re.UNICODE)
    return [EMOJI_TO_BYTE[char] for char in emojis if char in EMOJI_TO_BYTE]

# --- 2. THE SACRED CSS ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: #DBDCFF !important; }}
    .main .block-container {{ padding-bottom: 150px !important; }}
    div[data-testid="stWidgetLabel"], label {{ display: none !important; }}
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {{
        background-color: #FEE2E9 !important; color: #B4A7D6 !important; 
        border: 2px solid #B4A7D6 !important; font-family: "Courier New", monospace !important;
        font-size: 18px !important; font-weight: bold !important;
    }}
    .stProgress > div > div > div > div {{ background-color: #B4A7D6 !important; }}
    div.stButton > button {{
        background-color: #B4A7D6 !important; color: #FFD4E5 !important;
        border-radius: 15px !important; min-height: 100px !important; 
        border: none !important; text-transform: uppercase;
    }}
    div.stButton > button p {{ font-size: 38px !important; font-weight: 800 !important; }}
    .result-box {{
        background-color: #FEE2E9; color: #B4A7D6; padding: 15px;
        border-radius: 10px; border: 2px solid #B4A7D6; word-wrap: break-word;
        text-align: center; font-size: 24px; font-weight: bold; margin-top: 15px;
    }}
    .whisper-text {{
        color: #B4A7D6; font-family: "Courier New", monospace !important;
        font-weight: bold; font-size: 26px; border-top: 2px dashed #B4A7D6;
        padding-top: 15px; text-align: center; margin-top: 20px;
    }}
    .footer-text {{ color: #B4A7D6; font-size: 22px; font-weight: bold; text-align: center; margin-top: 15px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. THE CHEMISTRY (Argon2id + ChaCha20) ---
def get_derived_key(kw):
    # Salt derived from Pepper for consistent key generation
    salt = hashlib.sha256(PEPPER).digest()[:16]
    kdf = Argon2(memory_cost=65536, time_cost=3, parallelism=4, length=32, salt=salt)
    return kdf.derive(kw.encode())

def calculate_chemistry(password):
    if not password: return 0.0
    score = min(len(password) / 16, 1.0) * 0.4
    for p in [r"[a-z]", r"[A-Z]", r"[0-9]", r"[ !@#$%^&*(),.?\":{}|<>]"]:
        if re.search(p, password): score += 0.15
    return min(score, 1.0)

# --- 4. UI ---
if os.path.exists("CYPHER.png"): st.image("CYPHER.png")
kw = st.text_input("Key", type="password", key="lips", placeholder="SECRET KEY").strip()
st.progress(calculate_chemistry(kw))
user_input = st.text_area("Message", height=120, key="chem", placeholder="YOUR MESSAGE")

kiss_btn, tell_btn = st.button("KISS"), st.button("TELL")

# --- 5. EXECUTION ---
if kw and (kiss_btn or tell_btn):
    try:
        with st.spinner("Refining Chemistry..."):
            key = get_derived_key(kw)
        aead = ChaCha20Poly1305(key)
        
        if kiss_btn:
            nonce = secrets.token_bytes(NONCE_SIZE)
            ciphertext = aead.encrypt(nonce, user_input.encode(), None)
            output = "".join(to_emoji(b) for b in (nonce + ciphertext))
            st.markdown(f'<div class="result-box">{output}</div>', unsafe_allow_html=True)
            components.html(f"""<button onclick="navigator.share({{title:'Secret',text:`{output}`}})" style="background-color:#B4A7D6; color:#FFD4E5; font-weight:bold; border-radius:15px; min-height:80px; width:100%; cursor:pointer; font-size: 28px; border:none; text-transform:uppercase;">SHARE ✨</button>""", height=100)

        if tell_btn:
            data = bytes(from_emoji_string(user_input.strip()))
            nonce, cipher = data[:NONCE_SIZE], data[NONCE_SIZE:]
            msg = aead.decrypt(nonce, cipher, None).decode()
            st.markdown(f'<div class="whisper-text">Cypher Whispers: {msg}</div>', unsafe_allow_html=True)
            
    except Exception:
        st.error("🚫 CHEMISTRY ERROR: AUTHENTICATION FAILED.")

st.markdown('<div class="footer-text">CREATED BY</div>', unsafe_allow_html=True)
