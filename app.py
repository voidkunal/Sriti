import streamlit as st
import streamlit.components.v1 as components
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
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
import html
import secrets 
import json
import io
import requests

# ML Libraries for Data Protection Model
import tensorflow as tf
from PIL import Image
import numpy as np

# ==========================================
# 1. UI CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="voidememo Vault", page_icon="🌐", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid="stSidebar"], [data-testid="stSidebarNav"], [data-testid="collapsedControl"] { 
        display: none !important; width: 0 !important; min-width: 0 !important; margin: 0 !important; padding: 0 !important;
    }
    .stApp, [data-testid="stAppViewContainer"], .main {
        width: 100vw !important; max-width: 100vw !important; margin-left: 0 !important; padding-left: 0 !important; padding-right: 0 !important; left: 0 !important;
    }
    header[data-testid="stHeader"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# PURE AI PROTECTION ENGINE (STRICT)
# ==========================================
@st.cache_resource(show_spinner=False)
def load_nsfw_model():
    try:
        model = tf.keras.models.load_model('custom_nsfw_model.h5', compile=False)
        return model
    except Exception as e:
        print(f"Failed to load AI model: {e}")
        return None

safety_model = load_nsfw_model()

def is_safe_content(file_bytes, model):
    if model is None:
        # If the model is offline, return True so the app doesn't crash, 
        # but the UI will show a massive red warning to the developer.
        return True 
        
    try:
        pil_img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
        
        # DYNAMIC SHAPE DETECTION: Asks your specific model what image size it expects
        input_shape = model.input_shape
        target_size = (224, 224) # Fallback
        if input_shape and len(input_shape) >= 3 and input_shape[1] is not None:
            target_size = (input_shape[1], input_shape[2])
            
        img_resized = pil_img.resize(target_size, Image.Resampling.BILINEAR)
        img_array = np.array(img_resized, dtype=np.float32)
        
        # Normalize (Standard 0-1)
        norm_array = np.expand_dims(img_array / 255.0, axis=0)
        
        prediction = model.predict(norm_array, verbose=0)[0]
        
        # AGGRESSIVE THRESHOLDS (50%+)
        if len(prediction) == 5:
            # Classes: [drawings, hentai, neutral, porn, sexy]
            if prediction[1] >= 0.50 or prediction[3] >= 0.50 or prediction[4] >= 0.50:
                return False
        elif len(prediction) >= 2:
            if prediction[1] >= 0.50: return False
        elif len(prediction) == 1:
            if prediction[0] >= 0.50: return False
            
        return True 
    except Exception as e:
        print(f"AI Prediction Crash: {e}")
        # If the prediction logic crashes, flag it as unsafe so you know it's broken!
        return False 

# ==========================================
# 2. DATABASE & CLOUD CONFIGURATION
# ==========================================
MONGO_URI = st.secrets["MONGO_URI"]

client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
db = client["memory_vault"]

users_col = db["users"]
files_col = db["files"]
folders_col = db["folders"]
shares_col = db["shares"]             
notifications_col = db["notifications"] 

cloudinary.config(
    cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key=st.secrets["CLOUDINARY_API_KEY"],
    api_secret=st.secrets["CLOUDINARY_API_SECRET"]
)

# ==========================================
# 3. HEADLESS API ROUTER
# ==========================================
api_req_key = st.query_params.get("api_key")
if api_req_key:
    st.markdown("""
    <style>
        #MainMenu {visibility: hidden !important;} 
        footer {display: none !important; visibility: hidden !important;} 
        header {display: none !important;} 
        .stApp {background: transparent !important;}
        div[data-testid="stAppViewBlockContainer"] { padding: 0 !important; max-width: 100% !important; margin: 0 !important; background: transparent !important;}
    </style>
    """, unsafe_allow_html=True)
    
    target_folder = folders_col.find_one({"api_key": api_req_key, "api_enabled": True})
    
    if target_folder:
        files_data = list(files_col.find(
            {"folder_id": target_folder["_id"]}, 
            {"_id": 0, "filename": 1, "url": 1, "resource_type": 1, "is_flagged": 1}
        ))
        
        if len(files_data) > 0:
            media_html = ""
            for item in files_data:
                safe_url = html.escape(item["url"])
                is_flagged = item.get("is_flagged", False)
                
                if item["resource_type"] == "image":
                    if is_flagged:
                        media_html += f'''
                        <div style="position:relative; width:250px; height:380px; flex: 0 0 auto; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 16px rgba(0,0,0,0.3);">
                            <img src="{safe_url}" class="slide-media" style="width:100%; height:100%; object-fit:cover; filter: blur(25px); transform: scale(1.1); cursor: pointer;" onclick="this.style.filter='none'; this.style.transform='scale(1)'" onmouseleave="this.style.filter='blur(25px)'; this.style.transform='scale(1.1)'">
                            <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:50px; pointer-events:none; text-shadow: 0 2px 5px rgba(0,0,0,0.5);">🙈</div>
                        </div>'''
                    else:
                        media_html += f'<img src="{safe_url}" class="slide-media" style="flex: 0 0 auto; width: 250px; height: 380px; object-fit: cover; border-radius: 12px; scroll-snap-align: center; box-shadow: 0 8px 16px rgba(0,0,0,0.3); transition: transform 0.3s ease;">'
                else:
                    media_html += f'<video src="{safe_url}" controls class="slide-media" style="flex: 0 0 auto; width: 250px; height: 380px; object-fit: cover; border-radius: 12px; scroll-snap-align: center; box-shadow: 0 8px 16px rgba(0,0,0,0.3); transition: transform 0.3s ease;"></video>'
                    
            carousel_html = f"""
            <style>
                body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; font-family: sans-serif; }}
                .carousel-wrapper {{ position: relative; width: 100%; padding: 10px 40px; box-sizing: border-box; }}
                .carousel-track {{ display: flex; gap: 20px; overflow-x: auto; scroll-snap-type: x mandatory; scroll-behavior: smooth; -ms-overflow-style: none; scrollbar-width: none; }}
                .carousel-track::-webkit-scrollbar {{ display: none; }}
                .slide-media:hover {{ transform: scale(1.02); }}
                .slide-arrow {{ position: absolute; top: 50%; transform: translateY(-50%); background: rgba(255, 255, 255, 0.8); color: #333; border: none; font-size: 24px; font-weight: bold; cursor: pointer; width: 40px; height: 40px; border-radius: 50%; z-index: 10; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 8px rgba(0,0,0,0.2); transition: background 0.3s ease; }}
                .slide-arrow:hover {{ background: rgba(255, 255, 255, 1); }}
                .left-arrow {{ left: 0px; }}
                .right-arrow {{ right: 0px; }}
            </style>
            
            <div class="carousel-wrapper" id="carouselWrapper">
                <button class="slide-arrow left-arrow" onclick="slideLeft()">&#10094;</button>
                <div class="carousel-track" id="carouselTrack">
                    {media_html}
                </div>
                <button class="slide-arrow right-arrow" onclick="slideRight()">&#10095;</button>
            </div>
            
            <script>
                const track = document.getElementById("carouselTrack");
                const scrollAmount = 270; 
                function slideLeft() {{ track.scrollBy({{ left: -scrollAmount, behavior: 'smooth' }}); }}
                function slideRight() {{ 
                    if (track.scrollLeft + track.clientWidth >= track.scrollWidth - 10) {{
                        track.scrollTo({{ left: 0, behavior: 'smooth' }});
                    }} else {{
                        track.scrollBy({{ left: scrollAmount, behavior: 'smooth' }}); 
                    }}
                }}
                let autoSlide = setInterval(slideRight, 3500);
                const wrapper = document.getElementById('carouselWrapper');
                wrapper.addEventListener('mouseenter', () => clearInterval(autoSlide));
                wrapper.addEventListener('mouseleave', () => {{ autoSlide = setInterval(slideRight, 3500); }});
            </script>
            """
            components.html(carousel_html, height=450)
        else:
            st.markdown('<p style="color: white; text-align: center;">Gallery is empty.</p>', unsafe_allow_html=True)
    else:
        st.error("Access Denied. Invalid or disabled API Key.")
        
    st.stop()


# ==========================================
# 4. UTILITIES & SECURITY FUNCTIONS
# ==========================================
def hash_password(password):
    pwd_str = str(password).strip()
    pepper = st.secrets.get("APP_PEPPER", "")
    return hashlib.sha256((pwd_str + pepper).encode()).hexdigest()

def time_ago(ts):
    if not ts: return ""
    diff = time.time() - ts
    if diff < 60: return "Just now"
    elif diff < 3600: return f"{int(diff//60)}m ago"
    elif diff < 86400: return f"{int(diff//3600)}h ago"
    else: return f"{int(diff//86400)}d ago"

def register(email, password, first_name, last_name, birthday, pin_code, phone_number):
    email = str(email).strip().lower()
    existing_count = users_col.count_documents({"email": email})
    
    if existing_count >= 5: return "MAX_ACCOUNTS"
    if existing_count > 0 and not str(phone_number).strip(): return "PHONE_REQUIRED"

    base_username = email.split('@')[0]
    username = base_username if existing_count == 0 else f"{base_username}_{existing_count}"
    while users_col.find_one({"username": username}):
        username = f"{base_username}_{random.randint(100, 9999)}"
    
    safe_fname = html.escape(str(first_name).strip())
    safe_lname = html.escape(str(last_name).strip())
    safe_username = html.escape(username)
    safe_pin = html.escape(str(pin_code).strip())
    safe_phone = html.escape(str(phone_number).strip())
    
    users_col.insert_one({
        "username": safe_username, "first_name": safe_fname, "last_name": safe_lname,
        "birthday": str(birthday), "email": email, "password": hash_password(password),
        "pin_code": safe_pin, "phone_number": safe_phone,
        "profile_photo": "", "bio": "", "session_token": "", "reset_otp": "", "reset_otp_exp": 0
    })
    folders_col.insert_one({"username": safe_username, "folder_name": "root", "parent_id": None, "is_locked": False, "api_key": "", "api_enabled": False})
    return safe_username

def login(email, password):
    email = str(email).strip().lower()
    user = users_col.find_one({"email": email, "password": hash_password(password)})
    if user: return user["username"]
    time.sleep(1)
    return False

def delete_folder_tree(folder_id):
    subfolders = list(folders_col.find({"parent_id": folder_id}))
    for sub in subfolders:
        delete_folder_tree(sub["_id"])
    files = list(files_col.find({"folder_id": folder_id}))
    for f in files:
        if files_col.count_documents({"public_id": f["public_id"]}) <= 1:
            cloudinary.uploader.destroy(f["public_id"], resource_type=f["resource_type"])
    files_col.delete_many({"folder_id": folder_id})
    folders_col.delete_one({"_id": folder_id})

def send_otp_email(receiver_email, otp):
    try:
        sender_email = st.secrets["SMTP_EMAIL"]
        sender_password = st.secrets["SMTP_PASSWORD"] 
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = str(receiver_email).strip()
        msg['Subject'] = "voidememo - Vault Security Code"
        body = f"Hello,\n\nYour secure 6-digit access code is: {otp}\n\nThis code will expire in 10 minutes. If you did not request this, secure your account immediately."
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error("Failed to send secure email. Please try again later.")
        return False

# ==========================================
# 5. NATIVE GESTURE ROUTING SYSTEM
# ==========================================
def get_nav_link(page=None, view=None, tab=None, folder=None, story_group=None, story_idx=None, lightbox_idx=None, profile_hub=None, ai_chat=None, react=None, action=None, file_id=None):
    params = []
    if page is not None: params.append(f"page={page}")
    if view is not None: params.append(f"view={view}")
    if tab is not None: params.append(f"tab={tab}")
    if folder is not None: params.append(f"folder={folder}")
    if story_group is not None: params.append(f"story_group={story_group}")
    if story_idx is not None: params.append(f"story_idx={story_idx}")
    if lightbox_idx is not None: params.append(f"lightbox_idx={lightbox_idx}")
    if profile_hub is not None: params.append(f"profile_hub={profile_hub}")
    if ai_chat is not None: params.append(f"ai_chat={ai_chat}")
    if react is not None: params.append(f"react={react}")
    if action is not None: params.append(f"action={action}")
    if file_id is not None: params.append(f"file_id={file_id}")
    if "session" in st.query_params:
        params.append(f"session={html.escape(st.query_params['session'])}")
    return "?" + "&".join(params)

app_page = st.query_params.get("page", "landing")
auth_view = st.query_params.get("view", "login")
active_folder = st.query_params.get("folder", "root")

defaults = {
    "logged_in": False, "username": "", "reset_step": 0, "reset_email": "",
    "uploader_key": 0, "folder_key": 0, "story_groups": [], "pending_share": None,
    "pending_delete": None, "pending_locked_react": None, "pending_move": None,
    "login_step": 0, "login_email": ""
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if not st.session_state.logged_in and "session" in st.query_params:
    token = str(st.query_params["session"]).strip()
    user = users_col.find_one({"session_token": token})
    if user:
        st.session_state.logged_in = True
        st.session_state.username = user["username"]

# ==========================================
# 6. PRE-RENDER ACTION INTERCEPTORS
# ==========================================
if st.session_state.logged_in:
    if "action" in st.query_params and "file_id" in st.query_params:
        try:
            action = st.query_params["action"]
            fid = ObjectId(st.query_params["file_id"])
            file = files_col.find_one({"_id": fid})
            
            if file:
                if action == "confirm_delete":
                    st.session_state.pending_delete = str(fid)
                elif action == "move":
                    st.session_state.pending_move = str(fid)
                elif action == "locked_react":
                    time_elapsed = time.time() - file.get("tag_time", 0)
                    st.session_state.pending_locked_react = max(0, 86400 - time_elapsed)
                elif action == "pin":
                    if file.get("pin_order", 0) > 0:
                        files_col.update_one({"_id": fid}, {"$unset": {"pin_order": ""}})
                    else:
                        max_pin = files_col.find_one({"folder_id": file["folder_id"], "pin_order": {"$exists": True}}, sort=[("pin_order", -1)])
                        new_pin_val = 1
                        if max_pin and "pin_order" in max_pin:
                            new_pin_val = max_pin["pin_order"] + 1
                        files_col.update_one({"_id": fid}, {"$set": {"pin_order": new_pin_val}})
                elif action == "cover":
                    url = file["url"]
                    if file["resource_type"] == "video":
                        url = url.replace(".mp4", ".jpg").replace(".webm", ".jpg").replace(".mov", ".jpg")
                    folders_col.update_one({"_id": file["folder_id"]}, {"$set": {"cover_photo": url}})
                elif action == "share":
                    st.session_state.pending_share = str(fid)
                
                # --- MANUAL OVERRIDE CONTROLS (RESTORED) ---
                elif action == "unflag":
                    files_col.update_one({"_id": fid}, {"$set": {"is_flagged": False}})
                elif action == "flag":
                    files_col.update_one({"_id": fid}, {"$set": {"is_flagged": True}})

        except InvalidId: pass
        
        del st.query_params["action"]
        del st.query_params["file_id"]
        # Keep lightbox open at the same index
        st.rerun()

    if "react" in st.query_params:
        try:
            if "file_id" in st.query_params:
                fid = ObjectId(st.query_params["file_id"])
                files_col.update_one({"_id": fid}, {"$set": {"tag": st.query_params["react"], "tag_time": time.time()}})
            elif "story_group" in st.query_params and "story_idx" in st.query_params:
                s_grp = int(st.query_params["story_group"])
                s_idx = int(st.query_params["story_idx"])
                if s_grp < len(st.session_state.story_groups):
                    items = st.session_state.story_groups[s_grp]["items"]
                    if s_idx < len(items):
                        file_id = items[s_idx]["_id"]
                        files_col.update_one({"_id": file_id}, {"$set": {"tag": st.query_params["react"], "tag_time": time.time()}})
        except Exception: pass
        del st.query_params["react"]
        if "file_id" in st.query_params: del st.query_params["file_id"]
        st.rerun()

# ==========================================
# 7. TIME-SEEDED DETERMINISTIC ENGINE
# ==========================================
if st.session_state.logged_in:
    time_window = int(time.time() / 300) 
    random.seed(f"{st.session_state.username}_{time_window}") 
    
    all_user_media = list(files_col.find({"username": st.session_state.username}))
    story_groups = []
    
    if all_user_media:
        now = datetime.datetime.now(datetime.timezone.utc)
        recent, favorites, throwback = [], [], []
        for f in all_user_media:
            upload_date = f["_id"].generation_time
            age_days = (now - upload_date).days
            if age_days <= 7: recent.append(f)
            
            if f.get("tag"):
                tag_age_seconds = time.time() - f.get("tag_time", 0)
                if tag_age_seconds >= 604800:
                    favorites.append(f)
                    
            if age_days > 30: throwback.append(f)
                
        if recent:
            recent.sort(key=lambda x: x["_id"].generation_time, reverse=True)
            story_groups.append({"label": "Recent Highlights", "items": recent[:6]})
        if throwback:
            random.shuffle(throwback)
            story_groups.append({"label": "Memory Lane", "items": throwback[:6]})
        if favorites:
            random.shuffle(favorites)
            story_groups.append({"label": "Previous week's favs ⭐", "items": favorites[:6]})
            
        random_media = all_user_media[:]
        random.shuffle(random_media)
        story_groups.append({"label": "Discover", "items": random_media[:6]})
            
    st.session_state.story_groups = story_groups
    random.seed() 

# ==========================================
# 8. DIALOG FUNCTIONS
# ==========================================
@st.dialog("⚡ Developer API Access")
def developer_api_dialog(folder_id_str):
    fid = ObjectId(folder_id_str)
    folder = folders_col.find_one({"_id": fid})
    
    st.markdown("### Read-Only API Integration")
    st.write("Generate a REST endpoint to safely embed this album's media on your external website, portfolio, or app.")
    
    has_api = folder.get("api_enabled", False)
    api_key = folder.get("api_key", "")
    
    if not api_key:
        if st.button("Generate API Key", type="primary", use_container_width=True):
            new_key = "vm_api_" + secrets.token_urlsafe(24)
            folders_col.update_one({"_id": fid}, {"$set": {"api_key": new_key, "api_enabled": True}})
            st.rerun()
    else:
        st.success("✅ API is Currently Active" if has_api else "⏸️ API is Currently Paused")
        endpoint_url = f"https://voidmemo.streamlit.app/?embed=true&api_key={api_key}" 
        st.text_input("Your Secret API Endpoint URL:", value=endpoint_url, disabled=True)
        
        toggle_text = "Pause API Access" if has_api else "Resume API Access"
        if st.button(toggle_text, use_container_width=True):
            folders_col.update_one({"_id": fid}, {"$set": {"api_enabled": not has_api}})
            st.rerun()
            
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("#### Quick Integration Snippets")
        t1, t2 = st.tabs(["React (MERN)", "Python"])
        with t1:
            st.code(f"""// React / Next.js
import {{ useEffect, useState }} from 'react';
export default function Gallery() {{
  const [media, setMedia] = useState([]);
  useEffect(() => {{ fetch('{endpoint_url}').then(r=>r.text()).then(t=>console.log(t)) }}, []);
}}""", language="javascript")
        with t2:
            st.code(f"""import requests\nresp = requests.get('{endpoint_url}')""", language="python")

@st.dialog("⚠️ Confirm Deletion")
def delete_folder_dialog(folder_id, folder_name):
    st.write(f"Are you sure you want to completely delete **{html.escape(folder_name)}** and everything inside it?")
    c1, c2 = st.columns(2)
    if c1.button("Yes, Delete It", type="primary", use_container_width=True):
        delete_folder_tree(folder_id)
        st.query_params["folder"] = "root"
        st.rerun()
    if c2.button("No, Cancel", use_container_width=True): st.rerun()

@st.dialog("⚠️ Confirm File Deletion")
def delete_file_dialog(file_id, public_id, resource_type):
    st.write("Are you sure you want to delete this media permanently?")
    c1, c2 = st.columns(2)
    if c1.button("Yes, Delete It", type="primary", use_container_width=True):
        if files_col.count_documents({"public_id": public_id}) <= 1:
            cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        files_col.delete_one({"_id": file_id})
        st.rerun()
    if c2.button("No, Cancel", use_container_width=True): st.rerun()

@st.dialog("✏️ Rename Album")
def rename_folder_dialog(folder_id, current_name):
    new_name = st.text_input("Enter new album name:", value=current_name)
    c1, c2 = st.columns(2)
    if c1.button("Save Changes", type="primary", use_container_width=True):
        clean_name = str(new_name).strip()
        if clean_name and clean_name != current_name:
            folders_col.update_one({"_id": folder_id}, {"$set": {"folder_name": clean_name}})
        st.rerun()
    if c2.button("Cancel", use_container_width=True): st.rerun()

@st.dialog("📂 Move Media")
def move_media_dialog(file_id_str):
    try:
        fid = ObjectId(file_id_str)
        file = files_col.find_one({"_id": fid})
        if not file:
            st.error("File not found")
            if st.button("Close"): st.rerun()
            return
    except Exception:
        st.rerun()

    folders = list(folders_col.find({"username": st.session_state.username}))
    folder_options = {f["folder_name"] + (" (Home)" if f["folder_name"]=="root" else "") : f["_id"] for f in folders}

    st.write(f"Moving: **{html.escape(file.get('filename', 'Media Item'))}**")
    selected_folder_name = st.selectbox("Select destination album:", list(folder_options.keys()))

    c1, c2 = st.columns(2)
    if c1.button("Move File", type="primary", use_container_width=True):
        new_folder_id = folder_options[selected_folder_name]
        files_col.update_one({"_id": fid}, {"$set": {"folder_id": new_folder_id}})
        st.session_state.pending_move = None
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.session_state.pending_move = None
        st.rerun()

@st.dialog("⏳ Reaction Locked")
def locked_reaction_dialog(remaining_seconds):
    hours, remainder = divmod(int(remaining_seconds), 3600)
    minutes, _ = divmod(remainder, 60)
    st.warning("Emoji changes are locked for 24 hours after a reaction.")
    st.info(f"Time remaining: **{hours} hours and {minutes} minutes**")
    if st.button("Got it", use_container_width=True): st.rerun()

@st.dialog("🔍 Find & Remove Duplicates")
def find_duplicates_dialog(folder_id):
    st.write("This tool will scan the current album for exact duplicate images. It will keep one original and permanently delete the rest.")
    if st.button("Start Scan", type="primary", use_container_width=True):
        with st.spinner("Scanning album for duplicates... this may take a moment."):
            files_in_folder = list(files_col.find({"folder_id": folder_id}))
            hashes = {}
            duplicates_to_delete = []

            for f in files_in_folder:
                try:
                    response = requests.get(f["url"])
                    if response.status_code == 200:
                        file_hash = hashlib.md5(response.content).hexdigest()
                        if file_hash in hashes:
                            duplicates_to_delete.append(f)
                        else:
                            hashes[file_hash] = f
                except Exception:
                    pass

            if duplicates_to_delete:
                for df in duplicates_to_delete:
                    if files_col.count_documents({"public_id": df["public_id"]}) <= 1:
                        cloudinary.uploader.destroy(df["public_id"], resource_type=df["resource_type"])
                    files_col.delete_one({"_id": df["_id"]})
                
                st.success(f"Cleaned up! Found and removed {len(duplicates_to_delete)} duplicate files.")
                time.sleep(2.5)
                st.rerun()
            else:
                st.info("No duplicates found in this album! Everything looks clean.")
                time.sleep(2.5)
                st.rerun()

# ==========================================
# 10. MUTEX FULL-SCREEN OVERLAYS
# ==========================================
def render_share_media_overlay(target_data, mode):
    st.markdown("<style>header {display: none;} .block-container {padding: 3rem 1rem !important; max-width: 800px;}</style>", unsafe_allow_html=True)
    c1, c2 = st.columns([10, 1])
    c1.markdown("## 🔗 Share Media")
    if c2.button("✕", key="close_share_overlay"):
        if "share_folder" in st.query_params: del st.query_params["share_folder"]
        st.session_state.pending_share = None
        st.rerun()

    curr_user = users_col.find_one({"username": st.session_state.username})
    user_pin = curr_user.get("pin_code", "")
    
    try:
        if mode == "folder":
            cf_id = None if target_data == "root" else ObjectId(target_data)
            folder_files = list(files_col.find({"username": st.session_state.username, "folder_id": cf_id}))
            if not folder_files:
                st.info("No media files found to share in this folder.")
                st.stop()
            st.markdown("### 1. Select Media to Share")
            media_options = {html.escape(f['filename']) if f.get('filename') else str(f['_id']): f['_id'] for f in folder_files}
            selected_media_filenames = st.multiselect("Choose files from this album:", list(media_options.keys()), default=list(media_options.keys()), key="ms_media")
            selected_media_ids = [media_options[name] for name in selected_media_filenames]
        else:
            selected_media_ids = [ObjectId(target_data)]
            st.markdown("### 1. Share File")
            file_doc = files_col.find_one({"_id": selected_media_ids[0]})
            if file_doc: st.write(f"Sharing: **{html.escape(file_doc.get('filename', 'Media Item'))}**")
    except InvalidId:
        st.error("Invalid media reference.")
        st.stop()

    st.markdown("### 2. Discover Users")
    tab_n, tab_s = st.tabs(["📍 Nearby Users", "🔍 Search Global"])
    selected_users = []
    
    with tab_n:
        nearby_users = list(users_col.find({"pin_code": user_pin, "username": {"$ne": st.session_state.username}}))
        if nearby_users:
            sel_n = st.multiselect("Users in your area", [u["username"] for u in nearby_users], key="ms_nearby")
            selected_users.extend(sel_n)
        else: st.info("No users found with your PIN code.")
            
    with tab_s:
        sq = st.text_input("Search by username", key="search_user_input")
        if sq:
            s_res = list(users_col.find({"username": {"$regex": sq, "$options": "i"}, "username": {"$ne": st.session_state.username}}))
            sel_s = st.multiselect("Search Results", [u["username"] for u in s_res], key="ms_search")
            selected_users.extend(sel_s)
            
    final_selection = list(set(selected_users))
    st.write("<br>", unsafe_allow_html=True)
    
    if st.button(f"Send to {len(final_selection)} users", type="primary", disabled=len(final_selection)==0 or len(selected_media_ids)==0, use_container_width=True):
        for u in final_selection:
            share_res = shares_col.insert_one({
                "sender": st.session_state.username, "receiver": u,
                "media_ids": selected_media_ids, "count": len(selected_media_ids), 
                "created_at": time.time(), "is_seen": False
            })
            msg_text = f"shared a memory with you." if len(selected_media_ids) == 1 else f"shared a {len(selected_media_ids)} memory batch with you."
            notifications_col.insert_one({"username": u, "sender": st.session_state.username, "type": "share", "share_id": share_res.inserted_id, "message": msg_text, "is_read": False, "created_at": time.time()})
        st.success("Shared successfully!")
        time.sleep(1)
        if "share_folder" in st.query_params: del st.query_params["share_folder"]
        st.session_state.pending_share = None
        st.rerun()
    st.stop()


def render_preview_shared_overlay(notif_id_str):
    st.markdown("<style>header {display: none;} .block-container {padding: 3rem 1rem !important; max-width: 900px;}</style>", unsafe_allow_html=True)
    c1, c2 = st.columns([10, 1])
    c1.markdown("## 📬 Shared Media Preview")
    if c2.button("✕", key="close_preview_overlay"):
        del st.query_params["preview_notif"]
        st.rerun()

    try: notif_oid = ObjectId(notif_id_str)
    except InvalidId: st.stop()

    notif = notifications_col.find_one({"_id": notif_oid})
    if not notif: st.stop()

    if notif.get("type") == "share_reaction":
        st.info(f"**{html.escape(notif['sender'])}** {html.escape(notif['message'])}")
        share_id_val = notif.get("share_id")
        if isinstance(share_id_val, str): share_id_val = ObjectId(share_id_val)
        share = shares_col.find_one({"_id": share_id_val}) if share_id_val else None
        
        if share and share.get("media_ids"):
            files_to_preview = list(files_col.find({"_id": {"$in": share.get("media_ids")[:1]}}))
            if files_to_preview:
                p_file = files_to_preview[0]
                safe_preview_url = html.escape(p_file["url"])
                st.write("They reacted to this memory:")
                st.markdown('<div class="media-container-wrapper" style="width: 150px; margin: 0 auto;">', unsafe_allow_html=True)
                if p_file["resource_type"] == "image":
                    st.markdown(f'<div class="square-media"><img src="{safe_preview_url}"></div>'.replace('\n', ''), unsafe_allow_html=True)
                else:
                    vid_thumb_preview = safe_preview_url.replace(".mp4", ".webm", ".jpg").replace(".mov", ".jpg")
                    st.markdown(f'<div class="square-media" style="position:relative;"><img src="{vid_thumb_preview}" onerror="this.src=\'https://cdn-icons-png.flaticon.com/512/2985/2985655.png\'"><div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); font-size:40px; color:white; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">▶️</div></div>'.replace('\n', unsafe_allow_html=True))
                st.markdown('</div><br>', unsafe_allow_html=True)

        if st.button("Mark as Read & Close", use_container_width=True):
            notifications_col.update_one({"_id": notif_oid}, {"$set": {"is_read": True}})
            del st.query_params["preview_notif"]
            st.rerun()
        st.stop()

    # Standard Share Review
    share = shares_col.find_one({"_id": notif.get("share_id")})
    media_ids = share.get("media_ids", []) if share else []
    if not media_ids:
        st.error("Shared media no longer exists.")
        st.stop()

    st.markdown(f"**From:** {html.escape(notif['sender'])} | **Includes:** {share['count']} memory copies.")
    st.write("<br>", unsafe_allow_html=True)
    
    files_to_preview = list(files_col.find({"_id": {"$in": media_ids}}))
    preview_cols = st.columns(4)
    for p_idx, p_file in enumerate(files_to_preview):
        safe_preview_url = html.escape(p_file["url"])
        with preview_cols[p_idx % 4]:
            st.markdown('<div class="media-container-wrapper">', unsafe_allow_html=True)
            if p_file["resource_type"] == "image":
                st.markdown(f'<div class="square-media"><img src="{safe_preview_url}"></div>'.replace('\n', ''), unsafe_allow_html=True)
            else:
                vid_thumb_preview = safe_preview_url.replace(".mp4", ".jpg").replace(".webm", ".jpg").replace(".mov", ".jpg")
                st.markdown(f'<div class="square-media" style="position:relative;"><img src="{vid_thumb_preview}" onerror="this.src=\'https://cdn-icons-png.flaticon.com/512/2985/2985655.png\'"><div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); font-size:40px; color:white; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">▶️</div></div>'.replace('\n', ''), unsafe_allow_html=True)
            with st.popover("⋮"):
                st.markdown(f'<a href="{safe_preview_url}" download target="_blank" style="display:block; padding: 8px 16px; border: 1.5px solid var(--border); border-radius: 8px; color: var(--text-primary); text-decoration: none; text-align: center; font-weight: 600; margin-bottom: 5px;">⬇️ Download</a>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
    st.markdown("<hr style='border-color: rgba(255,255,255,0.2); margin-top: 30px;'>", unsafe_allow_html=True)
    
    with st.popover("➕ Add Reaction"):
        e_cols = st.columns(4)
        for e_idx, em in enumerate(["🥰", "❤️", "🔥", "😂", "👍", "🎉", "✨", "🥺"]):
            if e_cols[e_idx % 4].button(em, key=f"sreact_{em}", use_container_width=True):
                notifications_col.insert_one({"username": notif['sender'], "sender": st.session_state.username, "type": "share_reaction", "share_id": notif.get("share_id"), "message": f"reacted {em} to your shared memory.", "is_read": False, "created_at": time.time()})
                st.success(f"Sent {em} to {html.escape(notif['sender'])}!"); time.sleep(1)
                del st.query_params["preview_notif"]
                st.rerun()

    st.write("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button(f"📥 Save {share['count']} items to Album", type="primary", use_container_width=True):
        root = folders_col.find_one({"username": st.session_state.username, "parent_id": None})
        root_id = root["_id"] if root else None
        
        shared_folder = folders_col.find_one({"username": st.session_state.username, "folder_name": {"$regex": "^Shared Media$", "$options": "i"}, "parent_id": root_id})
        if not shared_folder:
            res = folders_col.insert_one({"username": st.session_state.username, "folder_name": "Shared Media", "parent_id": root_id, "cover_photo": "", "is_locked": False})
            dest_f_id = res.inserted_id
        else: dest_f_id = shared_folder["_id"]
            
        files_col.insert_many([{
            "username": st.session_state.username, "folder_id": dest_f_id, "filename": f"Shared from {notif['sender']} - {file.get('filename','media')}",
            "url": file["url"], "public_id": file["public_id"], "resource_type": file["resource_type"], "tag": "", "tag_time": 0
        } for file in files_to_preview])

        notifications_col.update_one({"_id": notif_oid}, {"$set": {"is_read": True}})
        shares_col.update_one({"_id": share["_id"]}, {"$set": {"is_seen": True}})
        st.success("Saved to Shared Media album!"); time.sleep(1); del st.query_params["preview_notif"]; st.rerun()
        
    if c2.button("Mark Read & Close", use_container_width=True):
        notifications_col.update_one({"_id": notif_oid}, {"$set": {"is_read": True}})
        del st.query_params["preview_notif"]; st.rerun()
    st.stop()


def render_profile_hub_overlay():
    st.markdown("<style>header {display: none;} .block-container {padding: 3rem 5% !important; max-width: 100vw;}</style>", unsafe_allow_html=True)
    
    user_data = users_col.find_one({"username": st.session_state.username})
    
    c1, c2 = st.columns([10, 1])
    c1.markdown('<div class="dashboard-title" style="margin-bottom: 20px;">Profile Hub</div>', unsafe_allow_html=True)
    if c2.button("✕", key="close_hub_overlay"):
        del st.query_params["profile_hub"]
        st.rerun()

    p_tab1, p_tab2, p_tab3 = st.tabs(["⚙️ Settings", "🔔 Notifications", "👥 Switch Profiles"])
    
    with p_tab1:
        c1, c2 = st.columns([1.5, 1], gap="large")
        with c1:
            st.markdown("### Profile Settings")
            new_username = st.text_input("Username", value=user_data.get("username", ""))
            new_pin = st.text_input("PIN / Zip Code", value=user_data.get("pin_code", ""))
            new_email = st.text_input("Email", value=user_data.get("email", ""), disabled=True)
            new_phone = st.text_input("Phone Number", value=user_data.get("phone_number", ""))
            bio = st.text_area("Bio", value=user_data.get("bio", ""))
            pic = st.file_uploader("Profile Photo", key="profile_pic_upload")
            
            if st.button("Save Changes", type="primary"):
                updates = {"bio": html.escape(str(bio).strip()), "pin_code": html.escape(str(new_pin).strip()), "phone_number": html.escape(str(new_phone).strip())}
                if pic:
                    res = cloudinary.uploader.upload(pic)
                    updates["profile_photo"] = res["secure_url"]
                    
                clean_username = html.escape(str(new_username).strip())
                if clean_username != st.session_state.username:
                    if users_col.find_one({"username": clean_username}): st.error("Username already taken.")
                    else:
                        updates["username"] = clean_username
                        users_col.update_one({"username": st.session_state.username}, {"$set": updates})
                        folders_col.update_many({"username": st.session_state.username}, {"$set": {"username": clean_username}})
                        files_col.update_many({"username": st.session_state.username}, {"$set": {"username": clean_username}})
                        st.session_state.username = clean_username
                        st.success("Profile Updated!"); time.sleep(1); st.rerun()
                else:
                    users_col.update_one({"username": st.session_state.username}, {"$set": updates})
                    st.success("Profile Updated!"); time.sleep(1); st.rerun()
            
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown("### Safety Controls")
            st.write("Force a deep re-scan of ALL media using the core AI Protection rules.")
            
            if st.button("🔍 Force Deep Scan for Sensitive Content", use_container_width=True):
                with st.spinner("Analyzing all media with core trained AI..."):
                    updated_count = 0
                    
                    for f in files_col.find({"username": st.session_state.username, "resource_type": "image"}):
                        try:
                            resp = requests.get(f["url"], timeout=5)
                            if resp.status_code == 200:
                                safe = is_safe_content(resp.content, safety_model)
                                files_col.update_one({"_id": f["_id"]}, {"$set": {"is_flagged": not safe}})
                                updated_count += 1
                        except Exception: pass
                        
                    st.success(f"Deep scan complete! Re-evaluated {updated_count} files.")

        with c2:
            st.markdown("### Reaction Analytics")
            pipeline = [{"$match": {"username": st.session_state.username, "tag": {"$ne": ""}}}, {"$group": {"_id": "$tag", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 4}]
            stats = list(files_col.aggregate(pipeline))
            if stats:
                scols = st.columns(2)
                for i, stat in enumerate(stats): scols[i % 2].metric(label="React", value=html.escape(stat["_id"]), delta=f"{stat['count']} times")
            else: st.info("You haven't reacted to any memories yet!")
                
            st.markdown("<hr style='margin: 30px 0;'>", unsafe_allow_html=True)
            if st.button("🚪 Logout Complete Session", use_container_width=True):
                users_col.update_one({"username": st.session_state.username}, {"$set": {"session_token": ""}})
                st.session_state.logged_in = False; st.session_state.username = ""
                st.query_params.clear(); st.rerun()

    with p_tab2:
        if st.query_params.get("confirm_all_read", "").lower() == "true":
             notifications_col.update_many({"username": st.session_state.username}, {"$set": {"is_read": True}})
             st.query_params.pop("confirm_all_read", None)
             st.success("All read!"); time.sleep(1); st.rerun()

        if st.query_params.get("confirm_clear_all", "").lower() == "true":
             notifications_col.delete_many({"username": st.session_state.username})
             st.query_params.pop("confirm_clear_all", None)
             st.success("All cleared!"); time.sleep(1); st.rerun()

        st.markdown("### Your Notifications")
        ca, cb = st.columns(2)
        if ca.button("✔️ Mark All Read", use_container_width=True):
            st.query_params["confirm_all_read"] = "true"; st.rerun()
        if cb.button("🗑️ Clear All", use_container_width=True):
            st.query_params["confirm_clear_all"] = "true"; st.rerun()
            
        st.markdown("<hr style='margin: 15px 0; border-color: var(--border);'>", unsafe_allow_html=True)

        notifs = list(notifications_col.find({"username": st.session_state.username}).sort("created_at", -1))
        if not notifs: st.info("You have no notifications.")
        else:
            for n in notifs:
                col_msg, col_del = st.columns([11, 1], vertical_alignment="center")
                status = "🟢" if not n.get("is_read") else "⚪"
                t_ago = time_ago(n.get("created_at", time.time()))
                
                with col_msg:
                    label = f"{status} [{t_ago}] {html.escape(n['sender'])} {n['message']}"
                    if st.button(label, key=f"nbtn_{n['_id']}", use_container_width=True):
                        notifications_col.update_one({"_id": n['_id']}, {"$set": {"is_read": True}})
                        if n.get("type") in ["share", "share_reaction"]: 
                            st.query_params["preview_notif"] = str(n['_id'])
                            del st.query_params["profile_hub"]
                        st.rerun()
                with col_del:
                    if st.button("❌", key=f"deln_{n['_id']}", help="Delete notification"):
                        notifications_col.delete_one({"_id": n['_id']})
                        st.rerun()

    with p_tab3:
        siblings = list(users_col.find({"email": user_data["email"]}))
        st.markdown(f"### Linked Accounts ({len(siblings)}/5)")
        for sib in siblings:
            if sib["username"] == st.session_state.username: st.success(f"👤 {html.escape(sib['username'])} (Active)")
            else:
                if st.button(f"🔄 Switch to {html.escape(sib['username'])}", key=f"sw_{sib['_id']}", use_container_width=True):
                    token = str(uuid.uuid4())
                    users_col.update_one({"username": sib["username"]}, {"$set": {"session_token": token}})
                    st.session_state.username = sib["username"]
                    st.query_params["session"] = token
                    del st.query_params["profile_hub"]; st.rerun()
                    
        if len(siblings) < 5:
            st.info("You can create up to 5 profiles using this email. Create a new account via the signup page using this email address.")
    st.stop()


def render_ai_chat_overlay():
    st.markdown("<style>header {display: none;} .block-container {padding: 3rem 1rem !important;}</style>", unsafe_allow_html=True)
    _, center_col, _ = st.columns([1, 2.5, 1])
    
    with center_col:
        c1, c2 = st.columns([10, 1])
        c1.markdown('<div class="dashboard-title" style="margin-bottom: 5px;">Vault AI</div>', unsafe_allow_html=True)
        if c2.button("✕", key="close_ai_overlay"):
            del st.query_params["ai_chat"]
            st.rerun()
            
        st.markdown("<p class='muted-text'>Ask me directly about your storage, files, or account.</p>", unsafe_allow_html=True)
        
        if "ai_messages" not in st.session_state:
            st.session_state.ai_messages = [{"role": "assistant", "content": "Hello! I can provide exact counts of your photos and albums, or factual information about your vault."}]
        
        chat_container = st.container(height=500)
        with chat_container:
            for msg in st.session_state.ai_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        
        if prompt := st.chat_input("Ask a question about your vault..."):
            st.session_state.ai_messages.append({"role": "user", "content": prompt})
            
            total_files = files_col.count_documents({"username": st.session_state.username})
            total_images = files_col.count_documents({"username": st.session_state.username, "resource_type": "image"})
            total_videos = files_col.count_documents({"username": st.session_state.username, "resource_type": "video"})
            total_folders = folders_col.count_documents({"username": st.session_state.username, "folder_name": {"$ne": "root"}})
            user_doc = users_col.find_one({"username": st.session_state.username})
            
            lower_p = prompt.lower()
            if any(w in lower_p for w in ["how many", "count", "number of", "total"]):
                if any(w in lower_p for w in ["photo", "image", "pic"]): reply = f"You have {total_images} photos."
                elif any(w in lower_p for w in ["video", "vid"]): reply = f"You have {total_videos} videos."
                elif any(w in lower_p for w in ["folder", "album"]): reply = f"You have {total_folders} albums."
                else: reply = f"You have {total_files} items in total."
            elif "latest" in lower_p or "recent" in lower_p:
                 recent_file = files_col.find_one({"username": st.session_state.username}, sort=[("_id", -1)])
                 reply = f"Your most recent file was uploaded on {recent_file['_id'].generation_time.strftime('%b %d, %Y')}." if recent_file else "You haven't uploaded anything yet."
            elif "pin" in lower_p or "location" in lower_p:
                reply = f"Your vault PIN is {user_doc.get('pin_code')}."
            else:
                reply = f"I am your Vault AI. Ask factual questions like 'how many photos do I have?' or 'what is my PIN?'."
                
            st.session_state.ai_messages.append({"role": "assistant", "content": reply})
            st.rerun()
    st.stop()


# --- FULL-SCREEN LIGHTBOX & STORY RENDERERS ---
def render_lightbox_fullscreen(idx, folder_id_str):
    f_id = None if folder_id_str == "root" else ObjectId(folder_id_str)
    files_raw = list(files_col.find({"username": st.session_state.username, "folder_id": f_id}))
    
    pinned_files = sorted([f for f in files_raw if f.get("pin_order", 0) > 0], key=lambda x: x.get("pin_order", 0), reverse=True)
    unpinned_files = [f for f in files_raw if not f.get("pin_order", 0) > 0]
    files = pinned_files + unpinned_files
    
    if not files or idx >= len(files):
        if "lightbox_idx" in st.query_params: del st.query_params["lightbox_idx"]
        st.rerun()

    file = files[idx]
    fid = str(file["_id"])
    is_flagged = file.get("is_flagged", False)
    has_next = "true" if idx < len(files) - 1 else "false"
    has_prev = "true" if idx > 0 else "false"
    
    session_token = html.escape(st.query_params.get('session', ''))
    safe_folder_id = html.escape(folder_id_str)
    next_search = f"?page=app&folder={safe_folder_id}&lightbox_idx={idx + 1}&session={session_token}"
    prev_search = f"?page=app&folder={safe_folder_id}&lightbox_idx={idx - 1}&session={session_token}"
    close_search = f"?page=app&folder={safe_folder_id}&session={session_token}"
    safe_url = html.escape(file['url'])

    blur_css = "filter: blur(30px); transform: scale(1.1);" if is_flagged else ""
    
    # PERMANENT OVERRIDE BUTTON
    reveal_btn = f"<a href='{get_nav_link(page='app', folder=safe_folder_id, action='unflag', file_id=fid)}' target='_self' style='position:absolute; top:80px; left:50%; transform:translateX(-50%); z-index:10000002; padding: 12px 24px; border-radius: 30px; background: rgba(0,0,0,0.8); color: white; border: 1px solid rgba(255,255,255,0.4); font-weight: bold; cursor: pointer; backdrop-filter: blur(10px); box-shadow: 0 4px 15px rgba(0,0,0,0.5); text-decoration:none;'>👁️ Reveal & Mark as Safe</a>" if is_flagged else ""

    media_element = f"<img id='lb-media' src='{safe_url}' style='max-width: 85vw; max-height: 85vh; object-fit: contain; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.6); pointer-events: none; transition: filter 0.3s, transform 0.3s; {blur_css}'>" if file['resource_type'] == "image" else f"<video src='{safe_url}' controls autoplay loop playsinline style='max-width: 85vw; max-height: 85vh; object-fit: contain; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.6);'></video>"
    
    prev_button = f"<a href='{prev_search}' target='_self' class='liquid-btn' style='left: 4%;'>◀</a>" if has_prev == "true" else ""
    next_button = f"<a href='{next_search}' target='_self' class='liquid-btn' style='right: 4%;'>▶</a>" if has_next == "true" else ""

    # DYNAMIC MENU: Includes restored permanent Safe/Sensitive overrides
    action_html = f'''
    <div class="lightbox-menu">
        <div class="lightbox-menu-btn">⋮ Options</div>
        <div class="lightbox-menu-content">
            <a href="{get_nav_link(page="app", folder=safe_folder_id, action="share", file_id=fid)}" target="_self">🔗 Share</a>
            <a href="{get_nav_link(page="app", folder=safe_folder_id, action="pin", file_id=fid)}" target="_self">📌 Pin</a>
            <a href="{get_nav_link(page="app", folder=safe_folder_id, action="cover", file_id=fid)}" target="_self">🖼️ Set Cover</a>
            <a href="{get_nav_link(page="app", folder=safe_folder_id, action="move", file_id=fid)}" target="_self">📂 Move</a>
    '''
    
    if is_flagged:
        action_html += f'<a href="{get_nav_link(page="app", folder=safe_folder_id, action="unflag", file_id=fid)}" target="_self" style="color: #34d399; border-top: 1px solid rgba(255,255,255,0.1); border-bottom: 1px solid rgba(255,255,255,0.1); padding: 12px 12px;">✅ Mark as Safe</a>'
    else:
        action_html += f'<a href="{get_nav_link(page="app", folder=safe_folder_id, action="flag", file_id=fid)}" target="_self" style="color: #f59e0b; border-top: 1px solid rgba(255,255,255,0.1); border-bottom: 1px solid rgba(255,255,255,0.1); padding: 12px 12px;">🚨 Mark Sensitive</a>'

    action_html += f'''
            <a href="{safe_url}" target="_blank" download>⬇️ Download</a>
            <a href="{get_nav_link(page="app", folder=safe_folder_id, action="confirm_delete", file_id=fid)}" target="_self" style="color: #ff3b30;">🗑️ Delete</a>
        </div>
    </div>
    '''

    time_elapsed = time.time() - file.get("tag_time", 0)
    is_locked = bool(file.get("tag")) and (time_elapsed < 86400)
    
    if is_locked:
        react_html = f'<div class="lightbox-react-menu"><a href="{get_nav_link(page="app", folder=safe_folder_id, action="locked_react", file_id=fid)}" target="_self" class="lightbox-menu-btn" style="text-decoration:none; width:auto; padding: 0 15px;">🔒 Locked</a></div>'
    else:
        emojis = ["🥰", "❤️", "🔥", "😂", "👍", "🎉", "✨", "🥺"]
        react_html = '<div class="lightbox-react-menu"><div class="lightbox-menu-btn">➕ React</div><div class="lightbox-react-content">'
        for em in emojis:
            r_link = get_nav_link(page="app", folder=safe_folder_id, lightbox_idx=idx, react=em, file_id=fid)
            react_html += f'<a href="{r_link}" target="_self">{em}</a>'
        react_html += '</div></div>'
        
    current_react = f"<div style='position:absolute; top:25px; left:25px; font-size: 32px; z-index:10000000;'>{html.escape(file.get('tag', ''))}</div>" if file.get("tag") else ""

    lightbox_ui = f"""<div id="lightbox-container" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.9); backdrop-filter: blur(20px); box-sizing: border-box; z-index: 9999999; display: flex; align-items: center; justify-content: center;"><style>header {{display: none !important;}} .liquid-btn {{ position: absolute; display: flex; align-items: center; justify-content: center; width: 60px; height: 60px; border-radius: 50%; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.3); color: white; font-size: 24px; text-decoration: none; cursor: pointer; z-index: 10000000; transition: transform 0.2s ease; }} .liquid-btn:hover {{ transform: scale(1.1); background: rgba(255, 255, 255, 0.3); }} .lightbox-menu {{ position: absolute; top: 25px; right: 100px; z-index: 10000001; padding-bottom:20px; }} .lightbox-react-menu {{ position: absolute; top: 25px; right: 230px; z-index: 10000001; padding-bottom:20px; }} .lightbox-menu-btn {{ height: 40px; border-radius: 20px; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); color: white; font-size: 16px; font-weight:600; display: flex; align-items: center; justify-content: center; cursor: pointer; border: 1px solid rgba(255, 255, 255, 0.3); padding: 0 15px; }} .lightbox-menu-content {{ display: none; position: absolute; top: 50px; right: 0; background: rgba(0,0,0,0.8); backdrop-filter: blur(20px); border-radius: 12px; padding: 10px; width: 160px; flex-direction: column; gap: 5px; border: 1px solid rgba(255,255,255,0.2); }} .lightbox-react-content {{ display: none; position: absolute; top: 50px; right: 0; background: rgba(0,0,0,0.8); backdrop-filter: blur(20px); border-radius: 12px; padding: 10px; width: 220px; flex-wrap: wrap; flex-direction: row; gap: 10px; border: 1px solid rgba(255,255,255,0.2); }} .lightbox-menu:hover .lightbox-menu-content, .lightbox-menu-content:hover {{ display: flex; }} .lightbox-react-menu:hover .lightbox-react-content, .lightbox-react-content:hover {{ display: flex; }} .lightbox-menu-content a {{ color: white; text-decoration: none; padding: 8px 12px; border-radius: 8px; font-size: 15px; font-family: sans-serif; font-weight: 500; display:block; }} .lightbox-menu-content a:hover {{ background: rgba(255, 255, 255, 0.2); }} .lightbox-react-content a {{ font-size: 28px; text-decoration: none; transition: transform 0.2s; cursor: pointer; line-height: 1; }} .lightbox-react-content a:hover {{ transform: scale(1.3); }}</style><a href="{close_search}" target="_self" class="liquid-btn" style="top: 25px; left: 25px;">✕</a>{current_react}{action_html}{react_html} {reveal_btn} <a href="{prev_search}" target="_self" style="position:absolute; top:100px; left:0; width:35vw; height:calc(100vh - 100px); z-index:9999990;"></a><a href="{next_search}" target="_self" style="position:absolute; top:100px; right:0; width:35vw; height:calc(100vh - 100px); z-index:9999990;"></a> {prev_button}{next_button}{media_element}</div>"""
    st.markdown(lightbox_ui.replace('\n', ''), unsafe_allow_html=True)
    st.stop()


def render_story_fullscreen(group_idx, story_idx):
    groups = st.session_state.get("story_groups", [])
    if not groups or group_idx >= len(groups):
        if "story_group" in st.query_params: del st.query_params["story_group"]
        if "story_idx" in st.query_params: del st.query_params["story_idx"]
        st.rerun()
        
    group = groups[group_idx]
    items = group.get("items", [])
    
    if not items or story_idx >= len(items):
        if "story_group" in st.query_params: del st.query_params["story_group"]
        if "story_idx" in st.query_params: del st.query_params["story_idx"]
        st.rerun()

    item = items[story_idx]
    has_next = "true" if story_idx < len(items) - 1 else "false"
    has_prev = "true" if story_idx > 0 else "false"
    
    session_token = html.escape(st.query_params.get('session', ''))
    next_search = f"?page=app&folder=root&story_group={group_idx}&story_idx={story_idx + 1}&session={session_token}"
    prev_search = f"?page=app&folder=root&story_group={group_idx}&story_idx={story_idx - 1}&session={session_token}"
    close_search = f"?page=app&folder=root&session={session_token}"
    safe_url = html.escape(item["url"])

    is_flagged = item.get("is_flagged", False)
    blur_css = "filter: blur(30px); transform: scale(1.1);" if is_flagged else ""
    
    reveal_btn = f"<a href='{get_nav_link(page='app', folder='root', action='unflag', file_id=str(item['_id']))}' target='_self' style='position:absolute; top:80px; left:50%; transform:translateX(-50%); z-index:10000002; padding: 12px 24px; border-radius: 30px; background: rgba(0,0,0,0.8); color: white; border: 1px solid rgba(255,255,255,0.4); font-weight: bold; cursor: pointer; backdrop-filter: blur(10px); box-shadow: 0 4px 15px rgba(0,0,0,0.5); text-decoration:none;'>👁️ Reveal & Mark as Safe</a>" if is_flagged else ""

    media_element = f"<img id='st-media' src='{safe_url}' style='max-width: 100%; max-height: 100%; object-fit: contain; pointer-events: none; transition: filter 0.3s, transform 0.3s; {blur_css}'>" if item['resource_type'] == "image" else f"<video src='{safe_url}' controls autoplay loop playsinline style='max-width: 100%; max-height: 100%; object-fit: contain;'></video>"
    
    prev_button = f"<a href='{prev_search}' target='_self' class='liquid-btn' style='left: 4%;'>◀</a>" if has_prev == "true" else ""
    next_button = f"<a href='{next_search}' target='_self' class='liquid-btn' style='right: 4%;'>▶</a>" if has_next == "true" else ""

    time_elapsed = time.time() - item.get("tag_time", 0)
    is_locked = bool(item.get("tag")) and (time_elapsed < 86400)
    
    if is_locked:
        react_html = f'<div class="story-menu"><a href="{get_nav_link(page="app", folder="root", action="locked_react", file_id=str(item["_id"]))}" target="_self" class="story-menu-btn" style="text-decoration:none; width:auto; padding: 0 15px;">🔒 Locked</a></div>'
    else:
        emojis = ["🥰", "❤️", "🔥", "😂", "👍", "🎉", "✨", "🥺"]
        react_html = '<div class="story-menu"><div class="story-menu-btn">⋮</div><div class="story-menu-content">'
        for em in emojis:
            r_link = get_nav_link(page="app", folder="root", story_group=group_idx, story_idx=story_idx, react=em, file_id=str(item["_id"]))
            react_html += f'<a href="{r_link}" target="_self" class="story-react-btn">{em}</a>'
        react_html += '</div></div>'

    lightbox_ui = f"""
    <div id="lightbox-container" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; box-sizing: border-box; background: #000000; z-index: 9999999; display: flex; flex-direction: column; align-items: center; justify-content: center;">
        <style>
            header {{display: none !important;}}
            .liquid-btn {{ position: absolute; display: flex; align-items: center; justify-content: center; width: 60px; height: 60px; border-radius: 50%; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.3); color: white; font-size: 24px; text-decoration: none; transition: transform 0.2s ease; cursor: pointer; z-index: 10000000; }} 
            .liquid-btn:hover {{ background: rgba(255, 255, 255, 0.3); transform: scale(1.1); color: white; }} 
            .story-menu {{ position: absolute; top: 25px; left: 25px; z-index: 10000001; padding-bottom: 20px; }} 
            .story-menu-btn {{ width: 50px; height: 50px; border-radius: 50%; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.3); color: white; font-size: 24px; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4); }} 
            .story-menu-content {{ display: none; position: absolute; top: 60px; left: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(20px); padding: 15px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.2); width: 220px; flex-wrap: wrap; gap: 12px; }} 
            .story-menu:hover .story-menu-content, .story-menu-content:hover {{ display: flex; flex-direction: row; }} 
            .story-menu::after {{ content: ''; position: absolute; top: 100%; left: 0; width: 100%; height: 20px; }}
            .story-react-btn {{ font-size: 28px; text-decoration: none; transition: transform 0.2s ease; cursor: pointer; line-height: 1; display:inline-block; }} 
            .story-react-btn:hover {{ transform: scale(1.3); }}
        </style>
        <a href="{close_search}" target="_self" class="liquid-btn" style="top: 25px; right: 25px;">✕</a>
        {react_html}
        {reveal_btn}
        <div style="position: absolute; top: 30px; color: white; font-family: sans-serif; font-size: 18px; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.5); z-index: 10000000; margin-left: 80px;">{html.escape(group['label'])}</div>
        <a href="{prev_search}" target="_self" style="position:absolute; top:100px; left:0; width:35vw; height:calc(100vh - 100px); z-index:9999990;"></a>
        <a href="{next_search}" target="_self" style="position:absolute; top:100px; right:0; width:35vw; height:calc(100vh - 100px); z-index:9999990;"></a>
        {prev_button}{next_button}
        <div style="position: absolute; bottom: 30px; color: white; font-family: sans-serif; font-size: 15px; font-weight: 600; background: rgba(255,255,255,0.15); padding: 8px 24px; border-radius: 30px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); letter-spacing: 1px; z-index: 10000000;">{story_idx + 1} / {len(items)}</div>
        {media_element}
    </div>
    """
    st.markdown(lightbox_ui.replace('\n', ''), unsafe_allow_html=True)
    st.stop()


# ================= PUBLIC ROUTING (LOGGED OUT) =================
if not st.session_state.logged_in:
    
    if app_page not in ["landing", "policy", "contact", "auth"]:
        st.query_params["page"] = "landing"
        st.rerun()

    # Z-index strictly 0, pointer events none.
    wallpaper_html = '''
    <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; overflow: hidden; background: #000; pointer-events: none;">
        <div class="live-wallpaper-track" style="display: flex; flex-wrap: wrap; width: 150vw; gap: 8px; transform: rotate(-15deg) scale(1.5); animation: scroll-wallpaper 120s linear infinite;">
    '''
    for i in range(60):
        wallpaper_html += f'<img src="https://picsum.photos/seed/{i+9000}/400/600" style="width: 12vw; height: 18vw; object-fit: cover; border-radius: 12px; opacity: 0.35;" loading="lazy">'
    wallpaper_html += '''
        </div>
    </div>
    <style>@keyframes scroll-wallpaper { 0% { transform: rotate(-15deg) translateY(0); } 100% { transform: rotate(-15deg) translateY(-50%); } }</style>
    '''

    if app_page == "landing":
        landing_html = wallpaper_html + """<style>
div[data-testid="stAppViewBlockContainer"] { background: transparent !important; padding: 0 !important; margin: 0 !important; max-width: 100vw !important; border: none !important; box-shadow: none !important; }
div[data-testid="stAppViewBlockContainer"]::before { display: none !important; }
</style>
<div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 10; display: flex; flex-direction: column; justify-content: center; align-items: center; background: radial-gradient(circle, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0.95) 100%);">
<div style="position: absolute; top: 0; left: 0; width: 100%; padding: 20px 5%; display: flex; justify-content: space-between; align-items: center;">
<a href="?page=landing" target="_self" style="font-size: 24px; font-weight: 800; color: white; text-decoration: none; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">voidememo</a>
<div style="display: flex; gap: 20px; align-items: center;">
<a href="?page=policy" target="_self" style="color: white; text-decoration: none; font-weight: 500; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">Policy</a>
<a href="?page=auth&view=login" target="_self" style="color: white; text-decoration: none; font-weight: 700; background: #0a84ff; padding: 8px 20px; border-radius: 20px; box-shadow: 0 4px 10px rgba(10, 132, 255, 0.4);">Log In</a>
</div>
</div>
<div style="font-size: clamp(3rem, 8vw, 5rem); font-weight: 900; color: white; margin-bottom: 10px; text-shadow: 0 4px 20px rgba(0,0,0,0.5); letter-spacing: -2px;">voidememo</div>
<div style="font-size: clamp(1.1rem, 3vw, 1.5rem); color: #ddd; text-align: center; max-width: 600px; margin-bottom: 3rem; text-shadow: 0 2px 10px rgba(0,0,0,0.5); padding: 0 20px;">The Private Digital Bibliotheca. Access, organize, and protect your media with absolute privacy.</div>
<div style="display: flex; gap: 20px; flex-wrap: wrap; justify-content: center;">
<a href="?page=auth&view=signup" target="_self" style="background: white; color: black; padding: 14px 36px; border-radius: 50px; font-weight: 700; font-size: 16px; text-decoration: none; box-shadow: 0 4px 15px rgba(255,255,255,0.2); transition: transform 0.2s;">Create Free Vault</a>
<a href="?page=auth&view=login" target="_self" style="background: rgba(0,0,0,0.4); color: white; border: 1px solid rgba(255,255,255,0.3); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 14px 36px; border-radius: 50px; font-weight: 700; font-size: 16px; text-decoration: none; transition: transform 0.2s;">Secure Login</a>
</div>
<div style="position: absolute; bottom: 20px; width: 100%; text-align: center; color: rgba(255,255,255,0.6); font-size: 13px;">© 2026 voidememo. All rights reserved.</div>
</div>"""
        st.markdown(landing_html, unsafe_allow_html=True)
        
    else:
        st.markdown(wallpaper_html, unsafe_allow_html=True)

        auth_css = """<style>
.stApp, .main, [data-testid="stAppViewContainer"] { background: transparent !important; }
p, h1, h2, h3, h4, h5, h6, span, label, li { color: #ffffff !important; }
.stTextInput div[data-baseweb="input"], .stDateInput div[data-baseweb="input"], .stTextArea div[data-baseweb="textarea"] { background-color: rgba(255, 255, 255, 0.1) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 12px !important; color: white !important; }
.stTextInput input, .stDateInput input, .stTextArea textarea { color: white !important; padding: 14px 16px !important; font-size: 15px !important; }
::placeholder { color: rgba(255,255,255,0.6) !important; }
.stCheckbox label p { color: white !important; }
.stButton > button[kind="primary"] { background-color: #0a84ff !important; color: #ffffff !important; border: none !important; border-radius: 12px !important; padding: 14px 24px !important; font-weight: 600 !important; width: 100% !important; margin-top: 10px !important; box-shadow: 0 4px 15px rgba(10, 132, 255, 0.4) !important; }

div[data-testid="stAppViewBlockContainer"] { 
    padding: 50px 40px !important; 
    max-width: 480px !important; 
    margin: 12vh auto 5vh auto !important; 
    position: relative; 
    z-index: 10 !important; 
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

div[data-testid="stAppViewBlockContainer"]::before {
    content: "";
    position: absolute;
    inset: 0;
    background-color: rgba(15, 15, 20, 0.75); 
    backdrop-filter: blur(25px); 
    -webkit-backdrop-filter: blur(25px); 
    border: 1px solid rgba(255, 255, 255, 0.15); 
    border-radius: 24px; 
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5); 
    z-index: -1;
}

@media (max-width: 768px) { 
    div[data-testid="stAppViewBlockContainer"] { 
        max-width: 92% !important; 
        margin: 18vh auto 5vh auto !important; 
        padding: 30px 20px !important; 
    } 
}
</style>"""
        st.markdown(auth_css, unsafe_allow_html=True)
        
        if app_page == "policy":
            st.markdown("<style>div[data-testid='stAppViewBlockContainer'] { max-width: 800px !important; }</style>", unsafe_allow_html=True)

        nav_html = """<div style="position: fixed; top: 0; left: 0; width: 100vw; padding: 20px 5%; display: flex; justify-content: space-between; align-items: center; z-index: 999999; background: rgba(0,0,0,0.5); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.1);">
<a href="?page=landing" target="_self" style="font-size: 24px; font-weight: 800; color: white !important; text-decoration: none; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">voidememo</a>
<div style="display: flex; gap: 20px; align-items: center;">
<a href="?page=landing" target="_self" style="color: white !important; text-decoration: none; font-weight: 500; font-size: 15px; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">Home</a>
<a href="?page=policy" target="_self" style="color: white !important; text-decoration: none; font-weight: 500; font-size: 15px; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">Policy</a>
<a href="?page=auth&view=login" target="_self" style="background: #0a84ff; padding: 8px 20px; border-radius: 20px; font-weight: 700; color: white !important; text-decoration: none; box-shadow: 0 4px 10px rgba(10, 132, 255, 0.4);">Log In</a>
</div>
</div>"""
        st.markdown(nav_html, unsafe_allow_html=True)

        if app_page == "policy":
            st.markdown("## voidememo Privacy Policy & Platform Architecture")
            st.markdown("<p style='color: #aaa;'>Effective Date: April 2026</p><hr style='border-color: rgba(255,255,255,0.2);'>", unsafe_allow_html=True)
            st.markdown("""
            ### 1. Introduction and Core Philosophy
            Welcome to voidememo. This document explicitly outlines our data handling procedures, storage architecture, and the mechanics of user interactions.
            """)

        elif auth_view == "login":
            st.markdown('<div style="font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 5px;">Welcome Back</div><div style="font-size: 15px; text-align: center; margin-bottom: 30px; color: #ccc;">Please enter your credentials to log in</div>', unsafe_allow_html=True)
            
            if st.session_state.login_step == 0:
                email = st.text_input("Email", placeholder="Email", label_visibility="collapsed", key="l_email")
                pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="l_pwd")
                is_human = st.checkbox("☑️ I am human (Not a robot)", key="l_human")
                
                st.markdown(f'<div style="text-align: right; margin-top: -10px; margin-bottom: 15px;"><a href="?page=auth&view=forgot" target="_self" style="color: #aaa; font-size: 13px; text-decoration: none; font-weight: 500;">Forgot Password?</a></div>', unsafe_allow_html=True)
                
                if st.button("Request OTP to Login", type="primary", use_container_width=True):
                    if not is_human:
                        st.error("Please confirm you are human to proceed.")
                    elif not email or not pwd:
                        st.error("Please enter email and password.")
                    else:
                        user = users_col.find_one({"email": email.strip().lower(), "password": hash_password(pwd)})
                        if user:
                            with st.spinner("Sending secure OTP to your email..."):
                                otp = str(secrets.randbelow(900000) + 100000)
                                users_col.update_one({"_id": user["_id"]}, {"$set": {"login_otp": otp}})
                                if send_otp_email(email.strip().lower(), otp):
                                    st.session_state.login_email = email.strip().lower()
                                    st.session_state.login_step = 1
                                    st.rerun()
                                else:
                                    st.error("Failed to send email. Ensure SMTP is configured.")
                        else:
                            st.error("Invalid credentials.")
                            
                st.markdown(f'<div style="text-align: center; margin-top: 25px;"><span style="color: #aaa;">New to our platform?</span> <a href="?page=auth&view=signup" target="_self" style="color: #0a84ff; text-decoration: none; font-weight: 600;">Sign Up</a></div>', unsafe_allow_html=True)
                
            elif st.session_state.login_step == 1:
                st.success(f"OTP sent to {html.escape(st.session_state.login_email)}")
                otp_input = st.text_input("Enter 6-Digit OTP", placeholder="123456", label_visibility="collapsed", key="l_otp")
                
                c1, c2 = st.columns(2)
                if c1.button("Verify & Login", type="primary", use_container_width=True):
                    user = users_col.find_one({"email": st.session_state.login_email, "login_otp": otp_input.strip()})
                    if user:
                        users_col.update_one({"_id": user["_id"]}, {"$unset": {"login_otp": ""}})
                        token = str(uuid.uuid4())
                        users_col.update_one({"_id": user["_id"]}, {"$set": {"session_token": token}})
                        st.session_state.logged_in = True
                        st.session_state.username = user["username"]
                        st.session_state.login_step = 0
                        st.query_params["session"] = token
                        st.query_params["page"] = "app"
                        st.query_params["folder"] = "root"
                        if "view" in st.query_params: del st.query_params["view"]
                        st.rerun()
                    else:
                        st.error("Invalid or expired OTP.")
                if c2.button("Cancel", use_container_width=True):
                    st.session_state.login_step = 0
                    st.rerun()

        elif auth_view == "signup":
            st.markdown('<div style="font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 5px;">Sign Up</div><div style="font-size: 15px; text-align: center; margin-bottom: 30px; color: #ccc;">Create an account to build your vault.</div>', unsafe_allow_html=True)
            fname = st.text_input("First Name", placeholder="First Name", label_visibility="collapsed", key="s_fname")
            lname = st.text_input("Last Name", placeholder="Last Name", label_visibility="collapsed", key="s_lname")
            bday = st.date_input("Birthday", value=datetime.date(2000, 1, 1), min_value=datetime.date(1900, 1, 1), label_visibility="collapsed")
            pin_code = st.text_input("PIN / Zip Code", placeholder="Location PIN", label_visibility="collapsed", key="s_pin")
            s_email = st.text_input("Email", placeholder="you@example.com", label_visibility="collapsed", key="s_email")
            s_phone = st.text_input("Phone Number", placeholder="Phone Number (Required for multiple profiles)", label_visibility="collapsed", key="s_phone")
            s_pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="s_pwd")
            s_agree = st.checkbox("☑️ I agree to the Privacy Policy and Terms of Service", key="s_agree")
            
            if st.button("Sign Up", type="primary", use_container_width=True):
                if not s_agree:
                    st.error("You must agree to the Privacy Policy to create a vault.")
                elif not s_email or not s_pwd or not fname or not pin_code: 
                    st.error("Please fill all core required fields.")
                else:
                    result = register(s_email, s_pwd, fname, lname, bday, pin_code, s_phone)
                    if result == "MAX_ACCOUNTS": st.error("Maximum of 5 profiles allowed per email address.")
                    elif result == "PHONE_REQUIRED": st.error("Phone number is required when creating multiple accounts with the same email.")
                    elif result:
                        token = str(uuid.uuid4())
                        users_col.update_one({"username": result}, {"$set": {"session_token": token}})
                        st.session_state.logged_in = True; st.session_state.username = result
                        st.query_params["session"] = token; st.query_params["page"] = "app"; st.query_params["folder"] = "root"
                        if "view" in st.query_params: del st.query_params["view"]
                        st.rerun()
            st.markdown(f'<div style="text-align: center; margin-top: 25px;"><span style="color: #aaa;">Already have an account?</span> <a href="?page=auth&view=login" target="_self" style="color: #0a84ff; text-decoration: none; font-weight: 600;">Sign In</a></div>', unsafe_allow_html=True)

        elif auth_view == "forgot":
            st.markdown('<div style="font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 5px;">Forgot Password</div>', unsafe_allow_html=True)
            if st.session_state.reset_step == 0:
                st.markdown('<div style="font-size: 15px; text-align: center; margin-bottom: 30px; color: #ccc;">Please enter your registered email</div>', unsafe_allow_html=True)
                f_email = st.text_input("Email", placeholder="Email", label_visibility="collapsed", key="f_email")
                if st.button("Reset Password", type="primary", use_container_width=True):
                    if f_email:
                        clean_email = str(f_email).strip().lower()
                        user = users_col.find_one({"email": clean_email})
                        if user:
                            with st.spinner("Sending OTP..."):
                                otp = str(secrets.randbelow(900000) + 100000)
                                exp_time = time.time() + 600 
                                users_col.update_many({"email": clean_email}, {"$set": {"reset_otp": otp, "reset_otp_exp": exp_time}})
                                if send_otp_email(clean_email, otp):
                                    st.session_state.reset_step = 1; st.session_state.reset_email = clean_email; st.rerun()
                        else: st.error("No account found with that email.")
            elif st.session_state.reset_step == 1:
                st.markdown('<div style="font-size: 15px; text-align: center; margin-bottom: 30px; color: #ccc;">Enter the 6-digit code sent to your email</div>', unsafe_allow_html=True)
                st.success(f"OTP sent to {html.escape(st.session_state.reset_email)}")
                entered_otp = st.text_input("Enter 6-Digit OTP", placeholder="123456", label_visibility="collapsed", key="entered_otp")
                new_pwd = st.text_input("Enter New Password", type="password", placeholder="New Password", label_visibility="collapsed", key="new_pwd")
                if st.button("Confirm Reset", type="primary", use_container_width=True):
                    if len(new_pwd) < 6: st.error("Password must be at least 6 characters.")
                    else:
                        user = users_col.find_one({"email": st.session_state.reset_email})
                        if user and user.get("reset_otp") == str(entered_otp).strip() and time.time() < user.get("reset_otp_exp", 0):
                            users_col.update_many({"email": st.session_state.reset_email}, {"$set": {"password": hash_password(new_pwd), "reset_otp": "", "reset_otp_exp": 0}})
                            st.success("Password updated!"); time.sleep(1.5)
                            st.session_state.reset_step = 0; st.session_state.reset_email = ""
                            st.query_params["view"] = "login"; st.rerun()
                        else: st.error("Invalid or expired token!")
            st.markdown(f'<div style="text-align: center; margin-top: 25px;"><span style="color: #aaa;">Remembered your password?</span> <a href="?page=auth&view=login" target="_self" style="color: #0a84ff; text-decoration: none; font-weight: 600;">Log In</a></div>', unsafe_allow_html=True)

# ================= DASHBOARD APP (LOGGED IN) =================
else:
    def inject_dashboard_css():
        dash_css = """<style>
:root { --bg-app: #f2f2f7; --bg-card: #ffffff; --bg-sidebar: #f2f2f7; --bg-input: #ffffff; --text-primary: #000000; --text-secondary: #8e8e93; --border: #d1d1d6; --accent: #007aff; --btn-hover: #e5e5ea; }
@media (prefers-color-scheme: dark) { :root { --bg-app: #000000; --bg-card: #1c1c1e; --bg-sidebar: #000000; --bg-input: #1c1c1e; --text-primary: #ffffff; --text-secondary: #8e8e93; --border: #38383a; --accent: #0a84ff; --btn-hover: #2c2c2e; } }
.stApp, [data-testid="stAppViewContainer"] { background-color: var(--bg-app) !important; color: var(--text-primary) !important; }
p, h1, h2, h3, h4, h5, h6, span, label, li { color: var(--text-primary) !important; transition: color 0.3s ease; }

div[data-testid="stAppViewBlockContainer"] { 
    max-width: 100vw !important; padding: 20px 5% 80px 5% !important; margin: 0 !important; background: transparent !important; border: none !important; box-shadow: none !important; backdrop-filter: none !important;
}
div[data-testid="stAppViewBlockContainer"]::before { display: none !important; content: none !important; }

.top-nav { display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; position: relative; z-index: 9999999 !important; pointer-events: auto !important; margin-bottom: 20px; }
.brand-logo { font-size: 24px; font-weight: 800; color: var(--accent) !important; letter-spacing: 0.5px; text-decoration: none; position:relative; z-index:100; }
.dashboard-title { font-size: 32px; font-weight: 800; color: var(--text-primary); margin: 0; }
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
.album-card { margin-bottom: 15px; transition: transform 0.2s ease; position: relative; }
.album-card:hover { transform: scale(1.02); }
.folder-card { position: relative; width: 100%; aspect-ratio: 1/1; border-radius: 12px; background-color: var(--bg-card); border: 1px solid var(--border); display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 8px; transition: transform 0.2s ease; }
.folder-card:hover { transform: scale(1.02); }
.media-container-wrapper { position: relative; margin-bottom: 15px; cursor: pointer; }
.media-container-wrapper:hover .square-media { transform: scale(1.02); }
.square-media { width: 100%; aspect-ratio: 1/1; overflow: hidden; transition: transform 0.2s; border-radius: 50% !important; box-shadow: 0 4px 10px rgba(0,0,0,0.1); background: var(--bg-card); border: 1px solid var(--border); }
.square-media img, .square-media video { width: 100%; height: 100%; object-fit: cover; display: block; }
[data-testid="column"] { position: relative; }
.folder-options-btn [data-testid="stPopover"] > button { background-color: var(--bg-card) !important; color: var(--text-primary) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; height: 38px !important; padding: 0 15px !important; font-weight: 600 !important; box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important; }
.folder-options-btn [data-testid="stPopover"] > button:hover { background-color: var(--btn-hover) !important; }
[data-testid="stFileUploader"] > div { background-color: var(--bg-card) !important; border: 1px dashed var(--border) !important; border-radius: 16px !important; padding: 20px !important; }
.profile-header-widget { display: inline-flex; align-items: center; gap: 12px; background: transparent; padding: 6px 12px; border-radius: 50px; transition: transform 0.2s; cursor: pointer; color: var(--text-primary) !important; position: relative; text-decoration: none; }
.profile-header-widget:hover { transform: scale(1.02); text-decoration: none; }
.profile-header-widget img { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; }
.profile-header-widget span { font-weight: 600; font-size: 15px;}
.profile-notif-dot { position: absolute; top: 2px; right: 8px; width: 11px; height: 11px; background-color: #ff3b30; border-radius: 50%; border: 1.5px solid var(--bg-card); box-shadow: 0 0 5px rgba(255, 59, 48, 0.5); z-index: 20; }
.custom-footer { margin-top: 50px; width: 100%; text-align: center; padding: 20px 0; border-top: 1px solid var(--border); color: var(--text-secondary); font-size: 13px; clear: both; }
@media (max-width: 768px) { .top-nav { padding: 15px 10px; flex-direction: column; gap: 15px; justify-content: center; text-align: center; } .brand-logo { font-size: 28px; margin-bottom: 10px;} div[data-testid="stAppViewBlockContainer"] { padding-top: 1rem !important; } }
</style>"""
        st.markdown(dash_css, unsafe_allow_html=True)

    inject_dashboard_css()

    dialog_rendered = False

    if "share_folder" in st.query_params and not dialog_rendered: 
        render_share_media_overlay(st.query_params["share_folder"], mode="folder")
        dialog_rendered = True
    elif "ai_chat" in st.query_params and not dialog_rendered: 
        render_ai_chat_overlay()
        dialog_rendered = True
    elif "profile_hub" in st.query_params and not dialog_rendered: 
        render_profile_hub_overlay()
        dialog_rendered = True
    elif "preview_notif" in st.query_params and not dialog_rendered: 
        render_preview_shared_overlay(st.query_params["preview_notif"])
        dialog_rendered = True
    elif "story_group" in st.query_params and "story_idx" in st.query_params and not dialog_rendered: 
        render_story_fullscreen(int(st.query_params["story_group"]), int(st.query_params["story_idx"]))
        dialog_rendered = True
    elif "lightbox_idx" in st.query_params and not dialog_rendered: 
        render_lightbox_fullscreen(int(st.query_params["lightbox_idx"]), st.query_params.get("folder", "root"))
        dialog_rendered = True
    
    if st.session_state.get("pending_share") and not dialog_rendered:
        render_share_media_overlay(st.session_state.pending_share, mode="single")
        st.session_state.pending_share = None
        dialog_rendered = True

    if st.session_state.get("pending_delete") and not dialog_rendered:
        try:
            file_to_del = files_col.find_one({"_id": ObjectId(st.session_state.pending_delete)})
            if file_to_del:
                delete_file_dialog(file_to_del["_id"], file_to_del["public_id"], file_to_del["resource_type"])
        except Exception: pass
        st.session_state.pending_delete = None
        dialog_rendered = True
        
    if st.session_state.get("pending_move") and not dialog_rendered:
        move_media_dialog(st.session_state.pending_move)
        st.session_state.pending_move = None
        dialog_rendered = True

    if st.session_state.get("pending_locked_react") and not dialog_rendered:
        locked_reaction_dialog(st.session_state.pending_locked_react)
        st.session_state.pending_locked_react = None
        dialog_rendered = True

    user_data = users_col.find_one({"username": st.session_state.username})
    root_folder = folders_col.find_one({"username": st.session_state.username, "parent_id": None})
    try: actual_folder_id = ObjectId(active_folder) if active_folder != "root" else root_folder["_id"] if root_folder else None
    except InvalidId: actual_folder_id = root_folder["_id"] if root_folder else None

    current = folders_col.find_one({"_id": actual_folder_id})
    is_root = current is None or current.get("parent_id") is None

    unscanned_files = list(files_col.find({"username": st.session_state.username, "resource_type": "image", "is_flagged": {"$exists": False}}).limit(15))
    if unscanned_files:
        with st.spinner("🤖 Auto-scanning media with Pure AI Engine..."):
            for f in unscanned_files:
                try:
                    resp = requests.get(f["url"], timeout=5)
                    if resp.status_code == 200:
                        safe = is_safe_content(resp.content, safety_model)
                        files_col.update_one({"_id": f["_id"]}, {"$set": {"is_flagged": not safe}})
                except: pass
            st.rerun()

    prof_pic = user_data.get("profile_photo") or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
    display_name = html.escape(user_data.get("first_name", st.session_state.username))
    
    ai_link = get_nav_link(page="app", folder=active_folder, ai_chat=1)
    home_link = get_nav_link(page="app", folder="root")
    prof_link = get_nav_link(page="app", folder=active_folder, profile_hub=1)

    unread_notifs = list(notifications_col.find({"username": st.session_state.username, "is_read": False}).sort("created_at", -1))
    notif_dot_html = '<div class="profile-notif-dot"></div>' if unread_notifs else ''

    prof_widget = f'<a href="{prof_link}" target="_self" class="profile-header-widget"><img src="{html.escape(prof_pic)}"><span>{display_name}</span>{notif_dot_html}</a>' if is_root else ""

    header_html = f'''
    <div class="top-nav">
        <a href="{home_link}" target="_self" class="brand-logo">voidememo</a>
        <div style="display:flex; gap:15px; align-items:center;">
            <a href="{ai_link}" target="_self" class="profile-header-widget" style="background:var(--accent); color:white!important; border:none; box-shadow:0 4px 12px rgba(10,132,255,0.3);">
                <span>✨ Ask AI</span>
            </a>
            {prof_widget}
        </div>
    </div>
    '''
    st.markdown(header_html.replace('\n', ''), unsafe_allow_html=True)
    st.write("<br>", unsafe_allow_html=True) 

    # VISUAL WARNING IF AI CRASHES / OFFLINE
    if safety_model is None:
        st.error("🚨 AI MODEL OFFLINE: 'custom_nsfw_model.h5' could not be loaded. Ensure the exact file is uploaded via Git LFS to your GitHub repository and is not corrupted. The filter is currently bypassed.")
    
    if is_root and st.session_state.story_groups:
        st.markdown(f'<h3 style="margin-left: 40px; margin-bottom: 10px;">Stories</h3>', unsafe_allow_html=True)
        story_html = '<div class="story-wrapper" style="margin-left: 40px;">'
        colors = ["linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%)", "var(--border)", "var(--accent)", "#34d399"]
        
        for g_idx, group in enumerate(st.session_state.story_groups):
            if not group["items"]: continue
            c = colors[g_idx % len(colors)]
            first_media = group["items"][0]
            safe_url = html.escape(first_media["url"])
            safe_label = html.escape(group["label"])
            
            thumb_html = f'<img src="{safe_url}">'
            if first_media.get("resource_type") == "video":
                vid_thumb = safe_url.replace(".mp4", ".jpg").replace(".webm", ".jpg").replace(".mov", ".jpg")
                thumb_html = f'<img src="{vid_thumb}" onerror="this.src=\'https://cdn-icons-png.flaticon.com/512/2985/2985655.png\'">'
            
            story_html += f'<a href="{get_nav_link("app", folder="root", story_group=g_idx, story_idx=0)}" target="_self" class="story-link"><div class="story-item"><div class="story-ring" style="background: {c};"><div class="story-inner">{thumb_html}</div></div><div class="story-label">{safe_label}</div></div></a>'
        
        story_html += '</div>'
        st.markdown(story_html.replace('\n', ''), unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)

    title_text = "Personal Albums" if is_root else html.escape(current["folder_name"])
    if not is_root and current.get("is_locked"): title_text += " 🔒"

    _, main_col, _ = st.columns([1, 12, 1])
    with main_col:
        folders = list(folders_col.find({"username": st.session_state.username, "parent_id": actual_folder_id}))
        files_raw = list(files_col.find({"username": st.session_state.username, "folder_id": actual_folder_id}))
        
        pinned_files = sorted([f for f in files_raw if f.get("pin_order", 0) > 0], key=lambda x: x.get("pin_order", 0), reverse=True)
        unpinned_files = [f for f in files_raw if not f.get("pin_order", 0) > 0]
        files = pinned_files + unpinned_files

        c_title, c_actions = st.columns([10, 2])
        
        if is_root:
            c_title.markdown(f'<h2 style="margin:0;">{title_text}</h2>', unsafe_allow_html=True)
        else:
            c_title.markdown(f'<div style="display:flex; align-items:center; gap: 15px;"><a href="{home_link}" target="_self" style="text-decoration:none; font-weight: 600; color: var(--accent); font-size: 20px;">←</a><h2 style="margin:0;">{title_text}</h2></div>', unsafe_allow_html=True)
        
        with c_actions:
            if is_root:
                with st.popover("➕ Create Album"):
                    new_folder = st.text_input("New Album", placeholder="Album Name...", label_visibility="collapsed", key=f"folder_input_{st.session_state.folder_key}")
                    if st.button("Create Album", type="primary"):
                        clean_folder_name = str(new_folder).strip()
                        if clean_folder_name:
                            folders_col.insert_one({"username": st.session_state.username, "folder_name": clean_folder_name, "parent_id": actual_folder_id, "cover_photo": "", "is_locked": False, "api_key": "", "api_enabled": False})
                            st.session_state.folder_key += 1; st.rerun()
            else:
                st.markdown('<div class="folder-options-btn" style="display: flex; justify-content: flex-end;">', unsafe_allow_html=True)
                with st.popover("⋮ Options", use_container_width=True):
                    st.markdown("**Album Management**")
                    if st.button("✏️ Rename Album", key=f"edit_{current['_id']}", use_container_width=True): rename_folder_dialog(current["_id"], current["folder_name"])
                    if st.button("🗑 Delete Album", key=f"del_fold_{current['_id']}", use_container_width=True): delete_folder_dialog(current["_id"], current["folder_name"])
                    
                    if st.button("🔍 Find & Remove Duplicates", key=f"dup_{current['_id']}", use_container_width=True): 
                        find_duplicates_dialog(current["_id"])
                        
                    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                    
                    st.markdown("**Developer & API**")
                    if st.button("⚡ Developer API", key=f"api_{current['_id']}", use_container_width=True): developer_api_dialog(current["_id"])
                    
                    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                    st.markdown("**Sharing & Privacy**")
                    
                    if st.button("🔗 Share Media Batch", key=f"share_folder_{current['_id']}", use_container_width=True):
                        st.query_params["share_folder"] = str(current['_id']); st.rerun()
                        
                    is_locked = current.get("is_locked", False)
                    lock_btn_txt = "🔓 Make Public" if is_locked else "🔒 Lock Album"
                    if st.button(lock_btn_txt, key=f"lock_fold_{current['_id']}", use_container_width=True):
                        folders_col.update_one({"_id": current["_id"]}, {"$set": {"is_locked": not is_locked}}); st.rerun()
                    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                    
                    st.markdown("**Add Content**")
                    with st.form("upload_content_form", clear_on_submit=True):
                        uploaded_files = st.file_uploader("Upload Media", accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}", label_visibility="collapsed")
                        
                        submit_button = st.form_submit_button("Sync Files", type="primary", use_container_width=True)
                        if submit_button and uploaded_files:
                            allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "video/mp4", "video/webm", "video/quicktime"]
                            with st.spinner("Analyzing and Syncing to cloud..."):
                                for file in uploaded_files:
                                    if file.type not in allowed_types: continue
                                    r_type = "video" if file.type.startswith("video") else "image"
                                    
                                    file_bytes = file.getvalue()
                                    file.seek(0)
                                    
                                    is_flagged = False
                                    if r_type == "image":
                                        is_flagged = not is_safe_content(file_bytes, safety_model)
                                        if is_flagged:
                                            st.warning(f"⚠️ '{html.escape(file.name)}' was flagged by AI as sensitive. It has been synced and blurred.")
                                        
                                    try:
                                        res = cloudinary.uploader.upload_large(file, resource_type=r_type, chunk_size=20000000) if file.size > 50000000 else cloudinary.uploader.upload(file, resource_type=r_type)
                                        files_col.insert_one({"username": st.session_state.username, "folder_id": current["_id"], "filename": html.escape(file.name), "url": res["secure_url"], "public_id": res["public_id"], "resource_type": r_type, "is_flagged": is_flagged, "tag": "", "tag_time": 0})
                                    except Exception as e: 
                                        st.error(f"Failed to upload {html.escape(file.name)}.")
                                        
                            st.session_state.uploader_key += 1; st.rerun()
                            
                st.markdown('</div>', unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)

        if not folders and not files:
            st.markdown('<p class="muted-text" style="text-align:center; margin-top: 50px;">This album is empty.</p>', unsafe_allow_html=True)

        if folders:
            f_cols = st.columns(4)
            for i, folder in enumerate(folders):
                with f_cols[i % 4]:
                    cover = folder.get("cover_photo")
                    folder_url = get_nav_link("app", folder=str(folder["_id"]))
                    lock_indicator = '<div style="position:absolute; top:8px; right:8px; font-size:16px; background: rgba(0,0,0,0.5); padding: 4px; border-radius: 50%;">🔒</div>' if folder.get("is_locked") else ""
                    safe_fname = html.escape(folder['folder_name'])
                    
                    if cover:
                        html_str = f'<a href="{folder_url}" target="_self" class="album-link" style="text-decoration: none;"><div class="album-card"><div style="width: 100%; aspect-ratio: 1/1; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid var(--border);">{lock_indicator}<img src="{html.escape(cover)}" style="width: 100%; height: 100%; object-fit: cover;"></div><div style="font-weight: 600; font-size: 15px; color: var(--text-primary); text-align: left; padding-left: 4px; margin-top: 8px;">{safe_fname}</div></div></a>'
                    else:
                        html_str = f'<a href="{folder_url}" target="_self" class="album-link" style="text-decoration: none;"><div style="margin-bottom: 15px;"><div class="folder-card">{lock_indicator}<div style="font-size: 40px;">📁</div></div><div style="font-weight: 600; font-size: 15px; color: var(--text-primary); text-align: left; padding-left: 4px; margin-top: 8px;">{safe_fname}</div></div></a>'
                    st.markdown(html_str.replace('\n', ''), unsafe_allow_html=True)

        if files:
            st.write("<br>", unsafe_allow_html=True)
            img_cols = st.columns(4)
            for i, file in enumerate(files):
                with img_cols[i % 4]:
                    st.markdown('<div class="media-container-wrapper">', unsafe_allow_html=True)
                    
                    safe_tag = html.escape(file.get("tag", ""))
                    emoji_badge = f'<div style="position:absolute; top:5px; left:5px; font-size:18px; z-index:10; background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(5px); padding: 2px 6px; border-radius: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); pointer-events: none;">{safe_tag}</div>' if safe_tag else ""
                    pin_badge = '<div style="position:absolute; top:5px; right:5px; font-size:16px; z-index:10; text-shadow: 0 2px 4px rgba(0,0,0,0.5); pointer-events: none;">📌</div>' if file.get("pin_order", 0) > 0 else ""
                    
                    session_token = html.escape(st.query_params.get('session', ''))
                    safe_folder_id = html.escape(str(actual_folder_id) if actual_folder_id else 'root')
                    lb_url = f"?page=app&folder={safe_folder_id}&lightbox_idx={i}&session={session_token}"
                    safe_url = html.escape(file["url"])
                    is_flagged = file.get("is_flagged", False)
                    
                    media_html = f'<a href="{lb_url}" target="_self" style="text-decoration:none; display: block; position: relative;">'
                    if file["resource_type"] == "image":
                        if is_flagged:
                            media_html += f'<div class="square-media" style="position:relative;">{emoji_badge}{pin_badge}<img src="{safe_url}" style="filter: blur(25px); transform: scale(1.1);"><div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:40px; z-index:20; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">🙈</div></div>'
                        else:
                            media_html += f'<div class="square-media" style="position:relative;">{emoji_badge}{pin_badge}<img src="{safe_url}"></div>'
                    else:
                        media_html += f'<div class="square-media" style="position:relative;">{emoji_badge}{pin_badge}<video src="{safe_url}" autoplay loop muted playsinline style="width: 100%; height: 100%; object-fit: cover;"></video><div style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:5;"></div></div>'
                    media_html += '</a>'
                    
                    st.markdown(media_html.replace('\n', ''), unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
        st.markdown('<div class="custom-footer">© 2026 voidememo. All rights reserved.</div>', unsafe_allow_html=True)