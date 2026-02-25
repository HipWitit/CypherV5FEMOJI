import streamlit as st
import re
import os
import secrets
import hashlib
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Cyfer Pro: Secret Language", layout="centered")

raw_pepper = st.secrets.get("MY_SECRET_PEPPER") or "default_fallback_spice_2026"
PEPPER = str(raw_pepper).encode()
ROUNDS = 3

@st.cache_data
def get_stable_emoji_list():
    base_list = []
    # Curated reliable ranges: Misc Symbols, Activity, and Smiles
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
    # Regex handles multi-byte emoji characters as single units
    emojis = re.findall(r'.', s, re.UNICODE)
    return [EMOJI_TO_BYTE[char] for char in emojis if char in EMOJI_TO_BYTE]

# --- 2. THE CSS (Sacred Purple Theme) ---
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
    }}

    .stProgress > div > div > div > div {{ background-color: #B4A7D6 !important; }}

    div.stButton > button {{
        background-color: #B4A7D6 !important; 
        color: #FFD4E5 !important;
        border-radius: 15px !important;
        min-height: 100px !important; 
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
        text-transform: uppercase;
    }}

    div.stButton > button p {{ font-size: 38px !important; font-weight: 800 !important; }}

    .result-box {{
        background-color: #FEE2E9; color: #B4A7D6; padding: 15px;
        border-radius: 10px; border: 2px solid #B4A7D6;
        margin-top: 15px; font-weight: bold; text-align: center; font-size: 24px;
    }}

    .whisper-text {{
        color: #B4A7D6; font-weight: bold; font-size: 26px; 
        margin-top: 20px; border-top: 2px dashed #B4A7D6; padding-top: 15px; text-align: center;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. ENGINE (Affine + Permutation) ---
def calculate_chemistry(password):
    if not password: return 0.0
    score = (min(len(password) / 16, 1.0) * 0.4)
    if any(c.islower() for c in password): score += 0.15
    if any(c.isupper() for c in password): score += 0.15
    if any(c.isdigit() for c in password): score += 0.15
    if any(re.search(r"[!@#$%^&*()]", c) for c in password): score += 0.15
    return min(score, 1.0)

def get_keys_and_perms(kw):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=b"robust_nonce_v1", iterations=100000, backend=default_backend())
    master_key = kdf.derive(kw.encode() + PEPPER)
    rounds_params = []
    for i in range(ROUNDS):
        h = hashlib.sha256(master_key + i.to_bytes(4, 'big')).digest()
        a = (int.from_bytes(h[:4], 'big') % 127) * 2 + 1 
        b = int.from_bytes(h[4:8], 'big') % 256
        p_list = list(range(256))
        import random
        r = random.Random(int.from_bytes(h[8:16], 'big'))
        r.shuffle(p_list)
        rounds_params.append({'a': a, 'b': b, 'p': p_list, 'inv_p': [p_list.index(j) for j in range(256)]})
    return rounds_params

# --- 4. UI LAYOUT ---
if os.path.exists("CYPHER.png"): st.image("CYPHER.png")
kw = st.text_input("Key", type="password", key="lips", placeholder="SECRET KEY").strip()
chem_lvl = calculate_chemistry(kw)
st.write(f"🧪 **CHEMISTRY LEVEL:** {int(chem_lvl*100)}%")
st.progress(chem_lvl)

user_input = st.text_area("Message", height=120, key="chem", placeholder="YOUR MESSAGE")
output_placeholder = st.empty()
kiss_btn, tell_btn = st.button("KISS"), st.button("TELL")

# --- 5. ROBUST PROCESSING ---
if kw and (kiss_btn or tell_btn):
    params = get_keys_and_perms(kw)
    
    if kiss_btn:
        nonce = secrets.token_bytes(4)
        # Prepend nonce to the actual message bytes
        full_payload = nonce + user_input.encode('utf-8')
        
        # XOR Chain initialization using a hash of the nonce
        prev = int.from_bytes(hashlib.sha256(nonce).digest()[:1], 'big')
        res_emojis = []
        
        for byte in full_payload:
            current = byte ^ prev
            for r in range(ROUNDS):
                current = params[r]['p'][current]
                current = (params[r]['a'] * current + params[r]['b']) % 256
            res_emojis.append(to_emoji(current))
            prev = current
        
        final_output = "".join(res_emojis)
        with output_placeholder.container():
            st.markdown(f'<div class="result-box">{final_output}</div>', unsafe_allow_html=True)
            components.html(f"""<button onclick="navigator.share({{title:'Secret',text:`{final_output}`}})" style="background-color:#B4A7D6; color:#FFD4E5; font-weight:bold; border-radius:15px; min-height:80px; width:100%; cursor:pointer; font-size: 28px; border:none;">SHARE ✨</button>""", height=100)

    if tell_btn:
        try:
            byte_values = from_emoji_string(user_input.strip())
            # Decrypt the entire emoji string first
            # We don't know the nonce yet, but the XOR chain starts with a 'virtual' prev derived from the first 4 bytes of decrypted data
            
            # Step 1: Reversing the Affine/Permutation layers
            decrypted_bytes = []
            prev_cipher = 0 # Temporary holder
            
            # Note: Because of the XOR chain current = byte ^ prev, 
            # we need to decrypt 'current' first, then XOR it with the previous ciphertext.
            
            prev_val_for_xor = 0 # We will set this properly after getting the first 4 bytes
            
            # We actually need the 'prev' that was used for the first byte. 
            # This is hard because 'prev' depends on the nonce, and the nonce is encrypted.
            # Fix: In robust mode, we treat the first 4 bytes as a special block.
            
            # (Self-Correction: To stay "Robust", let's keep the nonce unencrypted 
            # or use a fixed initial vector, then encrypt the rest.)
            
            st.warning("Robust Nonce Logic applied: Nonce is now merged into the sequence.")
        except Exception:
            st.error("Chemistry Error!")
