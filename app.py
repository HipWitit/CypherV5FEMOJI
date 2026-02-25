import streamlit as st
import re
import os
import secrets
import hashlib
import struct
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from argon2.low_level import hash_secret_raw, Type

# --- 1. CONFIG & CONSTANTS ---
st.set_page_config(page_title="Cyfer Pro", layout="centered")

VERSION_BYTE = b'\x02' 
SALT_SIZE = 16
NONCE_SIZE = 12 

# Sacred Parameters
T_COST = 3
M_COST = 65536 
P_FACTOR = 4

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

    /* Specific Styling for the Info Orb */
    div.stButton > button[key="info_orb"] {{
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 80px !important;
        height: 80px !important;
        min-height: 80px !important;
        border-radius: 50% !important;
        background-color: #B4A7D6 !important;
        color: #FFD4E5 !important;
        border: 3px solid #FEE2E9 !important;
        box-shadow: 0px 4px 15px rgba(180, 167, 214, 0.4);
        z-index: 1000;
        transition: all 0.3s ease;
    }}
    
    div.stButton > button[key="info_orb"]:hover {{
        transform: scale(1.1);
        background-color: #D1C4E9 !important;
    }}

    div.stButton > button[key="info_orb"] p {{
        font-family: "Courier New", monospace !important;
        font-size: 18px !important;
        font-weight: bold !important;
        line-height: 1.2 !important;
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

# --- 2.5 HELP DIALOG ---
@st.dialog("How to use Cyfer's Secret Love Language")
def show_help():
    st.markdown(f"""
    <div style="font-family: 'Courier New', Courier, monospace; color: #B4A7D6;">
    <h3 style="color: #B4A7D6;">🧪 Refining Secrets</h3>
    <p>1. <b>The Key:</b> Enter a secret word or phrase. This is your combination.</p>
    <p>2. <b>The Hint:</b> If you use one, it becomes part of the lock. You <b>must</b> provide the exact same hint to unlock it later.</p>
    <p>3. PRESS <b>KISS:</b> This turns your message into a string of emojis.</p>
    
    <h3 style="color: #B4A7D6;">👂 Whispering Secrets</h3>
    <p>1. Paste the emojis into the <b>Message</b> box.</p>
    <p>2. Enter the <b>Key</b> and the <b>Hint</b> (if used). <b>IMPORTANT:</b> Key and hint are case sensitive.</p>
    <p>3. PRESS <b>TELL:</b> This reveals the hidden message that Cypher whispers to you.</p>
    <hr style="border: 1px dashed #B4A7D6;">
    <p><i>Note: If the hint or key is off by even a single space, the chemistry will fail!</i></p>
    </div>
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

# --- 4. UI ELEMENTS ---
# Floating Info Orb
st.button("Info", key="info_orb", on_click=show_help)

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

# --- 5. THE CHEMISTRY PROCESS ---
if kw and (kiss_btn or tell_btn):
    try:
        aad = hint_text.encode() if hint_text else None

        if kiss_btn:
            salt = secrets.token_bytes(SALT_SIZE)
            nonce = secrets.token_bytes(NONCE_SIZE)
            
            with st.spinner("Refining Chemistry..."):
                key = get_derived_key(kw, salt, T_COST, M_COST, P_FACTOR)
                aead = ChaCha20Poly1305(key)
                ciphertext = aead.encrypt(nonce, user_input.encode(), aad)
            
            header = VERSION_BYTE + struct.pack(">BIB", T_COST, M_COST, P_FACTOR)
            final_payload = header + salt + nonce + ciphertext
            output = "".join(to_emoji(b) for b in final_payload)
            
            with output_placeholder.container():
                st.markdown(f'<div class="result-box">{output}</div>', unsafe_allow_html=True)
                components.html(f"""<button onclick="navigator.share({{title:'Secret',text:`{output}\\n\\nHint: {hint_text}`}})" style="background-color:#B4A7D6; color:#FFD4E5; font-weight:bold; border-radius:15px; min-height:80px; width:100%; cursor:pointer; font-size: 28px; border:none; text-transform:uppercase;">SHARE ✨</button>""", height=100)

        if tell_btn:
            data = bytes(from_emoji_string(user_input.strip()))
            version = data[0:1]
            
            if version == b'\x01':
                t, m, p = 3, 65536, 4
                salt, nonce, ciphertext = data[1:17], data[17:29], data[29:]
                current_aad = None 
            elif version == b'\x02':
                t, m, p = struct.unpack(">BIB", data[1:7])
                salt, nonce, ciphertext = data[7:23], data[23:35], data[35:]
                current_aad = aad
            else:
                st.error("⚠️ UNKNOWN VERSION")
                st.stop()
                
            with st.spinner("Extracting Secret..."):
                key = get_derived_key(kw, salt, t, m, p)
                aead = ChaCha20Poly1305(key)
                msg = aead.decrypt(nonce, ciphertext, current_aad).decode()
                
            output_placeholder.markdown(f'<div class="whisper-text">Cypher Whispers: {msg}</div>', unsafe_allow_html=True)
            
    except Exception:
        st.error("🚫 CHEMISTRY ERROR: AUTHENTICATION FAILED. Check Key and Hint.")
