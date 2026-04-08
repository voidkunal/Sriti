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
st.set_page_config(page_title="Voidmemo Dashboard", page_icon="🌐", layout="wide")

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
    "auth_view": "login",
    "theme": "dark"  # Added theme toggle: "dark" or "light"
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

# ================= CSS: THEME SYSTEM (DARK & LIGHT) =================
def inject_auth_css(view_state, theme="dark"):
    if theme == "dark":
        # Dark Mode: Warm Beige outer, Light Grey inner, Deep Graphite text
        colors = {
            "outer_bg": "#F5F5DC",          # Warm Beige outer background
            "inner_box": "#F5F5DC",         # Warm Beige for form side
            "text_primary": "#333333",      # Deep Graphite text
            "text_secondary": "#666666",    # Medium gray text
            "input_border": "#F24B8C",      # Light Rose Red border
            "input_bg": "rgba(230, 230, 230, 0.8)",  # Light background
            "purple": "#F24B8C",            # Light Rose Red button
            "button_hover": "rgba(242, 75, 140, 0.2)"
        }
    else:
        # Light Mode: Warm Beige outer, Warm Beige inner, Deep Graphite text
        colors = {
            "outer_bg": "#F5F5DC",          # Warm Beige outer background
            "inner_box": "#F5F5DC",         # Warm Beige for form side
            "text_primary": "#333333",      # Deep Graphite text
            "text_secondary": "#666666",    # Medium gray text
            "input_border": "#F24B8C",      # Light Rose Red border
            "input_bg": "#ffffff",          # White background
            "purple": "#F24B8C",            # Light Rose Red button
            "button_hover": "#E0115F"       # Darker rose on hover
        }

    css = f"""
    <style>
    /* 1. App Background - Warm Beige */
    .stApp {{ background: #F5F5DC !important; }}
    
    /* 2. Container Centering - White Inner Box */
    .block-container {{
        max-width: 1100px !important;
        width: 90% !important; 
        padding: 0 !important;
        margin: auto !important; 
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        border-radius: 20px;
        background-color: #FFFFFF !important;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
        overflow: hidden;
        min-height: 600px;
        border: none;
        display: flex !important;
    }}
    
    /* 3. Force 50/50 Split */
    [data-testid="stHorizontalBlock"] {{ gap: 0 !important; margin: 0 !important; width: 100% !important; align-items: stretch !important; }}
    
    /* Left Column - Form Side (White Background) */
    [data-testid="column"]:nth-of-type(1) {{
        background: #FFFFFF !important;
        padding: 80px 50px !important;
        width: 50% !important;
        flex: 1 1 50% !important;
        display: flex; flex-direction: column; justify-content: center;
        align-items: center;
        text-align: center !important;
        border-right: 2px solid #F5F5DC !important;
    }}
    
    /* Right Column - Switch Side (White Background) */
    [data-testid="column"]:nth-of-type(2) {{
        background: #FFFFFF !important;
        padding: 80px 50px !important;
        width: 50% !important;
        flex: 1 1 50% !important;
        display: flex; flex-direction: column; justify-content: center;
        align-items: center;
        text-align: center !important;
    }}
    
    /* All divs inside columns */
    [data-testid="column"] > div {{
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
    }}

    /* 4. Form Inputs */
    .stTextInput > div > div > input, .stDateInput > div > div > input {{
        background-color: {colors["input_bg"]} !important;
        color: {colors["text_primary"]} !important; 
        border: 2px solid {colors["input_border"]} !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        transition: all 0.3s ease !important;
        font-size: 15px !important;
    }}
    
    /* Left Column Input Styling - Rose Red borders on white background */
    [data-testid="column"]:nth-of-type(1) .stTextInput > div > div > input,
    [data-testid="column"]:nth-of-type(1) .stDateInput > div > div > input {{
        background-color: #FFFFFF !important;
        color: #333333 !important;
        border: 2px solid #F24B8C !important;
    }}
    .stTextInput > div > div > input:focus {{ 
        border-color: {colors["text_primary"]} !important; 
        background-color: {colors["input_bg"]} !important;
        box-shadow: 0 0 0 3px rgba(75, 144, 255, 0.3) !important; 
        outline: none !important;
    }}
    .stTextInput > div > div > input::placeholder {{ color: {colors["text_secondary"]} !important; opacity: 0.7 !important; }}
    
    /* 5. Primary Button - Blue for left side */
    button[kind="primary"] {{
        background: #4B90FF !important; 
        color: #FFFFFF !important;
        border: none !important; 
        border-radius: 12px !important;
        font-weight: 600 !important; 
        padding: 14px 20px !important; 
        width: 100% !important;
        margin-top: 20px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        font-size: 15px !important;
        cursor: pointer !important;
        box-shadow: 0 4px 15px rgba(75, 144, 255, 0.4) !important;
    }}
    button[kind="primary"]:hover {{
        transform: translateY(-4px) scale(1.02) !important;
        box-shadow: 0 12px 35px rgba(75, 144, 255, 0.7) !important;
    }}
    button[kind="primary"]:active {{
        transform: translateY(-1px) scale(0.99) !important;
    }}
    
    /* 6. Secondary Outline Button - Dark on white background */
    button[kind="secondary"] {{
        background-color: transparent !important; 
        color: #333333 !important;
        border: 2px solid #333333 !important; 
        border-radius: 12px !important;
        font-weight: 600 !important; 
        padding: 12px 18px !important; 
        width: 100% !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        font-size: 14px !important;
        cursor: pointer !important;
    }}
    button[kind="secondary"]:hover {{ 
        background-color: #F5F5DC !important;
        transform: translateY(-3px) !important;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1) !important;
    }}
    button[kind="secondary"]:active {{
        transform: translateY(-1px) !important;
    }}
    
    /* 7. Forgot Password Link */
    button[kind="tertiary"] {{
        color: {colors["text_primary"]} !important; 
        background: transparent !important; 
        border: none !important;
        padding: 0 !important; 
        font-size: 14px !important; 
        font-weight: 500 !important;
        display: flex; 
        justify-content: flex-end; 
        width: 100%; 
        margin-top: -10px;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }}
    button[kind="tertiary"]:hover {{
        opacity: 0.8 !important;
        text-decoration: underline !important;
    }}
    
    /* Typography Global Overrides */
    h1, h2, h3, h4, h5, h6 {{ font-weight: 700 !important; color: {colors["text_primary"]} !important; }}
    p {{ color: {colors["text_secondary"]} !important; }}
    label {{ color: {colors["text_primary"]} !important; }}
    header {{ visibility: hidden; }}
    
    /* Left Column Text Styling - Dark text on white background */
    [data-testid="column"]:nth-of-type(1) h1,
    [data-testid="column"]:nth-of-type(1) h2,
    [data-testid="column"]:nth-of-type(1) h3,
    [data-testid="column"]:nth-of-type(1) h4,
    [data-testid="column"]:nth-of-type(1) h5,
    [data-testid="column"]:nth-of-type(1) h6 {{
        color: #333333 !important;
        text-align: center !important;
    }}
    [data-testid="column"]:nth-of-type(1) p {{
        color: #666666 !important;
        text-align: center !important;
    }}
    
    /* Right Column Text Styling - Dark text on white background */
    [data-testid="column"]:nth-of-type(2) h1,
    [data-testid="column"]:nth-of-type(2) h2,
    [data-testid="column"]:nth-of-type(2) h3,
    [data-testid="column"]:nth-of-type(2) h4,
    [data-testid="column"]:nth-of-type(2) h5,
    [data-testid="column"]:nth-of-type(2) h6 {{
        color: #333333 !important;
        text-align: center !important;
    }}
    [data-testid="column"]:nth-of-type(2) p {{
        color: #666666 !important;
        text-align: center !important;
    }}
    /* Left Column Button Styling */
    [data-testid="column"]:nth-of-type(1) button {{
        width: 80% !important;
        margin: 20px auto !important;
        display: block !important;
    }}
    
    /* Right Column Button Styling - White outline on white background */
    [data-testid="column"]:nth-of-type(2) button[kind="secondary"] {{
        background-color: transparent !important;
        color: #333333 !important;
        border: 2px solid #333333 !important;
    }}
    [data-testid="column"]:nth-of-type(2) button[kind="secondary"]:hover {{
        background-color: #F5F5DC !important;
    }}
    [data-testid="column"]:nth-of-type(1) > div {{
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        text-align: center !important;
        gap: 15px !important;
    }}
    
    /* Remove Streamlit default styles */
    [data-testid="stForm"] {{ padding: 0 !important; }}
    [role="main"] {{ padding-top: 0 !important; }}
    
    /* Responsive Breakpoint */
    @media (max-width: 768px) {{
        [data-testid="stHorizontalBlock"] {{ flex-direction: column !important; }}
        [data-testid="column"]:nth-of-type(1), [data-testid="column"]:nth-of-type(2) {{ 
            width: 100% !important; 
            flex: none !important; 
            min-height: auto !important; 
            padding: 60px 40px !important; 
        }}
        .block-container {{ 
            position: relative; 
            top: auto; 
            left: auto; 
            transform: none; 
            margin: 5vh auto !important; 
            height: auto;
            border-radius: 20px;
        }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ================= THEME COLOR HELPER =================
def get_theme_colors(theme="dark"):
    """Returns color values based on theme"""
    if theme == "dark":
        return {
            "text_primary": "#F5FBFF",      # Arctic Ice text
            "text_secondary": "#e0e0e0",    # Light gray text
            "logo_color": "#9ABDDC",        # Kawaii Sky Blue
            "accent_color": "#9CB7BE",      # Cadet Blue
        }
    else:
        return {
            "text_primary": "#1a1a1a",      # Night black text
            "text_secondary": "#666666",    # Dark gray text
            "logo_color": "#9CB7BE",        # Cadet Blue
            "accent_color": "#9ABDDC",      # Kawaii Sky Blue
        }


# ================= LANDING =================
if not st.session_state.logged_in:
    
    inject_auth_css(st.session_state.auth_view, st.session_state.theme)
    
    col_left, col_right = st.columns(2)

    # --- 1. LOGIN VIEW ---
    if st.session_state.auth_view == "login":
        colors = get_theme_colors(st.session_state.theme)
        
        with col_left: # FORM SIDE
            st.markdown(f'<h2 style="font-weight: 700; text-align: center; margin-bottom: 10px; color: {colors["text_primary"]} !important; font-size: 32px;">Welcome Back</h2>', unsafe_allow_html=True)
            st.markdown(f'<p style="color: #EB4C4C !important; font-size: 15px; text-align: center; margin-bottom: 35px;">Please enter your credentials to log in</p>', unsafe_allow_html=True)
            
            email = st.text_input("Email", placeholder="Email", label_visibility="collapsed", key="l_email")
            pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="l_pwd")
            
            # Right-aligned Forgot Password
            _, c_link = st.columns([2, 1.2])
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

        with col_right: # SWITCH SIDE
            st.markdown(f'<h3 style="font-weight: 500; text-align: center; margin-bottom: 10px; color: {colors["text_primary"]} !important; font-size: 20px;">New to our Platform?</h3>', unsafe_allow_html=True)
            st.markdown(f'<p style="opacity: 0.9; text-align: center; font-size: 15px; margin-bottom: 30px; color: {colors["text_secondary"]} !important;">Create an account to build your vault.</p>', unsafe_allow_html=True)
            
            # Using columns to perfectly center the button in its dedicated area
            _, btn_col, _ = st.columns([1, 1.5, 1])
            with btn_col:
                if st.button("SIGN UP", type="secondary", use_container_width=True):
                    st.session_state.auth_view = "signup"
                    st.rerun()


    # --- 2. SIGN UP VIEW ---
    elif st.session_state.auth_view == "signup":
        colors = get_theme_colors(st.session_state.theme)
        
        with col_left: # SWITCH SIDE
            st.markdown(f'<h3 style="font-weight: 500; text-align: center; margin-bottom: 10px; color: {colors["text_primary"]} !important; font-size: 20px;">Already have an account?</h3>', unsafe_allow_html=True)
            st.markdown(f'<p style="opacity: 0.9; text-align: center; font-size: 15px; margin-bottom: 30px; color: {colors["text_secondary"]} !important;">Sign in to access your vault.</p>', unsafe_allow_html=True)
            
            # Using columns to perfectly center the buttons
            _, btn_col, _ = st.columns([1, 1.5, 1])
            with btn_col:
                if st.button("SIGN IN", type="secondary", use_container_width=True):
                    st.session_state.auth_view = "login"
                    st.rerun()

        with col_right: # FORM SIDE
            st.markdown(f'<h2 style="font-weight: 700; text-align: center; margin-bottom: 10px; color: {colors["text_primary"]} !important; font-size: 32px;">Sign Up</h2>', unsafe_allow_html=True)
            st.markdown(f'<p style="color: {colors["text_secondary"]} !important; font-size: 15px; text-align: center; margin-bottom: 35px;">Please provide your information to sign up.</p>', unsafe_allow_html=True)
            
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
        colors = get_theme_colors(st.session_state.theme)
        
        with col_left: # SWITCH SIDE

            st.markdown(f'<h3 style="font-weight: 500; font-style: italic; text-align: center; line-height: 1.5; margin-bottom: 30px; color: {colors["text_primary"]} !important; font-size: 18px;">"Your own digital<br>bibliothecas for<br>borrowing and<br>watching videos"</h3>', unsafe_allow_html=True)
            
            # Using columns to perfectly center the back button
            _, btn_col, _ = st.columns([1, 1.5, 1])
            with btn_col:
                if st.button("⬅ Back to Log In", type="secondary", use_container_width=True):
                    st.session_state.reset_step = 0
                    st.session_state.auth_view = "login"
                    st.rerun()

        with col_right: # FORM SIDE
            st.markdown(f'<h2 style="font-weight: 700; text-align: center; margin-bottom: 10px; color: {colors["text_primary"]} !important; font-size: 32px;">Forgot Password</h2>', unsafe_allow_html=True)
            
            if st.session_state.reset_step == 0:
                st.markdown(f'<p style="color: {colors["text_secondary"]} !important; font-size: 15px; text-align: center; margin-bottom: 35px;">Please enter your registered email</p>', unsafe_allow_html=True)
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
                st.markdown(f'<p style="color: {colors["text_secondary"]} !important; font-size: 15px; text-align: center; margin-bottom: 35px;">Enter the 6-digit code sent to your email</p>', unsafe_allow_html=True)
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


# ================= DASHBOARD (LIQUID GLASS) =================
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