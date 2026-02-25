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
st.set_page_config(page_title="Cyfer Pro: Authenticated", layout="centered")

raw_pepper = st.secrets.get("MY_SECRET_PEPPER") or "default_fallback_spice_2026"
PEPPER = str(raw_pepper).encode()
U_MOD = 256 
ROUNDS = 3

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

# --- 2. CSS STYLING ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: #DBDCFF !important; }}
    .main .block-container {{ padding-bottom: 150px !important; }}
    div[data-testid="stWidgetLabel"], label {{ display: none !important; }}

    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea {{
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

    div.stButton > button p {{ font-size: 38px !important; font-weight: 800 !important; }}

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
    </style>
    """, unsafe_allow_html=True)

# --- 3. ENGINE LOGIC ---
def calculate_chemistry(password):
    if not password: return 0.0
    score = min(len(password) / 16, 1.0) * 0.4
    if any(c.islower() for c in password): score += 0.15
    if any(c.isupper() for c in password): score += 0.15
    if any(c.isdigit() for c in password): score += 0.15
    if any(re.search(r"[ !@#$%^&*(),.?\":{}|<>]", c) for c in password): score += 0.15
    return min(score, 1.0)

def get_keys_and_perms(kw):
    # Derive a larger master key (64 bytes)
    # Part 1 (32 bytes) = Encryption parameters
    # Part 2 (32 bytes) = HMAC Authentication Key
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=b"affine_authenticated_v1", iterations=100000, backend=default_backend())
    master_key = kdf.derive(kw.encode() + PEPPER)
    
    enc_master = master_key[:32]
    auth_key = master_key[32:]
    
    rounds_params = []
    for i in range(ROUNDS):
        h = hashlib.sha256(enc_master + i.to_bytes(4, 'big')).digest()
        a = (int.from_bytes(h[:4], 'big') % 127) * 2 + 1 
        b = int.from_bytes(h[4:8], 'big') % 256
        p_list = list(range(256))
        seed = int.from_bytes(h[8:16], 'big')
        r = random.Random(seed)
        r.shuffle(p_list)
        rounds_params.append({'a': a, 'b': b, 'p': p_list, 'inv_p': [p_list.index(j) for j in range(256)]})
    
    return rounds_params, auth_key

def clear_everything():
    for k in ["lips", "chem", "hint"]:
        if k in st.session_state: st.session_state[k] = ""

# --- 4. UI ---
kw = st.text_input("Key", type="password", key="lips", placeholder="SECRET KEY").strip()
chem_lvl = calculate_chemistry(kw)
st.write(f"🧪 **CHEMISTRY LEVEL:** {int(chem_lvl*100)}%")
st.progress(chem_lvl)

user_input = st.text_area("Message", height=120, key="chem", placeholder="YOUR MESSAGE")
kiss_btn, tell_btn = st.button("KISS"), st.button("TELL")
st.button("DESTROY CHEMISTRY", on_click=clear_everything)

# --- 5. PROCESSING (Encrypt-then-MAC) ---
if kw and (kiss_btn or tell_btn):
    params, auth_key = get_keys_and_perms(kw)
    
    if kiss_btn:
        nonce_bytes = [secrets.randbelow(256) for _ in range(4)]
        raw_payload = bytes(nonce_bytes) + user_input.encode('utf-8')
        
        prev = int.from_bytes(hashlib.sha256(b"init_vector").digest()[:1], 'big')
        ciphertext_bytes = []
        for byte in raw_payload:
            current = byte ^ prev
            for r in range(ROUNDS):
                current = params[r]['p'][current]
                current = (params[r]['a'] * current + params[r]['b']) % 256
            ciphertext_bytes.append(current)
            prev = current
        
        # --- HMAC GENERATION ---
        # Compute HMAC over the ciphertext bytes
        mac = hmac.new(auth_key, bytes(ciphertext_bytes), hashlib.sha256).digest()
        # Append first 16 bytes of MAC to ciphertext
        final_bytes = bytes(ciphertext_bytes) + mac[:16]
        
        final_output = "".join(to_emoji(b) for b in final_bytes)
        st.markdown(f'<div class="result-box">{final_output}</div>', unsafe_allow_html=True)

    if tell_btn:
        try:
            full_data = from_emoji_string(user_input.strip())
            if len(full_data) < 21: # 4(nonce) + 1(msg) + 16(mac)
                raise ValueError("Payload too short")
            
            # Split ciphertext and HMAC
            incoming_ciphertext = bytes(full_data[:-16])
            incoming_mac = bytes(full_data[-16:])
            
            # --- HMAC VERIFICATION (Verify before Decrypt) ---
            expected_mac = hmac.new(auth_key, incoming_ciphertext, hashlib.sha256).digest()[:16]
            
            if not hmac.compare_digest(incoming_mac, expected_mac):
                st.error("🚫 AUTHENTICATION FAILURE: The message has been tampered with or the key is wrong.")
            else:
                # Proceed to decrypt
                prev_for_dec = int.from_bytes(hashlib.sha256(b"init_vector").digest()[:1], 'big')
                decoded_payload = []
                for current_cipher in incoming_ciphertext:
                    temp = current_cipher
                    for r in reversed(range(ROUNDS)):
                        a_inv = pow(params[r]['a'], -1, 256)
                        temp = (a_inv * (temp - params[r]['b'])) % 256
                        temp = params[r]['inv_p'][temp]
                    
                    original_byte = temp ^ prev_for_dec
                    decoded_payload.append(original_byte)
                    prev_for_dec = current_cipher
                
                decoded_msg = bytes(decoded_payload[4:]).decode('utf-8')
                st.markdown(f'<div class="whisper-text">Cypher Whispers: {decoded_msg}</div>', unsafe_allow_html=True)
        except Exception:
            st.error("Chemistry Error! Likely corrupted emojis.")
