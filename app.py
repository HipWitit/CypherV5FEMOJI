import streamlit as st
import re
import os
import secrets
import hashlib
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.argon2 import Argon2
from cryptography.hazmat.backends import default_backend

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Cyfer Pro: Argon2id", layout="centered")

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

# --- 2. THE CSS (Sacred Layout) ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: #DBDCFF !important; }}
    .main .block-container {{ padding-bottom: 150px !important; }}
    div[data-testid="stWidgetLabel"], label {{ display: none !important; }}
    .stTextInput > div > div > input, .stTextArea > div > div > textarea,
    input::placeholder, textarea::placeholder {{
        background-color: #FEE2E9 !important;
        color: #B4A7D6 !important; 
        border: 2px solid #B4A7D6 !important;
        font-family: "Courier New", Courier, monospace !important;
        font-size: 18px !important;
        font-weight: bold !important;
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
        text-align: center; font-size: 24px; font-weight: bold;
    }}
    .whisper-text {{
        color: #B4A7D6; font-family: "Courier New", monospace !important;
        font-weight: bold; font-size: 26px; margin-top: 20px;
        border-top: 2px dashed #B4A7D6; padding-top: 15px; text-align: center;
    }}
    .footer-text {{ color: #B4A7D6; text-align: center; font-weight: bold; font-size: 22px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. ENGINE LOGIC (Argon2id KDF) ---
def get_argon2_key(kw):
    # Argon2id parameters: memory_cost (64MB), time_cost (3 rounds), parallelism (4 threads)
    kdf = Argon2(
        memory_cost=65536,
        time_cost=3,
        parallelism=4,
        length=32,
        salt=hashlib.sha256(PEPPER).digest()[:16] # Deterministic salt for app stability
    )
    return kdf.derive(kw.encode())

def calculate_chemistry(password):
    if not password: return 0.0
    score = min(len(password) / 16, 1.0) * 0.4
    for pattern in [r"[a-z]", r"[A-Z]", r"[0-9]", r"[ !@#$%^&*(),.?\":{}|<>]"]:
        if re.search(pattern, password): score += 0.15
    return min(score, 1.0)

def clear_everything():
    for k in ["lips", "chem", "hint"]:
        if k in st.session_state: st.session_state[k] = ""

# --- 4. UI ---
if os.path.exists("CYPHER.png"): st.image("CYPHER.png")
kw = st.text_input("Key", type="password", key="lips", placeholder="SECRET KEY").strip()
st.progress(calculate_chemistry(kw))
hint_text = st.text_input("Hint", key="hint", placeholder="KEY HINT (Optional)")
user_input = st.text_area("Message", height=120, key="chem", placeholder="YOUR MESSAGE")

output_placeholder = st.empty()
kiss_btn, tell_btn = st.button("KISS"), st.button("TELL")
st.button("DESTROY CHEMISTRY", on_click=clear_everything)

st.markdown('<div class="footer-text">CREATED BY</div>', unsafe_allow_html=True)

# --- 5. PROCESSING ---
if kw and (kiss_btn or tell_btn):
    try:
        # Argon2id is computationally heavy; Streamlit will show a spinner automatically
        with st.spinner("Refining Chemistry..."):
            key = get_argon2_key(kw)
        chacha = ChaCha20Poly1305(key)
        
        if kiss_btn:
            nonce = secrets.token_bytes(NONCE_SIZE)
            ciphertext = chacha.encrypt(nonce, user_input.encode('utf-8'), None)
            final_payload = nonce + ciphertext
            final_output = "".join(to_emoji(b) for b in final_payload)
            with output_placeholder.container():
                st.markdown(f'<div class="result-box">{final_output}</div>', unsafe_allow_html=True)
                components.html(f"""<button onclick="navigator.share({{title:'Secret',text:`{final_output}\\n\\nHint: {hint_text}`}})" style="background-color:#B4A7D6; color:#FFD4E5; font-weight:bold; border-radius:15px; min-height:80px; width:100%; cursor:pointer; font-size: 28px; border:none; text-transform:uppercase;">SHARE ✨</button>""", height=100)

        if tell_btn:
            byte_data = bytes(from_emoji_string(user_input.strip()))
            nonce, ciphertext = byte_data[:NONCE_SIZE], byte_data[NONCE_SIZE:]
            decrypted_msg = chacha.decrypt(nonce, ciphertext, None).decode('utf-8')
            output_placeholder.markdown(f'<div class="whisper-text">Cypher Whispers: {decrypted_msg}</div>', unsafe_allow_html=True)
            
    except Exception:
        st.error("🚫 CHEMISTRY ERROR: AUTHENTICATION FAILED.")
