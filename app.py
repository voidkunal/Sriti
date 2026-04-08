import streamlit as st
import streamlit.components.v1 as components
from pymongo import MongoClient
from bson.objectid import ObjectId
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
st.set_page_config(page_title="voidememo  Vault", page_icon="🌐", layout="wide", initial_sidebar_state="expanded")

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
        msg['Subject'] = "voidememo - Password Reset"
        body = f"Hello,\n\nYou have requested to reset your password. Your 6-digit code is: {otp}\n\nIf you did not request this, please ignore this email."
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

@st.dialog("⚠️ Confirm Deletion")
def delete_folder_dialog(folder_id, folder_name):
    st.write(f"Are you sure you want to completely delete the album **{folder_name}** and everything inside it?")
    c1, c2 = st.columns(2)
    if c1.button("Yes, Delete It", type="primary", use_container_width=True):
        delete_folder_tree(folder_id)
        st.query_params["folder"] = "root"
        st.rerun()
    if c2.button("No, Cancel", use_container_width=True):
        st.rerun()

@st.dialog("✏️ Rename Album")
def rename_folder_dialog(folder_id, current_name):
    new_name = st.text_input("Enter new album name:", value=current_name)
    c1, c2 = st.columns(2)
    if c1.button("Save Changes", type="primary", use_container_width=True):
        if new_name.strip() and new_name.strip() != current_name:
            folders_col.update_one({"_id": folder_id}, {"$set": {"folder_name": new_name.strip()}})
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()

@st.dialog("⚠️ Confirm Deletion")
def delete_file_dialog(file_id, public_id, resource_type):
    st.write("Are you sure you want to delete this media?")
    c1, c2 = st.columns(2)
    if c1.button("Yes, Delete It", type="primary", use_container_width=True):
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        files_col.delete_one({"_id": file_id})
        st.rerun()
    if c2.button("No, Cancel", use_container_width=True):
        st.rerun()

@st.dialog("⏳ Reaction Locked")
def locked_reaction_dialog(remaining_seconds):
    hours, remainder = divmod(int(remaining_seconds), 3600)
    minutes, _ = divmod(remainder, 60)
    st.warning("Emoji changes are locked for 24 hours after a reaction.")
    st.info(f"Time remaining: **{hours} hours and {minutes} minutes**")
    if st.button("Got it", use_container_width=True):
        st.rerun()

# ================= NATIVE GESTURE ROUTING SYSTEM =================
def get_nav_link(page=None, view=None, tab=None, folder=None, story_idx=None):
    params = []
    if page is not None: params.append(f"page={page}")
    if view is not None: params.append(f"view={view}")
    if tab is not None: params.append(f"tab={tab}")
    if folder is not None: params.append(f"folder={folder}")
    if story_idx is not None: params.append(f"story_idx={story_idx}")
    if "session" in st.query_params:
        params.append(f"session={st.query_params['session']}")
    return "?" + "&".join(params)

app_page = st.query_params.get("page", "landing")
auth_view = st.query_params.get("view", "login")
active_tab = st.query_params.get("tab", "drive")
active_folder = st.query_params.get("folder", "root")

defaults = {
    "logged_in": False, "username": "", "reset_step": 0, "reset_email": "",
    "uploader_key": 0, "folder_key": 0,
    "story_sample": [], "story_timestamp": 0 # 5-minute cache
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

# ================= TRUE STORY POPUP MODAL =================
@st.dialog("✨ Memory Highlight", width="large")
def render_story_dialog(idx):
    sample = st.session_state.story_sample
    if not sample or idx >= len(sample):
        if "story_idx" in st.query_params: del st.query_params["story_idx"]
        st.rerun()
        
    current_story = sample[idx]
    
    st.markdown("""
    <style>
    .story-progress-bar { width: 100%; height: 4px; background: rgba(150,150,150,0.3); border-radius: 2px; margin-bottom: 15px; overflow: hidden; }
    .story-progress-fill { height: 100%; background: var(--accent); width: 0%; animation: progress-fill 15s linear forwards; }
    @keyframes progress-fill { to { width: 100%; } }
    </style>
    <div class="story-progress-bar"><div class="story-progress-fill"></div></div>
    """, unsafe_allow_html=True)
    
    if current_story["resource_type"] == "image":
        st.image(current_story["url"], use_container_width=True)
    else:
        st.video(current_story["url"], autoplay=True)
        
    c1, c2 = st.columns(2)
    next_idx = idx + 1
    
    if next_idx < len(sample):
        next_url = get_nav_link("app", tab="drive", folder="root", story_idx=next_idx)
        btn_txt = "Next ⏭️"
    else:
        next_url = get_nav_link("app", tab="drive", folder="root")
        btn_txt = "Finish ✓"
        
    if c1.button(btn_txt, use_container_width=True):
        if next_idx < len(sample): st.query_params["story_idx"] = next_idx
        else: del st.query_params["story_idx"]
        st.rerun()
        
    if c2.button("Close ✕", use_container_width=True):
        if "story_idx" in st.query_params: del st.query_params["story_idx"]
        st.rerun()
        
    components.html(f"""
    <script>
    setTimeout(function() {{
        window.parent.location.href = "{next_url}";
    }}, 15000);
    </script>
    """, height=0)


# ---------------- AUTH LOGIC ----------------
def register(email, password, first_name, last_name, birthday):
    if users_col.find_one({"email": email}): return False
    username = email.split('@')[0]
    users_col.insert_one({
        "username": username, "first_name": first_name, "last_name": last_name,
        "birthday": str(birthday), "email": email, "password": hash_password(password),
        "profile_photo": "", "bio": "", "session_token": "", "reset_otp": "" 
    })
    folders_col.insert_one({"username": username, "folder_name": "root", "parent_id": None})
    return username

def login(email, password):
    user = users_col.find_one({"email": email})
    if user and user["password"] == hash_password(password): return user["username"]
    return False

# ================= CORE CSS: AUTO LIGHT/DARK SYSTEM =================
def inject_global_css():
    css = """
    <style>
    :root {
        --bg-app: #f2f2f7;           
        --bg-card: #ffffff;          
        --bg-sidebar: #f2f2f7;       
        --bg-input: #ffffff;
        --text-primary: #000000;     
        --text-secondary: #8e8e93;   
        --border: #d1d1d6;
        --accent: #007aff;           
        --btn-hover: #e5e5ea;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-app: #000000;           
            --bg-card: #1c1c1e;          
            --bg-sidebar: #000000;       
            --bg-input: #1c1c1e;         
            --text-primary: #ffffff;     
            --text-secondary: #8e8e93;   
            --border: #38383a;           
            --accent: #0a84ff;           
            --btn-hover: #2c2c2e;
        }
    }

    .stApp { background-color: var(--bg-app) !important; color: var(--text-primary) !important; }
    p, h1, h2, h3, h4, h5, h6, span, label, li { color: var(--text-primary) !important; transition: color 0.3s ease; }
    
    #MainMenu { visibility: hidden; }
    .stDeployButton { display: none !important; }
    header[data-testid="stHeader"] { background-color: transparent !important; }
    
    .title-text { color: var(--text-primary) !important; font-weight: 800; font-size: 32px; text-align: center; margin-bottom: 5px; }
    .sub-text { color: var(--text-secondary) !important; font-size: 15px; text-align: center; margin-bottom: 30px; }
    .brand-logo { font-size: 24px; font-weight: 800; color: var(--accent) !important; letter-spacing: 0.5px; text-decoration: none; }
    .muted-text { color: var(--text-secondary) !important; }

    .auth-container, .content-card {
        max-width: 480px !important; width: 90% !important; 
        background-color: var(--bg-card) !important;
        padding: 50px 40px !important; border-radius: 20px !important;
        border: 1px solid var(--border) !important; margin: 8vh auto !important; 
    }
    .content-card { max-width: 800px !important; }

    .stTextInput div[data-baseweb="input"], .stDateInput div[data-baseweb="input"], .stTextArea div[data-baseweb="textarea"] {
        background-color: var(--bg-input) !important; border: 1.5px solid var(--border) !important; border-radius: 12px !important; 
    }
    .stTextInput input, .stDateInput input, .stTextArea textarea { 
        background-color: transparent !important; color: var(--text-primary) !important; padding: 14px 16px !important; font-size: 15px !important; 
    }
    ::placeholder { color: var(--text-secondary) !important; opacity: 1 !important; font-weight: 400 !important; }
    .stTextInput div[data-baseweb="input"]:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.2) !important; }

    .stButton > button[kind="primary"] { 
        background-color: var(--accent) !important; color: #ffffff !important; border: none !important; border-radius: 12px !important; 
        padding: 14px 24px !important; font-weight: 600 !important; width: 100% !important; margin-top: 10px !important; 
    }
    .native-link { color: var(--accent) !important; text-decoration: none; font-weight: 600; }
    .native-link:hover { text-decoration: underline; }
    
    .sidebar-link {
        display: block; background: transparent; color: var(--text-primary) !important;
        text-decoration: none; font-weight: 500; font-size: 15px;
        border-radius: 8px; padding: 10px 14px; margin-bottom: 4px; transition: background 0.2s;
    }
    .sidebar-link:hover { background: var(--btn-hover); text-decoration: none;}

    .top-nav { display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; }
    .nav-links { display: flex; gap: 20px; align-items: center; }
    .nav-links a { color: var(--text-primary) !important; text-decoration: none; font-weight: 500; font-size: 15px; }
    .nav-links a:hover { color: var(--accent) !important; }

    /* DASHBOARD */
    [data-testid="stSidebar"] { background-color: var(--bg-sidebar) !important; border-right: 1px solid var(--border) !important; padding-top: 1rem; }
    .dashboard-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;}
    .dashboard-title { font-size: 32px; font-weight: 800; color: var(--text-primary); }
    
    /* Dynamic Story Section */
    .story-wrapper { display: flex; overflow-x: auto; gap: 15px; padding: 10px 0 20px 0; margin-bottom: 10px; }
    .story-wrapper::-webkit-scrollbar { display: none; }
    .story-link { text-decoration: none; display: inline-block; }
    .story-item { display: flex; flex-direction: column; align-items: center; gap: 8px; min-width: 85px; cursor: pointer; transition: transform 0.2s; }
    .story-item:hover { transform: scale(1.05); }
    .story-ring { width: 76px; height: 76px; border-radius: 50%; padding: 3px; display: flex; align-items: center; justify-content: center; }
    .story-inner { width: 100%; height: 100%; border-radius: 50%; border: 3px solid var(--bg-app); overflow: hidden; background: var(--bg-card); display: flex; align-items: center; justify-content: center; font-size: 24px; }
    .story-inner img, .story-inner video { width: 100%; height: 100%; object-fit: cover; }
    .story-label { font-size: 12px; font-weight: 600; color: var(--text-primary); text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 80px;}

    .album-link { text-decoration: none; display: block; }
    
    /* MEDIA GRID & ABSOLUTE OVERLAYS */
    .media-container-wrapper { position: relative; margin-bottom: 15px; }
    
    .square-media {
        width: 100%; aspect-ratio: 1/1; overflow: hidden;
        border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        background: var(--bg-card); border: 1px solid var(--border);
    }
    .square-media img, .square-media video { width: 100%; height: 100%; object-fit: cover; }
    
    /* OVERLAID 3-DOTS MENU (Now positioned flawlessly inside the image) */
    .image-actions-overlay {
        position: absolute; top: 10px; right: 10px; z-index: 20;
    }
    .image-actions-overlay [data-testid="stPopover"] > button {
        background-color: rgba(0, 0, 0, 0.5) !important; color: white !important;
        border: none !important; border-radius: 50% !important;
        width: 32px !important; height: 32px !important;
        display: flex; align-items: center; justify-content: center; line-height: 0 !important;
        padding: 0 !important; font-size: 18px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    }
    .image-actions-overlay [data-testid="stPopover"] > button:hover { background-color: rgba(0, 0, 0, 0.8) !important; }
    
    [data-testid="stFileUploader"] > div { background-color: var(--bg-card) !important; border: 1px dashed var(--border) !important; border-radius: 16px !important; padding: 20px !important; }
    .profile-header-widget { display: flex; align-items: center; gap: 12px; background: var(--bg-card); padding: 6px 16px 6px 6px; border-radius: 50px; border: 1px solid var(--border); box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    .profile-header-widget img { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; }
    .profile-header-widget span { font-weight: 600; font-size: 14px; color: var(--text-primary); }

    .custom-footer { margin-top: 50px; padding: 20px; text-align: center; border-top: 1px solid var(--border); color: var(--text-secondary); font-size: 13px; }

    @media (max-width: 768px) {
        .auth-container, .content-card { border: none !important; border-radius: 0 !important; padding: 30px 20px !important; margin: 0 !important; width: 100% !important; max-width: 100% !important;}
        .top-nav { padding: 15px 20px; }
        .block-container { padding-top: 3rem !important; } 
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# Catch Story Dialog Trigger First
if "story_idx" in st.query_params and st.session_state.logged_in:
    inject_global_css()
    render_story_dialog(int(st.query_params["story_idx"]))


# ================= PUBLIC ROUTING (LOGGED OUT) =================
elif not st.session_state.logged_in:
    inject_global_css()
    
    if app_page not in ["landing", "policy", "contact", "auth"]:
        st.query_params["page"] = "landing"
        st.rerun()
    
    if app_page != "auth":
        st.markdown(f"""
        <div class="top-nav">
            <a href="{get_nav_link('landing')}" target="_self" class="brand-logo">voidememo</a>
            <div class="nav-links">
                <a href="{get_nav_link('landing')}" target="_self">Home</a>
                <a href="{get_nav_link('policy')}" target="_self">Policy</a>
                <a href="{get_nav_link('auth', 'login')}" target="_self" style="color: var(--accent) !important;">Log In</a>
            </div>
        </div>
        <hr style='margin: 0; border-color: var(--border);'>
        """, unsafe_allow_html=True)

        if app_page == "landing":
            st.markdown('<div class="title-text" style="font-size: 3.5rem; margin-top: 4rem;">Secure Your Memories</div>', unsafe_allow_html=True)
            st.markdown('<div class="sub-text" style="font-size: 1.25rem; max-width: 600px; margin: 0 auto 3rem auto;">Your personal digital bibliotheca. Access, organize, and protect your media with absolute privacy.</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align: center;"><a href="{get_nav_link("auth", "signup")}" target="_self" style="background: var(--accent); color: #ffffff; padding: 14px 30px; border-radius: 50px; text-decoration: none; font-weight: 600; font-size: 16px;">Create Free Vault</a></div>', unsafe_allow_html=True)
            st.write("<br><br><br><h3 style='text-align: center;'>Sample Vault Gallery</h3><br>", unsafe_allow_html=True)
            img_c1, img_c2, img_c3 = st.columns(3)
            with img_c1: st.image("https://images.unsplash.com/photo-1516541196182-6bdb0516ed27?auto=format&fit=crop&w=600&q=80", use_container_width=True)
            with img_c2: st.image("https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=600&q=80", use_container_width=True)
            with img_c3: st.image("https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=600&q=80", use_container_width=True)
            
        elif app_page == "policy":
            st.markdown("""
            <div class="content-card">
                <h2>Privacy Policy & Permissions</h2>
                <p class="muted-text">Last Updated: April 2026</p>
                <hr style='border-color: var(--border);'>
                <h4>1. Data Collection</h4>
                <p>We collect minimal information necessary to provide you with secure access to your digital bibliotheca.</p>
                <h4>2. Media Storage Permissions</h4>
                <p>By uploading files to voidememo, you grant us the permission to securely host and deliver this content back to you.</p>
            </div>
            """, unsafe_allow_html=True)
            
        elif app_page == "contact":
            st.markdown("""
            <div class="content-card" style="text-align: center;">
                <h2>Contact Support</h2>
                <p>Have questions about your vault or our privacy policies? We are here to help.</p><br>
                <h4>Email Support</h4>
                <p><a href="mailto:support@voidememo.com" class="native-link">support@voidememo.com</a></p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div class="custom-footer">© 2026 voidememo. All rights reserved.</div>', unsafe_allow_html=True)

    # --- AUTHENTICATION FLOW ---
    else:
        if auth_view not in ["login", "signup", "forgot"]:
            st.query_params["view"] = "login"; st.rerun()

        st.markdown('<div class="auth-container">', unsafe_allow_html=True)
        if auth_view == "login":
            st.markdown('<div class="title-text">Welcome Back</div><div class="sub-text">Please enter your credentials to log in</div>', unsafe_allow_html=True)
            email = st.text_input("Email", placeholder="Email", label_visibility="collapsed", key="l_email")
            pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="l_pwd")
            st.markdown(f'<div style="text-align: right; margin-top: -10px; margin-bottom: 15px;"><a href="{get_nav_link("auth", "forgot")}" target="_self" class="muted-text" style="font-size: 13px; text-decoration: none; font-weight: 500;">Forgot Password?</a></div>', unsafe_allow_html=True)
            
            if st.button("Sign In", type="primary", use_container_width=True):
                if not email or not pwd: st.error("Please enter email and password.")
                else:
                    result = login(email, pwd)
                    if result:
                        token = str(uuid.uuid4())
                        users_col.update_one({"username": result}, {"$set": {"session_token": token}})
                        st.session_state.logged_in = True; st.session_state.username = result
                        st.query_params["session"] = token; st.query_params["page"] = "app"; st.query_params["tab"] = "drive"; st.query_params["folder"] = "root"
                        if "view" in st.query_params: del st.query_params["view"]
                        st.rerun()
                    else: st.error("Invalid credentials")
            st.markdown(f'<div style="text-align: center; margin-top: 25px;"><span class="muted-text">New to our platform?</span> <a href="{get_nav_link("auth", "signup")}" target="_self" class="native-link">Sign Up</a></div>', unsafe_allow_html=True)

        elif auth_view == "signup":
            st.markdown('<div class="title-text">Sign Up</div><div class="sub-text">Create an account to build your vault.</div>', unsafe_allow_html=True)
            fname = st.text_input("First Name", placeholder="First Name", label_visibility="collapsed", key="s_fname")
            lname = st.text_input("Last Name", placeholder="Last Name", label_visibility="collapsed", key="s_lname")
            bday = st.date_input("Birthday", value=datetime.date(2000, 1, 1), min_value=datetime.date(1900, 1, 1), label_visibility="collapsed")
            s_email = st.text_input("Email", placeholder="you@example.com", label_visibility="collapsed", key="s_email")
            s_pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="s_pwd")
            
            if st.button("Sign Up", type="primary", use_container_width=True):
                if not s_email or not s_pwd or not fname: st.error("Please fill all required fields.")
                else:
                    result = register(s_email, s_pwd, fname, lname, bday)
                    if result:
                        token = str(uuid.uuid4())
                        users_col.update_one({"username": result}, {"$set": {"session_token": token}})
                        st.session_state.logged_in = True; st.session_state.username = result
                        st.query_params["session"] = token; st.query_params["page"] = "app"; st.query_params["tab"] = "drive"; st.query_params["folder"] = "root"
                        if "view" in st.query_params: del st.query_params["view"]
                        st.rerun()
                    else: st.error("Email already registered.")
            st.markdown(f'<div style="text-align: center; margin-top: 25px;"><span class="muted-text">Already have an account?</span> <a href="{get_nav_link("auth", "login")}" target="_self" class="native-link">Sign In</a></div>', unsafe_allow_html=True)

        elif auth_view == "forgot":
            st.markdown('<div class="title-text">Forgot Password</div>', unsafe_allow_html=True)
            if st.session_state.reset_step == 0:
                st.markdown('<div class="sub-text">Please enter your registered email</div>', unsafe_allow_html=True)
                f_email = st.text_input("Email", placeholder="Email", label_visibility="collapsed", key="f_email")
                if st.button("Reset Password", type="primary", use_container_width=True):
                    if f_email:
                        user = users_col.find_one({"email": f_email})
                        if user:
                            with st.spinner("Sending OTP..."):
                                otp = str(random.randint(100000, 999999))
                                users_col.update_one({"email": f_email}, {"$set": {"reset_otp": otp}})
                                if send_otp_email(f_email, otp):
                                    st.session_state.reset_step = 1; st.session_state.reset_email = f_email; st.rerun()
                        else: st.error("No account found with that email.")
                        
            elif st.session_state.reset_step == 1:
                st.markdown('<div class="sub-text">Enter the 6-digit code sent to your email</div>', unsafe_allow_html=True)
                st.success(f"OTP sent to {st.session_state.reset_email}")
                entered_otp = st.text_input("Enter 6-Digit OTP", placeholder="123456", label_visibility="collapsed", key="entered_otp")
                new_pwd = st.text_input("Enter New Password", type="password", placeholder="New Password", label_visibility="collapsed", key="new_pwd")
                if st.button("Confirm Reset", type="primary", use_container_width=True):
                    if len(new_pwd) < 6: st.error("Password must be at least 6 characters.")
                    else:
                        user = users_col.find_one({"email": st.session_state.reset_email})
                        if user and user.get("reset_otp") == entered_otp:
                            users_col.update_one({"email": st.session_state.reset_email}, {"$set": {"password": hash_password(new_pwd), "reset_otp": ""}})
                            st.success("Password updated!"); time.sleep(1.5)
                            st.session_state.reset_step = 0; st.session_state.reset_email = ""
                            st.query_params["view"] = "login"; st.rerun()
                        else: st.error("Invalid token!")
            st.markdown(f'<div style="text-align: center; margin-top: 25px;"><span class="muted-text">Remembered your password?</span> <a href="{get_nav_link("auth", "login")}" target="_self" class="native-link">Log In</a></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ================= DASHBOARD APP (LOGGED IN) =================
elif active_tab in ["drive", "profile"]:
    inject_global_css()
    st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { max-width: 100% !important; padding-top: 1rem !important; }</style>", unsafe_allow_html=True)

    user_data = users_col.find_one({"username": st.session_state.username})
    
    # ---------------- ROOT RESOLUTION (FIXED OBJECTID PARSING) ----------------
    root_folder = folders_col.find_one({"username": st.session_state.username, "parent_id": None})
    if active_folder == "root" and root_folder: actual_folder_id = root_folder["_id"]
    else:
        try: actual_folder_id = ObjectId(active_folder)
        except: actual_folder_id = root_folder["_id"] if root_folder else None

    # --- 5-MINUTE STORY CACHE LOGIC ---
    current_time = time.time()
    if current_time - st.session_state.story_timestamp > 300: 
        all_user_media = list(files_col.find({"username": st.session_state.username}))
        if all_user_media:
            random.shuffle(all_user_media)
            st.session_state.story_sample = all_user_media[:6]
        st.session_state.story_timestamp = current_time

    # --- SIDEBAR NAV ---
    st.sidebar.markdown('<div style="padding: 10px 10px 20px 10px;"><span style="font-weight: 800; font-size: 20px; color: var(--accent);">voidememo</span></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="muted-text" style="font-size: 12px; font-weight: 600; padding: 10px; margin-top: 10px;">Library</div>', unsafe_allow_html=True)
    
    st.sidebar.markdown(f'<a href="{get_nav_link("app", tab="drive", folder="root")}" target="_self" class="sidebar-link">📸 Dashboard</a>', unsafe_allow_html=True)
    st.sidebar.markdown(f'<a href="{get_nav_link("app", tab="profile")}" target="_self" class="sidebar-link">⚙️ Settings</a>', unsafe_allow_html=True)
    
    st.sidebar.markdown('<div class="muted-text" style="font-size: 12px; font-weight: 600; padding: 10px; margin-top: 20px;">Albums</div>', unsafe_allow_html=True)
    all_folders = list(folders_col.find({"username": st.session_state.username}))
    for f in all_folders:
        if f["folder_name"] != "root":
            st.sidebar.markdown(f'<a href="{get_nav_link("app", tab="drive", folder=str(f["_id"]))}" target="_self" class="sidebar-link">📁 {f["folder_name"]}</a>', unsafe_allow_html=True)
    
    st.sidebar.write("<br><br><br>", unsafe_allow_html=True)
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        users_col.update_one({"username": st.session_state.username}, {"$set": {"session_token": ""}})
        if "session" in st.query_params: del st.query_params["session"]
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.query_params["page"] = "landing"
        if "tab" in st.query_params: del st.query_params["tab"]
        if "folder" in st.query_params: del st.query_params["folder"]
        st.rerun()

    # ================= MAIN AREA (DRIVE) =================
    if active_tab == "drive":
        current = folders_col.find_one({"_id": actual_folder_id})
        is_root = current is None or current.get("parent_id") is None

        # --- HEADER ---
        prof_pic = user_data.get("profile_photo") or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
        display_name = user_data.get("first_name", st.session_state.username)
        
        c_title, c_prof = st.columns([4, 1])
        with c_title: st.markdown(f'<div class="dashboard-title">{"Albums" if is_root else current["folder_name"]}</div>', unsafe_allow_html=True)
        with c_prof: st.markdown(f'<div style="display: flex; justify-content: flex-end;"><div class="profile-header-widget"><img src="{prof_pic}"><span>{display_name}</span></div></div>', unsafe_allow_html=True)

        # --- DYNAMIC STORIES ---
        if is_root and st.session_state.story_sample:
            story_html = '<div class="story-wrapper">'
            colors = ["linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%)", "var(--border)", "var(--accent)", "#34d399"]
            
            for idx, media in enumerate(st.session_state.story_sample):
                c = colors[idx % len(colors)]
                label = "Highlights" if idx == 0 else f"Memory {idx+1}"
                
                thumb_html = f'<img src="{media["url"]}">'
                if media.get("resource_type") == "video":
                    vid_thumb = media["url"].replace(".mp4", ".jpg").replace(".webm", ".jpg").replace(".mov", ".jpg")
                    thumb_html = f'<img src="{vid_thumb}" onerror="this.src=\'https://cdn-icons-png.flaticon.com/512/2985/2985655.png\'">'
                
                story_html += f'<a href="{get_nav_link("app", tab="drive", folder="root", story_idx=idx)}" target="_self" class="story-link"><div class="story-item"><div class="story-ring" style="background: {c};"><div class="story-inner">{thumb_html}</div></div><div class="story-label">{label}</div></div></a>'
            
            story_html += '</div>'
            st.markdown(story_html, unsafe_allow_html=True)
            st.write("<br>", unsafe_allow_html=True)

        # --- INSIDE FOLDER MENU ---
        if not is_root:
            menu_c1, menu_c2 = st.columns([5, 1])
            with menu_c1:
                parent_id = current.get("parent_id")
                target_back = str(parent_id) if parent_id else "root"
                st.markdown(f'<a href="{get_nav_link("app", tab="drive", folder=target_back)}" target="_self" style="display:inline-block; padding: 8px 16px; border: 1.5px solid var(--border); border-radius: 8px; color: var(--text-primary); text-decoration: none; font-weight: 600;">⬅ Back to Albums</a>', unsafe_allow_html=True)
            with menu_c2:
                with st.popover("⋮ Options", use_container_width=True):
                    st.markdown("**Album Settings**")
                    if st.button("✏️ Rename Album", key=f"edit_{current['_id']}", use_container_width=True): rename_folder_dialog(current["_id"], current["folder_name"])
                    if st.button("🗑 Delete Album", key=f"del_fold_{current['_id']}", use_container_width=True): delete_folder_dialog(current["_id"], current["folder_name"])
                    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                    st.markdown("**Add Content**")
                    uploaded_files = st.file_uploader("Upload Media", accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}", label_visibility="collapsed")
                    if uploaded_files:
                        if st.button("Sync Files", type="primary", use_container_width=True):
                            with st.spinner("Syncing to cloud..."):
                                for file in uploaded_files:
                                    r_type = "video" if file.type.startswith("video") else "image"
                                    file_size_mb = file.size / (1024 * 1024)
                                    try:
                                        res = cloudinary.uploader.upload_large(file, resource_type=r_type, chunk_size=20000000) if file_size_mb > 50 else cloudinary.uploader.upload(file, resource_type=r_type)
                                        files_col.insert_one({"username": st.session_state.username, "folder_id": current["_id"], "filename": file.name, "url": res["secure_url"], "public_id": res["public_id"], "resource_type": r_type, "tag": "", "tag_time": 0})
                                    except Exception as e: st.error(f"Failed to upload {file.name}.")
                            st.session_state.uploader_key += 1; st.rerun()

        # --- CREATE NEW ALBUM (Only in Root) ---
        if is_root:
            with st.expander("➕ Create New Album"):
                new_folder = st.text_input("New Album", placeholder="Album Name...", label_visibility="collapsed", key=f"folder_input_{st.session_state.folder_key}")
                if st.button("Create Album", type="primary"):
                    if new_folder:
                        folders_col.insert_one({"username": st.session_state.username, "folder_name": new_folder, "parent_id": actual_folder_id, "cover_photo": ""})
                        st.session_state.folder_key += 1; st.rerun()
            st.write("<br>", unsafe_allow_html=True)

        # --- CONTENT GRID (ALBUMS & MEDIA) ---
        folders = list(folders_col.find({"username": st.session_state.username, "parent_id": actual_folder_id}))
        files = list(files_col.find({"username": st.session_state.username, "folder_id": actual_folder_id}))
        
        if not folders and not files:
            st.markdown('<p class="muted-text" style="text-align:center; margin-top: 50px;">This album is empty.</p>', unsafe_allow_html=True)

        # --- PERFECTED ALBUM COVERS ---
        if folders:
            f_cols = st.columns(4)
            for i, folder in enumerate(folders):
                with f_cols[i % 4]:
                    cover = folder.get("cover_photo")
                    folder_url = get_nav_link("app", tab="drive", folder=str(folder["_id"]))
                    
                    if cover:
                        st.markdown(f"""
                        <a href="{folder_url}" target="_self" class="album-link">
                            <div style="margin-bottom: 15px;">
                                <div style="width: 100%; aspect-ratio: 1/1; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid var(--border); margin-bottom: 8px;">
                                    <img src="{cover}" style="width: 100%; height: 100%; object-fit: cover;">
                                </div>
                                <div style="font-weight: 600; font-size: 15px; color: var(--text-primary); text-align: left; padding-left: 4px;">{folder['folder_name']}</div>
                            </div>
                        </a>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <a href="{folder_url}" target="_self" class="album-link">
                            <div style="margin-bottom: 15px;">
                                <div style="width: 100%; aspect-ratio: 1/1; border-radius: 12px; background-color: var(--bg-card); border: 1px solid var(--border); display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 8px; transition: transform 0.2s ease;">
                                    <div style="font-size: 40px;">📁</div>
                                </div>
                                <div style="font-weight: 600; font-size: 15px; color: var(--text-primary); text-align: left; padding-left: 4px;">{folder['folder_name']}</div>
                            </div>
                        </a>
                        """, unsafe_allow_html=True)

        if files:
            st.write("<br>", unsafe_allow_html=True)
            img_cols = st.columns(4)
            for i, file in enumerate(files):
                with img_cols[i % 4]:
                    st.markdown('<div class="media-container-wrapper">', unsafe_allow_html=True)
                    
                    # Emoji Badge
                    emoji_badge = f'<div style="position:absolute; top:8px; left:8px; font-size:20px; z-index:10; background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(5px); padding: 4px 8px; border-radius: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">{file["tag"]}</div>' if file.get("tag") else ""
                    
                    # Media Renderer
                    if file["resource_type"] == "image":
                        st.markdown(f'<div class="square-media">{emoji_badge}<img src="{file["url"]}"></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="square-media">{emoji_badge}<video src="{file["url"]}" controls></video></div>', unsafe_allow_html=True)

                    # --- OVERLAID 3-DOTS MENU ---
                    st.markdown('<div class="image-actions-overlay">', unsafe_allow_html=True)
                    with st.popover("⋮"):
                        st.markdown("**Actions**")
                        st.markdown(f'<a href="{file["url"]}" download target="_blank" style="display:block; padding: 8px 16px; border: 1.5px solid var(--border); border-radius: 8px; color: var(--text-primary); text-decoration: none; text-align: center; font-weight: 600; margin-bottom: 5px;">⬇️ Download</a>', unsafe_allow_html=True)
                        
                        if not is_root:
                            if st.button("🖼️ Set Cover", key=f"cov_{file['_id']}", use_container_width=True):
                                cover_url = file["url"]
                                if file["resource_type"] == "video":
                                    cover_url = file["url"].replace(".mp4", ".jpg").replace(".webm", ".jpg").replace(".mov", ".jpg")
                                folders_col.update_one({"_id": actual_folder_id}, {"$set": {"cover_photo": cover_url}})
                                st.rerun()
                        if st.button("🗑️ Delete", key=f"del_{file['_id']}", use_container_width=True): 
                            delete_file_dialog(file["_id"], file["public_id"], file["resource_type"])
                        
                        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                        st.markdown("**React**")
                        
                        # --- EMOJI LOCKING ENGINE ---
                        time_elapsed = time.time() - file.get("tag_time", 0)
                        is_locked = bool(file.get("tag")) and (time_elapsed < 86400) 
                        
                        if is_locked:
                            if st.button(f"🔒 Locked ({file['tag']})", key=f"lock_{file['_id']}", use_container_width=True):
                                locked_reaction_dialog(86400 - time_elapsed)
                        else:
                            e_cols = st.columns(4)
                            for e_idx, em in enumerate(["🥰", "❤️", "🔥", "😂", "👍", "🎉", "✨", "🥺"]):
                                if e_cols[e_idx % 4].button(em, key=f"em_{file['_id']}_{e_idx}"):
                                    files_col.update_one({"_id": file["_id"]}, {"$set": {"tag": em, "tag_time": time.time()}})
                                    st.rerun()
                    st.markdown('</div></div>', unsafe_allow_html=True)
                    
        st.markdown('<div class="custom-footer">© 2026 voidememo. All rights reserved.</div>', unsafe_allow_html=True)

    # ================= PROFILE (EXPANDED SETTINGS) =================
    elif active_tab == "profile":
        st.markdown('<div class="dashboard-title" style="margin-bottom: 20px;">Settings</div>', unsafe_allow_html=True)
        
        c1, c2 = st.columns([1.5, 1], gap="large")
        
        with c1:
            st.markdown("<div class='content-card' style='margin: 0; max-width: 100% !important;'>", unsafe_allow_html=True)
            st.markdown("### Profile Settings")
            new_username = st.text_input("Username", value=user_data.get("username", ""))
            new_email = st.text_input("Email", value=user_data.get("email", ""))
            bio = st.text_area("Bio", value=user_data.get("bio", ""))
            pic = st.file_uploader("Profile Photo", key="profile_pic_upload")
            
            if st.button("Save Changes", type="primary"):
                updates = {"bio": bio, "email": new_email}
                if pic:
                    res = cloudinary.uploader.upload(pic)
                    updates["profile_photo"] = res["secure_url"]
                    
                if new_username != st.session_state.username:
                    if users_col.find_one({"username": new_username}):
                        st.error("Username already taken.")
                    else:
                        updates["username"] = new_username
                        users_col.update_one({"username": st.session_state.username}, {"$set": updates})
                        folders_col.update_many({"username": st.session_state.username}, {"$set": {"username": new_username}})
                        files_col.update_many({"username": st.session_state.username}, {"$set": {"username": new_username}})
                        st.session_state.username = new_username
                        st.success("Profile and Username Updated!"); time.sleep(1); st.rerun()
                else:
                    users_col.update_one({"username": st.session_state.username}, {"$set": updates})
                    st.success("Profile Updated!"); time.sleep(1); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            
        with c2:
            st.markdown("<div class='content-card' style='margin: 0; max-width: 100% !important;'>", unsafe_allow_html=True)
            st.markdown("### Reaction Analytics")
            st.markdown("<p class='muted-text'>Your most frequently used emojis across your memory vault.</p>", unsafe_allow_html=True)
            
            pipeline = [
                {"$match": {"username": st.session_state.username, "tag": {"$ne": ""}}},
                {"$group": {"_id": "$tag", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 4}
            ]
            stats = list(files_col.aggregate(pipeline))
            
            if stats:
                scols = st.columns(2)
                for i, stat in enumerate(stats):
                    scols[i % 2].metric(label="React", value=stat["_id"], delta=f"{stat['count']} times")
            else:
                st.info("You haven't reacted to any memories yet!")
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.markdown('<div class="custom-footer">© 2026 voidememo. All rights reserved.</div>', unsafe_allow_html=True)