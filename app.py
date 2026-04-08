import streamlit as st
import streamlit.components.v1 as components
from pymongo import MongoClient
import hashlib
import cloudinary
import cloudinary.uploader
import certifi
import time
import uuid  
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import datetime

# ---------------- UI CONFIG ----------------
st.set_page_config(page_title="voidememo Dashboard", page_icon="🌐", layout="wide")

# ---------------- CONFIG (PRODUCTION SAFE) ----------------
MONGO_URI = st.secrets["MONGO_URI"]

client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
db = client["memory_vault"]

users_col = db["users"]
files_col = db["files"]
folders_col = db["folders"]

cloudinary.config(
    cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key=st.secrets["CLOUDINARY_API_KEY"],
    api_secret=st.secrets["CLOUDINARY_API_SECRET"]
)

# ---------------- UTILS & POPUP DIALOGS ----------------
def hash_password(password):
    return hashlib.sha256(password.strip().encode()).hexdigest()

def delete_folder_tree(folder_id):
    subfolders = list(folders_col.find({"parent_id": folder_id}))
    for sub in subfolders:
        delete_folder_tree(sub["_id"])
    
    files = list(files_col.find({"folder_id": folder_id}))
    for f in files:
        cloudinary.uploader.destroy(f["public_id"], resource_type=f["resource_type"])
    
    files_col.delete_many({"folder_id": folder_id})
    folders_col.delete_one({"_id": folder_id})

def send_otp_email(receiver_email, otp):
    try:
        sender_email = st.secrets["SMTP_EMAIL"]
        sender_password = st.secrets["SMTP_PASSWORD"] 
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "voidememo - Password Reset OTP"
        
        body = f"Hello,\n\nYou have requested to reset your password. Your 6-digit OTP is: {otp}\n\nIf you did not request this, please ignore this email."
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# ---------------- SESSION ----------------
defaults = {
    "logged_in": False,
    "username": "",
    "current_folder": None,
    "page": "drive",
    "folder_key": 0,
    "uploader_key": 0,
    "reset_step": 0,
    "reset_email": "",
    "auth_view": "login" 
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if not st.session_state.logged_in and "session" in st.query_params:
    token = st.query_params["session"]
    user = users_col.find_one({"session_token": token})
    if user:
        st.session_state.logged_in = True
        st.session_state.username = user["username"]
        root = folders_col.find_one({"username": user["username"], "parent_id": None})
        if root: st.session_state.current_folder = root["_id"]

# ---------------- AUTH LOGIC ----------------
def register(email, password, first_name, last_name, birthday):
    if users_col.find_one({"email": email}): return False
    username = email.split('@')[0]
    users_col.insert_one({
        "username": username, "first_name": first_name, "last_name": last_name,
        "birthday": str(birthday), "email": email, "password": hash_password(password),
        "profile_photo": "", "bio": "", "session_token": "", "reset_otp": "" 
    })
    root = folders_col.insert_one({"username": username, "folder_name": "root", "parent_id": None})
    st.session_state.current_folder = root.inserted_id
    return username

def login(email, password):
    user = users_col.find_one({"email": email})
    if user and user["password"] == hash_password(password):
        root = folders_col.find_one({"username": user["username"], "parent_id": None})
        if root: st.session_state.current_folder = root["_id"]
        return user["username"]
    return False

# ================= CSS: PROFESSIONAL UI ALIGNMENT =================
def inject_auth_css():
    css = """
    <style>
    /* 1. Base App Background */
    .stApp { background-color: #f4f2e6 !important; }
    header { visibility: hidden; }

    /* 2. The Unified White Card */
    .block-container {
        max-width: 850px !important;
        background-color: #ffffff !important;
        padding: 40px 60px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 40px rgba(0,0,0,0.05) !important;
        margin-top: 12vh !important;
        margin-bottom: 10vh !important;
    }

    /* 3. Vertically Center Content Across Columns */
    div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
    }

    /* 4. Form Inputs Styling (Bulletproof) */
    .stTextInput div[data-baseweb="input"], 
    .stDateInput div[data-baseweb="input"] {
        background-color: #e5e7eb !important;
        border: 2px solid #e11d48 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease;
    }
    .stTextInput input, .stDateInput input {
        background-color: transparent !important;
        color: #111111 !important;
        padding: 12px 16px !important;
        font-size: 15px !important;
    }
    ::placeholder { color: #6b7280 !important; opacity: 1 !important; }
    
    /* Input Focus State */
    .stTextInput div[data-baseweb="input"]:focus-within,
    .stDateInput div[data-baseweb="input"]:focus-within {
        border-color: #4b90ff !important;
        box-shadow: none !important;
    }

    /* Hide the password eye background block */
    .stTextInput div[data-baseweb="input"] > div:last-child {
        background: transparent !important;
    }

    /* 5. Buttons */
    .stButton > button[kind="primary"] {
        background-color: #4b90ff !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        width: 100% !important;
        margin-top: 10px !important;
    }
    .stButton > button[kind="primary"]:hover { background-color: #3b82f6 !important; }

    .stButton > button[kind="secondary"] {
        background-color: transparent !important;
        color: #111111 !important;
        border: 1.5px solid #111111 !important;
        border-radius: 8px !important;
        padding: 10px 40px !important;
        font-weight: 600 !important;
        display: block !important;
        margin: 0 auto !important; /* Perfectly centers the button */
    }
    .stButton > button[kind="secondary"]:hover { background-color: #f3f4f6 !important; }

    .stButton > button[kind="tertiary"] {
        color: #6b7280 !important;
        background: transparent !important;
        padding: 0 !important;
        font-size: 13px !important;
        display: flex !important;
        justify-content: flex-end !important;
        width: 100% !important;
        margin-top: -5px !important;
    }
    .stButton > button[kind="tertiary"]:hover { color: #111111 !important; text-decoration: underline; }

    /* 6. Typography Helper Classes */
    .center-text { text-align: center; }
    .title-text { color: #111; font-weight: 800; font-size: 28px; margin-bottom: 5px; }
    .title-small { color: #111; font-weight: 700; font-size: 20px; margin-bottom: 8px; }
    .sub-text { color: #6b7280; font-size: 14px; margin-bottom: 25px; }
    .logo-text { color: #4b90ff; font-weight: 700; font-size: 18px; letter-spacing: 1px; margin-bottom: 20px; }
    
    /* 7. Responsive stacking for mobile */
    @media (max-width: 768px) {
        .block-container { padding: 30px 25px !important; margin-top: 5vh !important; }
        div[data-testid="stHorizontalBlock"] { flex-direction: column !important; gap: 40px !important; }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ================= LANDING (EXACT LAYOUT) =================
if not st.session_state.logged_in:
    
    inject_auth_css()
    
    # Simple Columns: Let Streamlit handle the grid cleanly
    col_left, col_right = st.columns(2, gap="large")

    # --- 1. LOGIN VIEW ---
    if st.session_state.auth_view == "login":
        
        with col_left: # Form Side
            st.markdown('''
            <div class="center-text">
                <div class="logo-text">voidememo</div>
                <div class="title-text">Welcome Back</div>
                <div class="sub-text">Please enter your credentials to log in</div>
            </div>
            ''', unsafe_allow_html=True)
            
            email = st.text_input("Email", placeholder="Email", label_visibility="collapsed", key="l_email")
            pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="l_pwd")
            
            _, c_link = st.columns([1.5, 1])
            with c_link:
                if st.button("Forgot Password?", type="tertiary", use_container_width=True):
                    st.session_state.auth_view = "forgot"
                    st.rerun()
            
            if st.button("SIGN IN", type="primary", use_container_width=True):
                if not email or not pwd:
                    st.error("Please enter email and password.")
                else:
                    result = login(email, pwd)
                    if result:
                        token = str(uuid.uuid4())
                        users_col.update_one({"username": result}, {"$set": {"session_token": token}})
                        st.query_params["session"] = token 
                        st.session_state.logged_in = True
                        st.session_state.username = result
                        st.rerun()
                    else:
                        st.error("Invalid credentials")

        with col_right: # Switch Side
            st.markdown('''
            <div class="center-text">
                <div class="title-small">New to our Platform?</div>
                <div class="sub-text">Create an account to build your vault.</div>
            </div>
            ''', unsafe_allow_html=True)
            
            if st.button("SIGN UP", type="secondary"):
                st.session_state.auth_view = "signup"
                st.rerun()


    # --- 2. SIGN UP VIEW ---
    elif st.session_state.auth_view == "signup":
        
        with col_left: # Switch Side
            st.markdown('''
            <div class="center-text">
                <div class="title-small">Already have an account?</div>
                <div class="sub-text">Sign in to access your vault.</div>
            </div>
            ''', unsafe_allow_html=True)
            
            if st.button("SIGN IN", type="secondary"):
                st.session_state.auth_view = "login"
                st.rerun()

        with col_right: # Form Side
            st.markdown('''
            <div class="center-text">
                <div class="logo-text">voidememo</div>
                <div class="title-text">Sign Up</div>
                <div class="sub-text">Please provide your information to sign up.</div>
            </div>
            ''', unsafe_allow_html=True)
            
            # Using nested columns safely (won't break since we removed destructive CSS)
            c_fn, c_ln = st.columns(2)
            with c_fn: fname = st.text_input("First Name", placeholder="First Name", label_visibility="collapsed", key="s_fname")
            with c_ln: lname = st.text_input("Last Name", placeholder="Last Name", label_visibility="collapsed", key="s_lname")
                
            bday = st.date_input("Birthday", value=datetime.date(2000, 1, 1), min_value=datetime.date(1900, 1, 1), label_visibility="collapsed")
            s_email = st.text_input("Email", placeholder="you@example.com", label_visibility="collapsed", key="s_email")
            s_pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="s_pwd")
            
            if st.button("SIGN UP", type="primary", use_container_width=True):
                if not s_email or not s_pwd or not fname:
                    st.error("Please fill all required fields.")
                else:
                    result = register(s_email, s_pwd, fname, lname, bday)
                    if result:
                        token = str(uuid.uuid4())
                        users_col.update_one({"username": result}, {"$set": {"session_token": token}})
                        st.query_params["session"] = token
                        st.session_state.logged_in = True
                        st.session_state.username = result
                        st.rerun()
                    else:
                        st.error("Email already registered. Try logging in.")


    # --- 3. FORGOT PASSWORD VIEW ---
    elif st.session_state.auth_view == "forgot":
        
        with col_left: # Form Side
            st.markdown('''
            <div class="center-text">
                <div class="logo-text">voidememo</div>
                <div class="title-text">Forgot Password</div>
            </div>
            ''', unsafe_allow_html=True)
            
            if st.session_state.reset_step == 0:
                st.markdown('<div class="center-text sub-text">Please enter your registered email</div>', unsafe_allow_html=True)
                f_email = st.text_input("Email", placeholder="Email", label_visibility="collapsed", key="f_email")
                
                if st.button("RESET PASSWORD", type="primary", use_container_width=True):
                    if f_email:
                        user = users_col.find_one({"email": f_email})
                        if user:
                            with st.spinner("Sending OTP..."):
                                otp = str(random.randint(100000, 999999))
                                users_col.update_one({"email": f_email}, {"$set": {"reset_otp": otp}})
                                if send_otp_email(f_email, otp):
                                    st.session_state.reset_step = 1
                                    st.session_state.reset_email = f_email
                                    st.rerun()
                                else:
                                    st.error("Email dispatch failed. Check SMTP settings.")
                        else:
                            st.error("No account found with that email.")
                            
            elif st.session_state.reset_step == 1:
                st.markdown('<div class="center-text sub-text">Enter the 6-digit code sent to your email</div>', unsafe_allow_html=True)
                st.success(f"OTP sent to {st.session_state.reset_email}")
                entered_otp = st.text_input("Enter 6-Digit OTP", placeholder="123456", label_visibility="collapsed", key="entered_otp")
                new_pwd = st.text_input("Enter New Password", type="password", placeholder="New Password", label_visibility="collapsed", key="new_pwd")
                
                if st.button("CONFIRM RESET", type="primary", use_container_width=True):
                    if len(new_pwd) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        user = users_col.find_one({"email": st.session_state.reset_email})
                        if user and user.get("reset_otp") == entered_otp:
                            users_col.update_one(
                                {"email": st.session_state.reset_email}, 
                                {"$set": {"password": hash_password(new_pwd), "reset_otp": ""}}
                            )
                            st.success("Password successfully updated!")
                            time.sleep(1.5)
                            st.session_state.reset_step = 0
                            st.session_state.reset_email = ""
                            st.session_state.auth_view = "login"
                            st.rerun()
                        else:
                            st.error("Invalid token!")

        with col_right: # Switch Side
            st.markdown('''
            <div class="center-text">
                <div class="title-small" style="margin-top: 20px;">Remembered your password?</div>
                <div class="sub-text">Head back to access your vault.</div>
            </div>
            ''', unsafe_allow_html=True)
            
            if st.button("LOG IN", type="secondary"):
                st.session_state.reset_step = 0
                st.session_state.auth_view = "login"
                st.rerun()


# ================= DASHBOARD (LIQUID GLASS) =================
# ... (Dashboard logic remains unchanged below) ...
else:
    # --- DASHBOARD HEADER ---
    components.html(
        """
        <style>
            body { margin: 0; padding: 0; font-family: -apple-system, sans-serif; }
            .glass-nav {
                display: flex; justify-content: space-between; align-items: center;
                background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding: 15px 30px;
                border-radius: 0 0 20px 20px; color: rgba(255, 255, 255, 0.9); box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
            }
            .logo { font-size: 20px; font-weight: bold; letter-spacing: 1px;}
            .clock { font-size: 16px; font-weight: 500; opacity: 0.9;}
        </style>
        <div class="glass-nav">
            <div class="logo">🌐 voidememo Vault</div>
            <div class="clock" id="live-clock">Loading...</div>
        </div>
        <script>
            function updateTime() {
                const now = new Date();
                const timeString = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                const dateString = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                document.getElementById('live-clock').innerText = "⏱️ " + timeString + " | " + dateString;
            }
            setInterval(updateTime, 1000);
            updateTime();
        </script>
        """,
        height=70,
    )

    # --- LIQUID GLASS DASHBOARD CSS ---
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #0f2027, #203a43, #2c5364) !important; }
    .block-container { max-width: 1400px !important; width: 100% !important; padding-top: 1rem !important; padding-bottom: 80px !important; margin-top: 0 !important; position: static !important; transform: none !important; background: transparent !important; box-shadow: none !important;}
    .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label { color: #e0e0e0 !important; text-align: left; }
    .card { 
        position: relative; border-radius: 16px; overflow: hidden;
        background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px); 
        border: 1px solid rgba(255, 255, 255, 0.15); box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3); 
        transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), box-shadow 0.3s ease;
    }
    .card:hover { transform: translateY(-6px); box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.5); }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, rgba(41, 128, 185, 0.6), rgba(44, 62, 80, 0.8)) !important; backdrop-filter: blur(25px) !important; border-right: 1px solid rgba(255, 255, 255, 0.1) !important; }
    [data-testid="stSidebar"] .stButton > button { background: transparent !important; border: none !important; box-shadow: none !important; text-align: left !important; justify-content: flex-start !important; padding-left: 15px !important; font-size: 16px !important; border-radius: 10px !important; margin-bottom: 5px !important; width: 100% !important; color: white !important;}
    [data-testid="stSidebar"] .stButton > button:hover { background: rgba(255, 255, 255, 0.15) !important; transform: translateX(5px) !important; }
    div[role="dialog"] { background: rgba(20, 30, 40, 0.65) !important; backdrop-filter: blur(25px) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 20px !important; box-shadow: 0 10px 50px rgba(0, 0, 0, 0.8) !important; }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea { background: rgba(255, 255, 255, 0.05) !important; backdrop-filter: blur(10px) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; color: white !important; border-radius: 10px !important; }
    [data-testid="stFileUploader"] > div { background: rgba(255, 255, 255, 0.05) !important; backdrop-filter: blur(10px) !important; border: 1px dashed rgba(255, 255, 255, 0.3) !important; border-radius: 16px !important; transition: all 0.3s ease; }
    .stApp .stButton > button { background: rgba(255, 255, 255, 0.08) !important; backdrop-filter: blur(10px) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.2) !important; border-radius: 10px; color: white !important; transition: all 0.3s ease !important; width: 100% !important;}
    .stApp .stButton > button[kind="primary"] { background: rgba(50, 150, 255, 0.2) !important; border: 1px solid rgba(50, 150, 255, 0.4) !important; }
    .glass-download { display: flex; justify-content: center; align-items: center; background: rgba(255, 255, 255, 0.08); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 10px; text-decoration: none; height: 42px; transition: all 0.3s ease; }
    .overlay { position:absolute; top:0; left:0; width:100%; height:100%; background: rgba(0, 0, 0, 0.3); backdrop-filter: blur(2px); opacity:0; transition:0.3s ease-in-out; }
    .card:hover .overlay { opacity:1; }
    .custom-footer { position: fixed; bottom: 0; left: 0; width: 100%; text-align: center; padding: 12px; background: rgba(20, 30, 40, 0.6); backdrop-filter: blur(15px); border-top: 1px solid rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.6); font-size: 14px; z-index: 1000; }
    </style>
    <div class="custom-footer">Copyright © 2026 by @Kunal_Mandal | All Rights Reserved.</div>
    """, unsafe_allow_html=True)


    if st.session_state.current_folder is None:
        root = folders_col.find_one({"username": st.session_state.username, "parent_id": None})
        if root:
            st.session_state.current_folder = root["_id"]

    # --- SIDEBAR (DASHBOARD STYLE) ---
    st.sidebar.markdown("<h2 style='text-align: center; color: white; margin-bottom: 20px;'>Menu</h2>", unsafe_allow_html=True)

    if st.sidebar.button("📊 Dashboard Area", use_container_width=True):
        st.session_state.page = "drive"
        st.rerun()

    if st.sidebar.button("⚙️ Profile Settings", use_container_width=True):
        st.session_state.page = "profile"
        st.rerun()

    st.sidebar.write("<br><br>", unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Secure Logout", use_container_width=True):
        users_col.update_one({"username": st.session_state.username}, {"$set": {"session_token": ""}})
        if "session" in st.query_params:
            del st.query_params["session"]
            
        st.session_state.logged_in = False
        st.session_state.current_folder = None
        st.session_state.auth_view = "login"
        st.rerun()

    user_data = users_col.find_one({"username": st.session_state.username})

    # ================= MAIN AREA (DRIVE) =================
    if st.session_state.page == "drive":
        
        current = folders_col.find_one({"_id": st.session_state.current_folder})
        is_root = current is None or current.get("parent_id") is None

        # --- TOP DASHBOARD METRICS (Visible only in Root) ---
        if is_root:
            st.markdown("<h2 style='text-align: center; margin-bottom: 30px;'>Admin Control Panel</h2>", unsafe_allow_html=True)
            
            dash_c1, dash_c2, dash_c3 = st.columns([1, 1, 1.5])
            
            total_folders = folders_col.count_documents({"username": st.session_state.username}) - 1
            total_files = files_col.count_documents({"username": st.session_state.username})
            
            with dash_c1:
                st.markdown(f"""
                <div class="card" style="padding: 20px; text-align: center; height: 100%;">
                    <h2 style="margin: 0; color: #4facfe; text-align: center;">{total_folders}</h2>
                    <p style="margin: 0; opacity: 0.8; text-align: center;">Total Folders</p>
                </div>
                """, unsafe_allow_html=True)
                
            with dash_c2:
                st.markdown(f"""
                <div class="card" style="padding: 20px; text-align: center; height: 100%;">
                    <h2 style="margin: 0; color: #4facfe; text-align: center;">{total_files}</h2>
                    <p style="margin: 0; opacity: 0.8; text-align: center;">Total Files</p>
                </div>
                """, unsafe_allow_html=True)
                
            with dash_c3:
                prof_pic = user_data.get("profile_photo") or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
                bio = user_data.get("bio") or "Welcome to your Dashboard"
                display_name = user_data.get("first_name", st.session_state.username)
                
                st.markdown(f"""
                <div class="card" style="padding: 15px; display: flex; align-items: center; gap: 15px; height: 100%;">
                    <img src="{prof_pic}" style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(255,255,255,0.3);">
                    <div>
                        <h3 style="margin: 0;">{display_name}</h3>
                        <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">"{bio}"</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            st.write("<br>", unsafe_allow_html=True)

            with st.expander("➕ Create New Folder"):
                new_folder = st.text_input("Folder Name", key=f"folder_input_{st.session_state.folder_key}", label_visibility="collapsed")
                if st.button("Create Folder", type="primary"):
                    if new_folder:
                        folders_col.insert_one({
                            "username": st.session_state.username,
                            "folder_name": new_folder,
                            "parent_id": st.session_state.current_folder
                        })
                        st.session_state.folder_key += 1 
                        st.rerun()

        # Navigation
        if current and not is_root:
            nav_c1, nav_c2 = st.columns([3, 1])
            with nav_c1:
                st.title(f"📂 {current['folder_name']}")
            with nav_c2:
                st.write("")
                if st.button("⬅ Back to Dashboard", use_container_width=True):
                    st.session_state.current_folder = current["parent_id"]
                    st.rerun()
            st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)

        # Show folders
        folders = list(folders_col.find({
            "username": st.session_state.username,
            "parent_id": st.session_state.current_folder
        }))

        if folders:
            if is_root: st.subheader("Your Directories")
            f_cols = st.columns(4)
            for i, folder in enumerate(folders):
                with f_cols[i % 4]:
                    if st.button(f"📁 {folder['folder_name']}", key=f"folder_{folder['_id']}", use_container_width=True):
                        st.session_state.current_folder = folder["_id"]
                        st.rerun()
                    
                    c1, c2 = st.columns(2)
                    if c1.button("✏️ Rename", key=f"edit_{folder['_id']}", use_container_width=True):
                        rename_folder_dialog(folder["_id"], folder["folder_name"])
                        
                    if c2.button("🗑️ Delete", key=f"del_fold_{folder['_id']}", use_container_width=True):
                        delete_folder_dialog(folder["_id"], folder["folder_name"])

                    st.write("<br>", unsafe_allow_html=True) 
        
        # Upload
        if not is_root:
            with st.expander("☁️ Upload Files", expanded=True):
                uploaded_files = st.file_uploader("Drag and drop files here (Max 1GB)", accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}", label_visibility="collapsed")

                if uploaded_files:
                    with st.spinner("Uploading to secure vault..."):
                        for file in uploaded_files:
                            r_type = "video" if file.type.startswith("video") else "image"
                            file_size_mb = file.size / (1024 * 1024)
                            
                            try:
                                if file_size_mb > 50:
                                    res = cloudinary.uploader.upload_large(file, resource_type=r_type, chunk_size=20000000)
                                else:
                                    res = cloudinary.uploader.upload(file, resource_type=r_type)

                                files_col.insert_one({
                                    "username": st.session_state.username,
                                    "folder_id": st.session_state.current_folder,
                                    "filename": file.name,
                                    "url": res["secure_url"],
                                    "public_id": res["public_id"],
                                    "resource_type": r_type,
                                    "tag": "",
                                    "tag_time": 0 
                                })
                            except Exception as e:
                                st.error(f"Failed to upload {file.name}. Error: {e}")
                    
                    st.session_state.uploader_key += 1 
                    st.success("Files successfully uploaded!")
                    time.sleep(1) 
                    st.rerun()

        # Files Display
        files = list(files_col.find({
            "username": st.session_state.username,
            "folder_id": st.session_state.current_folder
        }))

        if files:
            st.write("<br>", unsafe_allow_html=True)
            cols = st.columns(3)

            for i, file in enumerate(files):
                with cols[i % 3]:

                    st.markdown('<div class="card">', unsafe_allow_html=True)

                    if file.get("tag"):
                        st.markdown(f"""
                        <div style="position:absolute; top:10px; right:10px; font-size:24px; z-index:10; background: rgba(255, 255, 255, 0.2); backdrop-filter: blur(5px); padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.3);">
                            {file['tag']}
                        </div>
                        """, unsafe_allow_html=True)

                    if file["resource_type"] == "image":
                        st.image(file["url"], use_container_width=True)
                    else:
                        st.video(file["url"])

                    st.markdown('<div class="overlay"></div></div>', unsafe_allow_html=True)

                    c1, c2, c3 = st.columns([2, 1, 1])
                    tag_time = file.get("tag_time", 0)
                    time_elapsed = time.time() - tag_time
                    is_locked = bool(file.get("tag")) and (time_elapsed < 86400) 

                    with c1:
                        if is_locked:
                            remaining_seconds = 86400 - time_elapsed
                            if st.button(f"🔒 {file['tag']}", key=f"lock_{file['_id']}", use_container_width=True):
                                locked_reaction_dialog(remaining_seconds)
                        else:
                            button_label = f"✨ Change {file['tag']}" if file.get("tag") else "😀 React"
                            with st.popover(button_label, use_container_width=True):
                                emojis = ["🥰", "❤️", "😘", "🔥", "😂", "👍", "🎉", "✨", "🥺", "😎", "💯", "🙏", "😭", "😮", "😡", "💩"]
                                e_cols = st.columns(4)
                                for e_idx, em in enumerate(emojis):
                                    if e_cols[e_idx % 4].button(em, key=f"em_{file['_id']}_{e_idx}", use_container_width=True):
                                        files_col.update_one({"_id": file["_id"]}, {"$set": {"tag": em, "tag_time": time.time()}})
                                        st.rerun()

                    with c2:
                        st.markdown(f'<a href="{file["url"]}" download target="_blank" class="glass-download" title="Download">⬇️</a>', unsafe_allow_html=True)

                    with c3:
                        if st.button("🗑", key=f"del_{file['_id']}", use_container_width=True):
                            delete_file_dialog(file["_id"], file["public_id"], file["resource_type"])

                    st.write("<br>", unsafe_allow_html=True) 

    # ================= PROFILE =================
    elif st.session_state.page == "profile":
        st.title("👤 Profile Settings")
        
        with st.container():
            st.markdown("<div class='card' style='padding: 30px;'>", unsafe_allow_html=True)
            bio = st.text_area("Update your Bio", value=user_data.get("bio", ""))
            pic = st.file_uploader("Upload New Profile Photo", key="profile_pic_upload")

            if st.button("💾 Save Changes", type="primary"):
                data = {}
                if pic:
                    res = cloudinary.uploader.upload(pic)
                    data["profile_photo"] = res["secure_url"]

                data["bio"] = bio
                users_col.update_one({"username": st.session_state.username}, {"$set": data})

                st.success("Profile Updated Successfully!")
                time.sleep(1)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)