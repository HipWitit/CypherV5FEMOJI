import streamlit as st
import re
import os
import secrets
import hashlib
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Cyfer Pro: ChaCha20", layout="centered")

raw_pepper = st.secrets.get("MY_SECRET_PEPPER") or "default_fallback_spice_2026"
PEPPER = str(raw_pepper).encode()
NONCE_SIZE = 12 # Standard for ChaCha20-Poly1305

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

# --- 2. THE CSS (Preserving Sacred Layout) ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: #DBDCFF !important; }}
    .main .block-container {{ padding-bottom: 150px !important; }}
    div[data-testid="stWidgetLabel"], label {{ display: none !important; }}

    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea,
    input::placeholder, textarea::placeholder {{
        background-color: #FEE2E9 !important;
        color: #B4A7D6 !important; 
        border: 2px solid #B4A7D6 !important;
        font-family: "Courier New", Courier, monospace !important;
        font-size: 18px !important;
        font-weight: bold !important;
    }}

    .stProgress > div > div > div > div {{ 
        background-color: #B4A7D6 !important; 
        box-shadow: 0px 0px 10px rgba(180, 167, 214, 0.5);
    }}

    [data-testid="column"], [data-testid="stVerticalBlock"] > div {{ width: 100% !important; flex: 1 1 100% !important; }}
    .stButton, .stButton > button {{ width: 100% !important; display: block !important; }}

    div.stButton > button {{
        background-color: #B4A7D6 !important; 
        color: #FFD4E5 !important;
        border-radius: 15px !important;
        min-height: 100px !important; 
        border: none !important;
        text-transform: uppercase;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
        margin-top: 15px !important;
    }}

    div.stButton > button p {{
        font-size: 38px !important; 
        font-weight: 800 !important;
        line-height: 1.1 !important;
        margin: 0 !important;
        text-align: center !important;
    }}

    div[data-testid="stVerticalBlock"] > div:last-child .stButton > button {{
        min-height: 70px !important;
        background-color: #D1C4E9 !important;
        border: none !important;
    }}

    .result-box {{
        background-color: #FEE2E9; color: #B4A7D6; padding: 15px;
        border-radius: 10px; font-family: "Courier New", monospace !important;
        border: 2px solid #B4A7D6; word-wrap: break-word;
        margin-top: 15px; font-weight: bold; text-align: center; font-size: 24px;
    }}

    .whisper-text {{
        color: #B4A7D6; font-family: "Courier New", monospace !important;
        font-weight: bold; font-size: 26px; margin-top: 20px;
        border-top: 2px dashed #B4A7D6; padding-top: 15px; text-align: center;
    }}

    .footer-text {{
        color: #B4A7D6; font-family: "Courier New", Courier, monospace;
        font-size: 22px; font-weight: bold; margin-top: 15px;
        letter-spacing: 2px; text-align: center;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. ENGINE LOGIC (ChaCha20-Poly1305) ---
def get_aead_key(kw):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"sacred_chacha_v1",
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(kw.encode() + PEPPER)

def calculate_chemistry(password):
    if not password: return 0.0
    score = min(len(password) / 16, 1.0) * 0.4
    if any(c.islower() for c in password): score += 0.15
    if any(c.isupper() for c in password): score += 0.15
    if any(c.isdigit() for c in password): score += 0.15
    if any(re.search(r"[ !@#$%^&*(),.?\":{}|<>]", c) for c in password): score += 0.15
    return min(score, 1.0)

def clear_everything():
    for k in ["lips", "chem", "hint"]:
        if k in st.session_state: st.session_state[k] = ""

# --- 4. UI ---
if os.path.exists("CYPHER.png"): st.image("CYPHER.png")
if os.path.exists("Lock Lips.png"): st.image("Lock Lips.png")

kw = st.text_input("Key", type="password", key="lips", placeholder="SECRET KEY").strip()
chem_lvl = calculate_chemistry(kw)
st.write(f"🧪 **CHEMISTRY LEVEL:** {int(chem_lvl*100)}%")
st.progress(chem_lvl)

hint_text = st.text_input("Hint", key="hint", placeholder="KEY HINT (Optional)")
if os.path.exists("Kiss Chemistry.png"): st.image("Kiss Chemistry.png")
user_input = st.text_area("Message", height=120, key="chem", placeholder="YOUR MESSAGE")

output_placeholder = st.empty()
kiss_btn, tell_btn = st.button("KISS"), st.button("TELL")
st.button("DESTROY CHEMISTRY", on_click=clear_everything)

if os.path.exists("LPB.png"):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2: st.image("LPB.png")

st.markdown('<div class="footer-text">CREATED BY</div>', unsafe_allow_html=True)

# --- 5. PROCESSING ---
if kw and (kiss_btn or tell_btn):
    key = get_aead_key(kw)
    chacha = ChaCha20Poly1305(key)
    
    if kiss_btn:
        nonce = secrets.token_bytes(NONCE_SIZE)
        # chacha.encrypt returns ciphertext + 16-byte Poly1305 tag
        ciphertext = chacha.encrypt(nonce, user_input.encode('utf-8'), None)
        final_payload = nonce + ciphertext
        
        final_output = "".join(to_emoji(b) for b in final_payload)
        with output_placeholder.container():
            st.markdown(f'<div class="result-box">{final_output}</div>', unsafe_allow_html=True)
            components.html(f"""<button onclick="navigator.share({{title:'Secret',text:`{final_output}\\n\\nHint: {hint_text}`}})" style="background-color:#B4A7D6; color:#FFD4E5; font-weight:bold; border-radius:15px; min-height:80px; width:100%; cursor:pointer; font-size: 28px; border:none; text-transform:uppercase;">SHARE ✨</button>""", height=100)

    if tell_btn:
        try:
            byte_data = bytes(from_emoji_string(user_input.strip()))
            if len(byte_data) < (NONCE_SIZE + 16): # Nonce + Tag
                raise ValueError("Payload too short")
            
            nonce = byte_data[:NONCE_SIZE]
            ciphertext = byte_data[NONCE_SIZE:]
            
            # Poly1305 tag is automatically verified during decryption
            decrypted_msg = chacha.decrypt(nonce, ciphertext, None).decode('utf-8')
            output_placeholder.markdown(f'<div class="whisper-text">Cypher Whispers: {decrypted_msg}</div>', unsafe_allow_html=True)
        except Exception:
            st.error("🚫 CHEMISTRY ERROR: AUTHENTICATION FAILED. (Wrong key or tampered message)")
