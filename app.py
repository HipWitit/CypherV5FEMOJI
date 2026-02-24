import streamlit as st
import os
import secrets
import hashlib
import math
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# --- 1. CONFIG & STYLING (Sacred Layout) ---
st.set_page_config(page_title="Cyfer Pro: Secret Language", layout="centered")

raw_pepper = st.secrets.get("MY_SECRET_PEPPER") or "global_unicode_spice_2026"
PEPPER = str(raw_pepper).encode()
U_MOD = 256 
ROUNDS = 3
EMOJI_START = 0x1F300  # Start of a dense emoji block

st.markdown("""
    <style>
    .stApp { background-color: #DBDCFF !important; }
    div[data-testid="stWidgetLabel"], label { display: none !important; }
    .stTextInput input, .stTextArea textarea {
        background-color: #FEE2E9 !important;
        color: #B4A7D6 !important; 
        border: 2px solid #B4A7D6 !important;
        font-family: "Courier New", monospace !important;
        font-size: 18px !important; font-weight: bold !important;
    }
    .stButton > button {
        background-color: #B4A7D6 !important; color: #FFD4E5 !important;
        border-radius: 15px !important; min-height: 100px !important; 
        font-size: 38px !important; font-weight: 800 !important;
        text-transform: uppercase; box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
    }
    .result-box {
        background-color: #FEE2E9; color: #B4A7D6; padding: 20px;
        border-radius: 10px; border: 2px solid #B4A7D6;
        font-size: 24px; text-align: center; word-wrap: break-word;
    }
    .whisper-text {
        color: #B4A7D6; font-size: 26px; font-weight: bold;
        text-align: center; border-top: 2px dashed #B4A7D6; padding-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DENSE MAPPING ENGINE ---
def to_emoji(val):
    return chr(EMOJI_START + val)

def from_emoji_string(s):
    # Extracts each emoji and converts back to byte value
    return [ord(char) - EMOJI_START for char in s]

def get_keys_and_perms(kw):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=b"csprng_v4_dense", iterations=100000, backend=default_backend())
    master_key = kdf.derive(kw.encode() + PEPPER)
    rounds_params = []
    for i in range(ROUNDS):
        h = hashlib.sha256(master_key + i.to_bytes(4, 'big')).digest()
        a = (int.from_bytes(h[:4], 'big') % 120) * 2 + 1 
        b = int.from_bytes(h[4:8], 'big') % 256
        p_list = list(range(256))
        seed = int.from_bytes(h[8:16], 'big')
        import random
        r = random.Random(seed)
        r.shuffle(p_list)
        rounds_params.append({'a': a, 'b': b, 'p': p_list, 'inv_p': [p_list.index(j) for j in range(256)]})
    return rounds_params

# --- 3. UI ---
if os.path.exists("CYPHER.png"): st.image("CYPHER.png")
kw = st.text_input("Key", type="password", key="lips", placeholder="SECRET KEY").strip()
hint_text = st.text_input("Hint", key="hint", placeholder="KEY HINT (Optional)")
user_input = st.text_area("Message", height=120, key="chem", placeholder="YOUR MESSAGE")

kiss_btn, tell_btn = st.button("KISS"), st.button("TELL")

# --- 4. PROCESSING ---
if kw and (kiss_btn or tell_btn):
    params = get_keys_and_perms(kw)
    
    if kiss_btn:
        data = user_input.encode('utf-8')
        nonce_bytes = [secrets.randbelow(256) for _ in range(4)]
        prev = int.from_bytes(hashlib.sha256(bytes(nonce_bytes)).digest()[:1], 'big')
        
        # Build compact ciphertext
        res = "".join([to_emoji(b) for b in nonce_bytes])
        for byte in data:
            current = byte ^ prev
            for r in range(ROUNDS):
                current = params[r]['p'][current]
                current = (params[r]['a'] * current + params[r]['b']) % 256
            res += to_emoji(current)
            prev = current
        
        st.markdown(f'<div class="result-box">{res}</div>', unsafe_allow_html=True)
        components.html(f"""<button onclick="navigator.share({{title:'Secret',text:`{res}\\n\\nHint: {hint_text}`}})" style="background-color:#B4A7D6; color:#FFD4E5; font-weight:bold; border-radius:15px; min-height:80px; width:100%; cursor:pointer; font-size: 28px; border:none; text-transform:uppercase;">SHARE ✨</button>""", height=100)

    if tell_btn:
        try:
            # Strip spaces if user added them, though the new format is space-less
            input_clean = user_input.replace(" ", "")
            byte_values = from_emoji_string(input_clean)
            
            nonce_bytes = byte_values[:4]
            ciphertext_payload = byte_values[4:]
            prev = int.from_bytes(hashlib.sha256(bytes(nonce_bytes)).digest()[:1], 'big')
            
            decoded_bytes = []
            for current_cipher in ciphertext_payload:
                temp = current_cipher
                for r in reversed(range(ROUNDS)):
                    a_inv = pow(params[r]['a'], -1, 256)
                    temp = (a_inv * (temp - params[r]['b'])) % 256
                    temp = params[r]['inv_p'][temp]
                
                original_byte = temp ^ prev
                decoded_bytes.append(original_byte)
                prev = current_cipher
            
            st.markdown(f'<div class="whisper-text">Cypher Whispers: {bytes(decoded_bytes).decode("utf-8")}</div>', unsafe_allow_html=True)
        except:
            st.error("Chemistry Error! Corrupted or incompatible message.")

