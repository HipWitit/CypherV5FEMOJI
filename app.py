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
st.set_page_config(page_title="Cyfer Pro: PRF Shuffle", layout="centered")

raw_pepper = st.secrets.get("MY_SECRET_PEPPER") or "default_fallback_spice_2026"
PEPPER = str(raw_pepper).encode()
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

# --- 2. SACRED CSS ---
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
        color: #B4A7D6; font-family: "Courier New", monospace;
        font-size: 26px; border-top: 2px dashed #B4A7D6; text-align: center; padding-top: 15px;
    }}
    .footer-text {{ color: #B4A7D6; text-align: center; font-weight: bold; font-size: 22px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. CRYPTOGRAPHIC PRF LOGIC ---
def get_keys_and_perms(kw):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=b"prf_v1_stable", iterations=100000, backend=default_backend())
    master_key = kdf.derive(kw.encode() + PEPPER)
    enc_key, auth_key = master_key[:32], master_key[32:]
    
    rounds_params = []
    for i in range(ROUNDS):
        # Round-specific seed via HMAC-PRF
        round_seed = hmac.new(enc_key, i.to_bytes(4, 'big'), hashlib.sha256).digest()
        
        # 1. Fisher-Yates Shuffle driven by HMAC-PRF
        p_list = list(range(256))
        for j in range(255, 0, -1):
            # Generate a "random" index k in [0, j] using HMAC as the PRF
            index_material = hmac.new(round_seed, j.to_bytes(4, 'big'), hashlib.sha256).digest()
            k = int.from_bytes(index_material, 'big') % (j + 1)
            p_list[j], p_list[k] = p_list[k], p_list[j]
        
        # 2. Affine parameters derived from same round seed
        h_affine = hashlib.sha256(round_seed + b"affine").digest()
        a = (int.from_bytes(h_affine[:4], 'big') % 127) * 2 + 1 
        b = int.from_bytes(h_affine[4:8], 'big') % 256
        
        rounds_params.append({
            'a': a, 'b': b, 'p': p_list, 
            'inv_p': [p_list.index(v) for v in range(256)]
        })
    return rounds_params, auth_key

def calculate_chemistry(password):
    if not password: return 0.0
    score = min(len(password) / 16, 1.0) * 0.4
    for regex in [r"[a-z]", r"[A-Z]", r"[0-9]", r"[ !@#$%^&*(),.?\":{}|<>]"]:
        if re.search(regex, password): score += 0.15
    return min(score, 1.0)

# --- 4. UI ---
if os.path.exists("CYPHER.png"): st.image("CYPHER.png")
kw = st.text_input("Key", type="password", key="lips", placeholder="SECRET KEY").strip()
st.progress(calculate_chemistry(kw))
user_input = st.text_area("Message", height=120, key="chem", placeholder="YOUR MESSAGE")
kiss_btn, tell_btn = st.button("KISS"), st.button("TELL")

# --- 5. EXECUTION ---
if kw and (kiss_btn or tell_btn):
    params, auth_key = get_keys_and_perms(kw)
    
    if kiss_btn:
        nonce = bytes([secrets.randbelow(256) for _ in range(NONCE_SIZE)])
        payload = nonce + user_input.encode('utf-8')
        prev = int.from_bytes(hashlib.sha256(b"init").digest()[:1], 'big')
        cipher = []
        for byte in payload:
            curr = byte ^ prev
            for r in range(ROUNDS):
                curr = params[r]['p'][curr]
                curr = (params[r]['a'] * curr + params[r]['b']) % 256
            cipher.append(curr)
            prev = curr
        
        sig = hmac.new(auth_key, bytes(cipher), hashlib.sha256).digest()[:16]
        final = "".join(to_emoji(b) for b in (bytes(cipher) + sig))
        st.markdown(f'<div class="result-box">{final}</div>', unsafe_allow_html=True)

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
                st.markdown(f'<div class="whisper-text">{bytes(plain[NONCE_SIZE:]).decode()}</div>', unsafe_allow_html=True)
            else: st.error("🚫 AUTH FAILED")
        except: st.error("🚫 CHEMISTRY ERROR")

st.markdown('<div class="footer-text">CREATED BY</div>', unsafe_allow_html=True)
