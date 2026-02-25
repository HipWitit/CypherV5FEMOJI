import streamlit as st
import re
import os
import random
import secrets
import hashlib
import hmac
import base64
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Cyfer Pro: Secret Language", layout="centered")

raw_pepper = st.secrets.get("MY_SECRET_PEPPER") or "default_fallback_spice_2026"
PEPPER = str(raw_pepper).encode()
U_MOD = 256 
ROUNDS = 3
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

# --- 2. THE CSS (Restoring Sacred Layout) ---
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

# --- 3. ENGINE LOGIC (PRF-Driven Fisher-Yates) ---
def get_keys_and_perms(kw):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=b"affine_v5_stable", iterations=100000, backend=default_backend())
    master_key = kdf.derive(kw.encode() + PEPPER)
    enc_key, auth_key = master_key[:32], master_key[32:]
    
    rounds_params = []
    for i in range(ROUNDS):
        round_seed = hmac.new(enc_key, i.to_bytes(4, 'big'), hashlib.sha256).digest()
        
        # Fisher-Yates Shuffle driven by PRF
        p_list = list(range(256))
        for j in range(255, 0, -1):
            index_bytes = hmac.new(round_seed, j.to_bytes(4, 'big'), hashlib.sha256).digest()
            k = int.from_bytes(index_bytes, 'big') % (j + 1)
            p_list[j], p_list[k] = p_list[k], p_list[j]
        
        h_affine = hashlib.sha256(round_seed + b"affine").digest()
        a = (int.from_bytes(h_affine[:4], 'big') % 127) * 2 + 1 
        b = int.from_bytes(h_affine[4:8], 'big') % 256
        rounds_params.append({'a': a, 'b': b, 'p': p_list, 'inv_p': [p_list.index(v) for v in range(256)]})
    return rounds_params, auth_key

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
st.write(f"🧪 **CHEMISTRY LEVEL:** {int(calculate_chemistry(kw)*100)}%")
st.progress(calculate_chemistry(kw))

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
    params, auth_key = get_keys_and_perms(kw)
    
    if kiss_btn:
        nonce = bytes([secrets.randbelow(256) for _ in range(NONCE_SIZE)])
        raw_payload = nonce + user_input.encode('utf-8')
        prev = int.from_bytes(hashlib.sha256(b"init").digest()[:1], 'big')
        cipher_bytes = []
        for byte in raw_payload:
            current = byte ^ prev
            for r in range(ROUNDS):
                current = params[r]['p'][current]
                current = (params[r]['a'] * current + params[r]['b']) % 256
            cipher_bytes.append(current)
            prev = current
        
        sig = hmac.new(auth_key, bytes(cipher_bytes), hashlib.sha256).digest()[:16]
        final_output = "".join(to_emoji(b) for b in (bytes(cipher_bytes) + sig))
        with output_placeholder.container():
            st.markdown(f'<div class="result-box">{final_output}</div>', unsafe_allow_html=True)
            components.html(f"""<button onclick="navigator.share({{title:'Secret',text:`{final_output}\\n\\nHint: {hint_text}`}})" style="background-color:#B4A7D6; color:#FFD4E5; font-weight:bold; border-radius:15px; min-height:80px; width:100%; cursor:pointer; font-size: 28px; border:none; text-transform:uppercase;">SHARE ✨</button>""", height=100)

    if tell_btn:
        try:
            raw = from_emoji_string(user_input.strip())
            c_part, sig_part = bytes(raw[:-16]), bytes(raw[-16:])
            if hmac.compare_digest(hmac.new(auth_key, c_part, hashlib.sha256).digest()[:16], sig_part):
                prev_dec = int.from_bytes(hashlib.sha256(b"init").digest()[:1], 'big')
                plain = []
                for c in c_part:
                    temp = c
                    for r in reversed(range(ROUNDS)):
                        a_inv = pow(params[r]['a'], -1, 256)
                        temp = params[r]['inv_p'][(a_inv * (temp - params[r]['b'])) % 256]
                    plain.append(temp ^ prev_dec)
                    prev_dec = c
                decoded_msg = bytes(plain[NONCE_SIZE:]).decode('utf-8')
                output_placeholder.markdown(f'<div class="whisper-text">Cypher Whispers: {decoded_msg}</div>', unsafe_allow_html=True)
            else: st.error("🚫 AUTHENTICATION FAILED")
        except: st.error("🚫 CHEMISTRY ERROR")
