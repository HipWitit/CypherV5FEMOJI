import streamlit as st
import re
import os
import secrets
import hashlib
import struct  # Required for binary packing of parameters
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from argon2.low_level import hash_secret_raw, Type

# --- 1. CONFIG & CONSTANTS ---
st.set_page_config(page_title="Cyfer Pro", layout="centered")

VERSION_BYTE = b'\x02' # Version 2 supports dynamic parameters
SALT_SIZE = 16
NONCE_SIZE = 12 

# Current Sacred Parameters
DEFAULT_T = 3
DEFAULT_M = 65536  # 64MB
DEFAULT_P = 4

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
        box-shadow: 0px 4px 12px rgba(0,0,0,0.1);
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

# --- 3. CORE LOGIC ---
def get_derived_key(kw, salt, t, m, p):
    return hash_secret_raw(
        secret=kw.encode(), salt=salt, time_cost=t,
        memory_cost=m, parallelism=p, hash_len=32, type=Type.ID
    )

def calculate_chemistry(password):
    if not password: return 0.0
    score = min(len(password) / 16, 1.0) * 0.4
    for p in [r"[a-z]", r"[A-Z]", r"[0-9]", r"[ !@#$%^&*(),.?\":{}|<>]"]:
        if re.search(p, password): score += 0.15
    return min(score, 1.0)

def clear_everything():
    for k in ["lips", "chem", "hint"]:
        if k in st.session_state: st.session_state[k] = ""

# --- 4. UI ---
if os.path.exists("CYPHER.png"): st.image("CYPHER.png")
kw = st.text_input("Key", type="password", key="lips", placeholder="SECRET KEY").strip()
st.progress(calculate_chemistry(kw))
user_input = st.text_area("Message", height=120, key="chem", placeholder="YOUR MESSAGE")

output_placeholder = st.empty()
kiss_btn, tell_btn = st.button("KISS"), st.button("TELL")
st.button("DESTROY CHEMISTRY", on_click=clear_everything)
st.markdown('<div class="footer-text">CREATED BY</div>', unsafe_allow_html=True)

# --- 5. EXECUTION ---
if kw and (kiss_btn or tell_btn):
    try:
        if kiss_btn:
            salt = secrets.token_bytes(SALT_SIZE)
            nonce = secrets.token_bytes(NONCE_SIZE)
            
            with st.spinner("Refining Chemistry..."):
                key = get_derived_key(kw, salt, DEFAULT_T, DEFAULT_M, DEFAULT_P)
                aead = ChaCha20Poly1305(key)
                ciphertext = aead.encrypt(nonce, user_input.encode(), None)
            
            # Pack Header: Version(1) + T(1) + M(4) + P(1) = 7 bytes
            header = VERSION_BYTE + struct.pack(">BIB", DEFAULT_T, DEFAULT_M, DEFAULT_P)
            final_payload = header + salt + nonce + ciphertext
            output = "".join(to_emoji(b) for b in final_payload)
            
            with output_placeholder.container():
                st.markdown(f'<div class="result-box">{output}</div>', unsafe_allow_html=True)
                components.html(f"""<button onclick="navigator.share({{title:'Secret',text:`{output}`}})" style="background-color:#B4A7D6; color:#FFD4E5; font-weight:bold; border-radius:15px; min-height:80px; width:100%; cursor:pointer; font-size: 28px; border:none; text-transform:uppercase;">SHARE ✨</button>""", height=100)

        if tell_btn:
            data = bytes(from_emoji_string(user_input.strip()))
            version = data[0:1]
            
            if version == b'\x01':
                # Legacy Support
                t, m, p = 3, 65536, 4
                salt = data[1:17]
                nonce = data[17:29]
                ciphertext = data[29:]
            elif version == b'\x02':
                # Dynamic Support: Extract params from bytes 1-7
                t, m, p = struct.unpack(">BIB", data[1:7])
                salt = data[7:23]
                nonce = data[23:35]
                ciphertext = data[35:]
            else:
                st.error("⚠️ UNKNOWN CHEMISTRY VERSION")
                st.stop()
                
            with st.spinner("Refining Chemistry..."):
                key = get_derived_key(kw, salt, t, m, p)
                aead = ChaCha20Poly1305(key)
                msg = aead.decrypt(nonce, ciphertext, None).decode()
            output_placeholder.markdown(f'<div class="whisper-text">Cypher Whispers: {msg}</div>', unsafe_allow_html=True)
            
    except Exception:
        st.error("🚫 CHEMISTRY ERROR: AUTHENTICATION FAILED.")
