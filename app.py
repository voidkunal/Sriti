import streamlit as st
import streamlit.components.v1 as components
from pymongo import MongoClient
import hashlib
import cloudinary
import cloudinary.uploader
import certifi
import time
import uuid  
import plotly.express as px

# --- NEW IMPORTS FOR FORGOT PASSWORD ---
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

# ---------------- UI CONFIG ----------------
st.set_page_config(page_title="Memory Vault Dashboard", page_icon="🌐", layout="wide")

# ---------------- CONFIG (PRODUCTION SAFE) ----------------
# Fetching secrets securely from Streamlit Cloud
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

# ---------------- CSS (LIQUID GLASS DASHBOARD THEME) ----------------
st.markdown("""
<style>
/* 1. App Background */
.stApp {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364) !important;
}

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 80px !important; 
}

/* Fix text color globally for dark background */
.stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label {
    color: #e0e0e0 !important;
}

/* 2. Glass Cards for Media & Dashboard Widgets */
.card { 
    position: relative; 
    border-radius: 16px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.05); 
    backdrop-filter: blur(15px); 
    -webkit-backdrop-filter: blur(15px); 
    border: 1px solid rgba(255, 255, 255, 0.15); 
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3); 
    transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), box-shadow 0.3s ease;
}
.card:hover { 
    transform: translateY(-6px);
    box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.5);
}

/* 3. Dashboard-Style Blue Glass Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(41, 128, 185, 0.6), rgba(44, 62, 80, 0.8)) !important;
    backdrop-filter: blur(25px) !important;
    -webkit-backdrop-filter: blur(25px) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
}

/* Custom Sidebar Navigation Buttons (Dashboard Style) */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding-left: 15px !important;
    font-size: 16px !important;
    border-radius: 10px !important;
    transition: all 0.3s ease !important;
    margin-bottom: 5px !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.15) !important;
    transform: translateX(5px) !important;
}

/* 4. Glass Popups / Dialog Modals */
div[role="dialog"] {
    background: rgba(20, 30, 40, 0.65) !important; 
    backdrop-filter: blur(25px) !important;
    -webkit-backdrop-filter: blur(25px) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    border-radius: 20px !important;
    box-shadow: 0 10px 50px rgba(0, 0, 0, 0.8) !important;
}

/* 5. Glass Popover Menus */
[data-testid="stPopoverBody"] {
    background: rgba(20, 30, 40, 0.7) !important;
    backdrop-filter: blur(20px) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.6) !important;
}

/* 6. Glass Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: rgba(255, 255, 255, 0.05) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    color: white !important;
    border-radius: 10px !important;
}

/* 7. Glass File Uploader */
[data-testid="stFileUploader"] > div {
    background: rgba(255, 255, 255, 0.05) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px dashed rgba(255, 255, 255, 0.3) !important;
    border-radius: 16px !important;
    transition: all 0.3s ease;
}
[data-testid="stFileUploader"] > div:hover {
    background: rgba(255, 255, 255, 0.1) !important;
    border: 1px dashed rgba(255, 255, 255, 0.6) !important;
}

/* 8. Regular Glass Buttons (Main Area) */
.stApp .stButton > button {
    background: rgba(255, 255, 255, 0.08) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.2) !important;
    border-radius: 10px;
    color: white !important;
    transition: all 0.3s ease !important;
}
.stApp .stButton > button:hover {
    background: rgba(255, 255, 255, 0.2) !important; 
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    transform: translateY(-2px);
}

/* Primary Buttons */
.stButton > button[kind="primary"] {
    background: rgba(50, 150, 255, 0.2) !important;
    border: 1px solid rgba(50, 150, 255, 0.4) !important;
}
.stButton > button[kind="primary"]:hover {
    background: rgba(50, 150, 255, 0.3) !important;
}

/* Glass Download Button */
.glass-download {
    display: flex;
    justify-content: center;
    align-items: center;
    background: rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    text-decoration: none;
    height: 42px; 
    transition: all 0.3s ease;
}
.glass-download:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: translateY(-2px);
}

/* Overlay for images */
.overlay {
    position:absolute;
    top:0;left:0;
    width:100%;height:100%;
    background: rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(2px);
    opacity:0;
    transition:0.3s ease-in-out;
}
.card:hover .overlay { opacity:1; }

/* Fixed Custom Footer */
.custom-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    text-align: center;
    padding: 12px;
    background: rgba(20, 30, 40, 0.6);
    backdrop-filter: blur(15px);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
    z-index: 1000;
}
</style>

<div class="custom-footer">
    Copyright © 2026 by @Kunal_Mandal | All Rights Reserved.
</div>
""", unsafe_allow_html=True)


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

# --- EMAIL SENDER FUNCTON ---
def send_otp_email(receiver_email, otp):
    try:
        sender_email = st.secrets["SMTP_EMAIL"]
        sender_password = st.secrets["SMTP_PASSWORD"] 
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "Memory Vault - Password Reset OTP"
        
        body = f"""
        Hello,
        
        You have requested to reset your password for Memory Vault.
        Your 6-digit OTP is: {otp}
        
        If you did not request this, please ignore this email.
        """
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

# --- POPUP MODALS ---
@st.dialog("⚠️ Confirm Deletion")
def delete_folder_dialog(folder_id, folder_name):
    st.write(f"Are you sure you want to completely delete the folder **{folder_name}** and everything inside it?")
    c1, c2 = st.columns(2)
    if c1.button("Yes, Delete It", type="primary", use_container_width=True):
        delete_folder_tree(folder_id)
        st.rerun()
    if c2.button("No, Cancel", use_container_width=True):
        st.rerun()

@st.dialog("✏️ Rename Folder")
def rename_folder_dialog(folder_id, current_name):
    new_name = st.text_input("Enter new folder name:", value=current_name)
    c1, c2 = st.columns(2)
    if c1.button("Save Changes", type="primary", use_container_width=True):
        if new_name.strip() and new_name.strip() != current_name:
            folders_col.update_one({"_id": folder_id}, {"$set": {"folder_name": new_name.strip()}})
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()

@st.dialog("⚠️ Confirm Deletion")
def delete_file_dialog(file_id, public_id, resource_type):
    st.write("Are you sure you want to delete this file?")
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
    st.warning("You must wait 24 hours before changing your reaction to this file.")
    st.info(f"Time remaining: **{hours} hours and {minutes} minutes**")
    if st.button("Got it", use_container_width=True):
        st.rerun()

# ---------------- SESSION ----------------
defaults = {
    "logged_in": False,
    "username": "",
    "current_folder": None,
    "page": "drive",
    "folder_key": 0,
    "uploader_key": 0,
    "reset_step": 0,      # For forgot password flow
    "reset_email": ""     # For forgot password flow
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Restore session on browser refresh
if not st.session_state.logged_in and "session" in st.query_params:
    token = st.query_params["session"]
    user = users_col.find_one({"session_token": token})
    if user:
        st.session_state.logged_in = True
        st.session_state.username = user["username"]
        
        root = folders_col.find_one({
            "username": user["username"],
            "parent_id": None
        })
        if root:
            st.session_state.current_folder = root["_id"]

# ---------------- AUTH ----------------
def register(username, password, email):
    if users_col.find_one({"username": username}):
        return False

    users_col.insert_one({
        "username": username,
        "email": email,
        "password": hash_password(password),
        "profile_photo": "",
        "bio": "",
        "session_token": "",
        "reset_otp": "" 
    })
    root = folders_col.insert_one({
        "username": username,
        "folder_name": "root",
        "parent_id": None
    })
    st.session_state.current_folder = root.inserted_id
    return True

def login(identifier, password):
    user = users_col.find_one({
        "$or": [{"username": identifier}, {"email": identifier}]
    })
    if user and user["password"] == hash_password(password):
        root = folders_col.find_one({
            "username": user["username"],
            "parent_id": None
        })
        if root:
            st.session_state.current_folder = root["_id"]
        return user["username"]
    return False

# ---------------- UI: LIVE DASHBOARD HEADER ----------------
components.html(
    """
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, sans-serif; }
        .glass-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding: 15px 30px;
            border-radius: 0 0 20px 20px;
            color: rgba(255, 255, 255, 0.9);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        }
        .logo { font-size: 20px; font-weight: bold; letter-spacing: 1px;}
        .clock { font-size: 16px; font-weight: 500; opacity: 0.9;}
    </style>
    <div class="glass-nav">
        <div class="logo">🌐 Memory Vault</div>
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

# ================= LANDING =================
if not st.session_state.logged_in:
    st.title("📁 Private Memory Vault")

    # ADDED: Third Tab for Forgot Password
    tab1, tab2, tab3 = st.tabs(["Login", "Sign Up", "Forgot Password"])

    with tab1:
        identifier = st.text_input("Username or Email", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login", type="primary"):
            result = login(identifier, password)
            if result:
                token = str(uuid.uuid4())
                users_col.update_one({"username": result}, {"$set": {"session_token": token}})
                st.query_params["session"] = token 
                
                st.session_state.logged_in = True
                st.session_state.username = result
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        new_user = st.text_input("Username", key="signup_user")
        email = st.text_input("Email", key="signup_email")
        new_pass = st.text_input("Password", type="password", key="signup_pass")

        if st.button("Create Account", type="primary"):
            if register(new_user, new_pass, email):
                token = str(uuid.uuid4())
                users_col.update_one({"username": new_user}, {"$set": {"session_token": token}})
                st.query_params["session"] = token

                st.session_state.logged_in = True
                st.session_state.username = new_user
                st.rerun()
            else:
                st.error("User exists")

    # --- NEW: FORGOT PASSWORD FLOW ---
    with tab3:
        st.subheader("Recover Your Password")
        
        if st.session_state.reset_step == 0:
            reset_email = st.text_input("Enter your registered Email", key="reset_email_input")
            if st.button("Send Recovery OTP", type="primary"):
                user = users_col.find_one({"email": reset_email})
                if user:
                    with st.spinner("Sending OTP securely via Google SMTP..."):
                        otp = str(random.randint(100000, 999999))
                        # Save OTP to database
                        users_col.update_one({"email": reset_email}, {"$set": {"reset_otp": otp}})
                        
                        if send_otp_email(reset_email, otp):
                            st.session_state.reset_step = 1
                            st.session_state.reset_email = reset_email
                            st.rerun()
                        else:
                            st.error("Could not send email. Please check Streamlit SMTP secrets.")
                else:
                    st.error("This email is not registered in our database.")
                    
        elif st.session_state.reset_step == 1:
            st.success(f"An OTP was successfully sent to: **{st.session_state.reset_email}**")
            entered_otp = st.text_input("Enter 6-Digit OTP", key="entered_otp")
            new_pwd = st.text_input("Enter New Password", type="password", key="new_pwd")
            confirm_pwd = st.text_input("Confirm New Password", type="password", key="confirm_pwd")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verify & Reset Password", type="primary", use_container_width=True):
                    if new_pwd != confirm_pwd:
                        st.error("Passwords do not match!")
                    elif len(new_pwd) < 4:
                        st.error("Password is too short.")
                    else:
                        user = users_col.find_one({"email": st.session_state.reset_email})
                        if user and user.get("reset_otp") == entered_otp:
                            # Update to new password and clear the OTP
                            users_col.update_one(
                                {"email": st.session_state.reset_email}, 
                                {"$set": {"password": hash_password(new_pwd), "reset_otp": ""}}
                            )
                            st.success("Password updated successfully! You can now log in.")
                            time.sleep(2)
                            # Reset states and refresh
                            st.session_state.reset_step = 0
                            st.session_state.reset_email = ""
                            st.rerun()
                        else:
                            st.error("Invalid or Incorrect OTP!")
            with col2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.reset_step = 0
                    st.session_state.reset_email = ""
                    st.rerun()

# ================= DASHBOARD =================
else:
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
            
            # Fetch Stats
            total_folders = folders_col.count_documents({"username": st.session_state.username}) - 1
            total_files = files_col.count_documents({"username": st.session_state.username})
            
            with dash_c1:
                st.markdown(f"""
                <div class="card" style="padding: 20px; text-align: center; height: 100%;">
                    <h2 style="margin: 0; color: #4facfe;">{total_folders}</h2>
                    <p style="margin: 0; opacity: 0.8;">Total Folders</p>
                </div>
                """, unsafe_allow_html=True)
                
            with dash_c2:
                st.markdown(f"""
                <div class="card" style="padding: 20px; text-align: center; height: 100%;">
                    <h2 style="margin: 0; color: #4facfe;">{total_files}</h2>
                    <p style="margin: 0; opacity: 0.8;">Total Files</p>
                </div>
                """, unsafe_allow_html=True)
                
            with dash_c3:
                prof_pic = user_data.get("profile_photo") or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
                bio = user_data.get("bio") or "Welcome to your Dashboard"
                st.markdown(f"""
                <div class="card" style="padding: 15px; display: flex; align-items: center; gap: 15px; height: 100%;">
                    <img src="{prof_pic}" style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(255,255,255,0.3);">
                    <div>
                        <h3 style="margin: 0;">{st.session_state.username}</h3>
                        <p style="margin: 0; font-size: 0.9em; opacity: 0.8;">"{bio}"</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            st.write("<br>", unsafe_allow_html=True)

            # Create Folder Area
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

        # # Upload & File Logic
        # if not is_root:
        #     with st.expander("☁️ Upload Files", expanded=True):
        #         uploaded_files = st.file_uploader("Drag and drop files here", accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}", label_visibility="collapsed")

        #         if uploaded_files:
        #             with st.spinner("Uploading to secure vault..."):
        #                 for file in uploaded_files:
        #                     r_type = "video" if file.type.startswith("video") else "image"
        #                     res = cloudinary.uploader.upload(file, resource_type=r_type)

        #                     files_col.insert_one({
        #                         "username": st.session_state.username,
        #                         "folder_id": st.session_state.current_folder,
        #                         "filename": file.name,
        #                         "url": res["secure_url"],
        #                         "public_id": res["public_id"],
        #                         "resource_type": r_type,
        #                         "tag": "",
        #                         "tag_time": 0 
        #                     })
                    
        #             st.session_state.uploader_key += 1 
        #             st.success("Files successfully uploaded!")
        #             time.sleep(1) 
        #             st.rerun()
        
        
        # Upload & File Logic
        if not is_root:
            with st.expander("☁️ Upload Files", expanded=True):
                # We added a note to the UI so users know large files take time
                uploaded_files = st.file_uploader("Drag and drop files here (Max 1GB)", accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}", label_visibility="collapsed")

                if uploaded_files:
                    with st.spinner("Uploading to secure vault (large files may take a few minutes)..."):
                        for file in uploaded_files:
                            r_type = "video" if file.type.startswith("video") else "image"
                            
                            # Determine file size in MB
                            file_size_mb = file.size / (1024 * 1024)
                            
                            try:
                                # Use chunked uploads for anything over 50MB to be safe
                                if file_size_mb > 50:
                                    res = cloudinary.uploader.upload_large(
                                        file, 
                                        resource_type=r_type,
                                        chunk_size=20000000  # Uploads in 20MB chunks
                                    )
                                else:
                                    # Standard upload for smaller files
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

        # -------- FILE DISPLAY --------
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
                        <div style="
                            position:absolute; top:10px; right:10px; font-size:24px; z-index:10;
                            background: rgba(255, 255, 255, 0.2); backdrop-filter: blur(5px);
                            padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.3);
                            ">
                            {file['tag']}
                        </div>
                        """, unsafe_allow_html=True)

                    if file["resource_type"] == "image":
                        st.image(file["url"], use_container_width=True)
                    else:
                        st.video(file["url"])

                    st.markdown('<div class="overlay"></div></div>', unsafe_allow_html=True)

                    c1, c2, c3 = st.columns([2, 1, 1])

                    # 1. Emoji Picker
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
                                st.write("**Pick a reaction:**")
                                emojis = ["🥰", "❤️", "😘", "🔥", "😂", "👍", "🎉", "✨", "🥺", "😎", "💯", "🙏", "😭", "😮", "😡", "💩"]
                                e_cols = st.columns(4)
                                for e_idx, em in enumerate(emojis):
                                    if e_cols[e_idx % 4].button(em, key=f"em_{file['_id']}_{e_idx}", use_container_width=True):
                                        files_col.update_one({"_id": file["_id"]}, {"$set": {"tag": em, "tag_time": time.time()}})
                                        st.rerun()

                    # 2. Download Button
                    with c2:
                        st.markdown(
                            f'<a href="{file["url"]}" download target="_blank" class="glass-download" title="Download">⬇️</a>',
                            unsafe_allow_html=True
                        )

                    # 3. Delete Button
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
            
    # ================= CONTACT =================
    elif st.session_state.page == "contact":
        st.title("📞 Contact Us")
        st.markdown("""
        <div class="card" style="padding: 30px; max-width: 600px; margin: auto;">
            <h3>Need Help? Get in Touch!</h3>
            <p>If you have any questions, feedback, or need assistance, feel free to reach out to us. We're here to help you make the most of your Memory Vault experience.</p>
            <ul>
                <li><strong>Email:</strong> <a href="mailto:khalifa.miya.love@gmail.com">khalifa.miya.love@gmail.com</a></li>
            </ul>
        </div>
        """, unsafe_allow_html=True)