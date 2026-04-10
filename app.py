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

# ---------------- UI CONFIG ----------------
st.set_page_config(page_title="voidememo Vault", page_icon="🌐", layout="wide", initial_sidebar_state="collapsed")

# ---------------- CONFIG (PRODUCTION SAFE) ----------------
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

# ---------------- UTILS & SECURITY / AUTHENTICATION ----------------
def hash_password(password):
    pwd_str = str(password).strip()
    pepper = st.secrets.get("APP_PEPPER", "")
    return hashlib.sha256((pwd_str + pepper).encode()).hexdigest()

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
    folders_col.insert_one({"username": safe_username, "folder_name": "root", "parent_id": None, "is_locked": False})
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
        msg['Subject'] = "voidememo - Password Reset Security Code"
        body = f"Hello,\n\nYou requested a password reset. Your secure 6-digit code is: {otp}\n\nThis code will expire in 10 minutes. If you did not request this, secure your account immediately."
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


# ---------------- NATIVE GESTURE ROUTING SYSTEM ----------------
def get_nav_link(page=None, view=None, folder=None, story_group=None, story_idx=None, lightbox_idx=None, profile_hub=None, ai_chat=None, react=None):
    params = []
    if page is not None: params.append(f"page={page}")
    if view is not None: params.append(f"view={view}")
    if folder is not None: params.append(f"folder={folder}")
    if story_group is not None: params.append(f"story_group={story_group}")
    if story_idx is not None: params.append(f"story_idx={story_idx}")
    if lightbox_idx is not None: params.append(f"lightbox_idx={lightbox_idx}")
    if profile_hub is not None: params.append(f"profile_hub={profile_hub}")
    if ai_chat is not None: params.append(f"ai_chat={ai_chat}")
    if react is not None: params.append(f"react={react}")
    if "session" in st.query_params:
        params.append(f"session={html.escape(st.query_params['session'])}")
    return "?" + "&".join(params)

app_page = st.query_params.get("page", "landing")
auth_view = st.query_params.get("view", "login")
active_folder = st.query_params.get("folder", "root")

defaults = {
    "logged_in": False, "username": "", "reset_step": 0, "reset_email": "",
    "uploader_key": 0, "folder_key": 0, "story_groups": []
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

# --- HANDLE STORY REACTIONS ---
if st.session_state.logged_in and "react" in st.query_params and "story_group" in st.query_params and "story_idx" in st.query_params:
    try:
        s_grp = int(st.query_params["story_group"])
        s_idx = int(st.query_params["story_idx"])
        if s_grp < len(st.session_state.story_groups):
            items = st.session_state.story_groups[s_grp]["items"]
            if s_idx < len(items):
                file_id = items[s_idx]["_id"]
                files_col.update_one({"_id": file_id}, {"$set": {"tag": st.query_params["react"], "tag_time": time.time()}})
    except Exception:
        pass
    del st.query_params["react"]
    st.rerun()


# ---------------- TIME-SEEDED DETERMINISTIC ENGINE ----------------
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
            if f.get("tag"): favorites.append(f)
            if age_days > 30: throwback.append(f)
                
        if recent:
            recent.sort(key=lambda x: x["_id"].generation_time, reverse=True)
            story_groups.append({"label": "Recent Highlights", "items": recent[:6]})
        if throwback:
            random.shuffle(throwback)
            story_groups.append({"label": "Memory Lane", "items": throwback[:6]})
        if favorites:
            random.shuffle(favorites)
            # Custom requested heading
            story_groups.append({"label": "This week your fav ⭐", "items": favorites[:6]})
            
        random_media = all_user_media[:]
        random.shuffle(random_media)
        story_groups.append({"label": "Discover", "items": random_media[:6]})
            
    st.session_state.story_groups = story_groups
    random.seed() 


# ---------------- STANDARD POPUP DIALOGS ----------------
@st.dialog("⚠️ Confirm Deletion")
def delete_folder_dialog(folder_id, folder_name):
    st.write(f"Are you sure you want to completely delete the album **{html.escape(folder_name)}** and everything inside it?")
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
        clean_name = str(new_name).strip()
        if clean_name and clean_name != current_name:
            folders_col.update_one({"_id": folder_id}, {"$set": {"folder_name": clean_name}})
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()

@st.dialog("⚠️ Confirm Deletion")
def delete_file_dialog(file_id, public_id, resource_type):
    st.write("Are you sure you want to delete this media?")
    c1, c2 = st.columns(2)
    if c1.button("Yes, Delete It", type="primary", use_container_width=True):
        if files_col.count_documents({"public_id": public_id}) <= 1:
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


# ---------------- APP FULL-SCREEN DIALOGS (HUB & AI) ----------------
@st.dialog("👤 Profile Hub")
def render_profile_hub_fullscreen():
    st.markdown("""<style>
        div[data-testid="stDialog"] > div[role="dialog"] {
            width: 100vw !important; max-width: 100vw !important;
            height: 100vh !important; max-height: 100vh !important;
            margin: 0 !important; border-radius: 0 !important;
            background: var(--bg-app) !important; padding: 40px 5% !important;
        }
        div[data-testid="stDialog"] button[aria-label="Close"] { top: 20px; right: 20px; transform: scale(1.5); }
    </style>""", unsafe_allow_html=True)
    
    user_data = users_col.find_one({"username": st.session_state.username})
    st.markdown('<div class="dashboard-title" style="margin-bottom: 20px;">Profile Hub</div>', unsafe_allow_html=True)
    
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
                safe_bio = html.escape(str(bio).strip())
                safe_pin = html.escape(str(new_pin).strip())
                safe_phone = html.escape(str(new_phone).strip())
                
                updates = {"bio": safe_bio, "pin_code": safe_pin, "phone_number": safe_phone}
                if pic:
                    res = cloudinary.uploader.upload(pic)
                    updates["profile_photo"] = res["secure_url"]
                    
                clean_username = html.escape(str(new_username).strip())
                if clean_username != st.session_state.username:
                    if users_col.find_one({"username": clean_username}):
                        st.error("Username already taken.")
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
        
        with c2:
            st.markdown("### Reaction Analytics")
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
                    safe_stat_id = html.escape(stat["_id"])
                    scols[i % 2].metric(label="React", value=safe_stat_id, delta=f"{stat['count']} times")
            else:
                st.info("You haven't reacted to any memories yet!")
                
            st.markdown("<hr style='margin: 30px 0;'>", unsafe_allow_html=True)
            if st.button("🚪 Logout Complete Session", use_container_width=True):
                users_col.update_one({"username": st.session_state.username}, {"$set": {"session_token": ""}})
                st.session_state.logged_in = False; st.session_state.username = ""
                st.query_params.clear(); st.rerun()

    with p_tab2:
        st.markdown("### Your Notifications")
        unread_notifs = list(notifications_col.find({"username": st.session_state.username, "is_read": False}).sort("created_at", -1))
        if not unread_notifs:
            st.info("You are all caught up! No new notifications.")
        else:
            for n in unread_notifs:
                safe_sender = html.escape(n["sender"])
                if st.button(f"📩 {safe_sender} {n['message']}", key=f"nbtn_{n['_id']}", use_container_width=True):
                    if n.get("type") in ["share", "share_reaction"]:
                        st.query_params["preview_notif"] = str(n['_id'])
                    else:
                        notifications_col.update_one({"_id": n['_id']}, {"$set": {"is_read": True}})
                    del st.query_params["profile_hub"]
                    st.rerun()

    with p_tab3:
        siblings = list(users_col.find({"email": user_data["email"]}))
        st.markdown(f"### Linked Accounts ({len(siblings)}/5)")
        st.markdown(f"<p class='muted-text'>Profiles associated with: {html.escape(user_data['email'])}</p>", unsafe_allow_html=True)
        
        for sib in siblings:
            is_current = (sib["username"] == st.session_state.username)
            sib_name = html.escape(sib["username"])
            
            if is_current:
                st.success(f"👤 {sib_name} (Active)")
            else:
                if st.button(f"🔄 Switch to {sib_name}", key=f"sw_{sib['_id']}", use_container_width=True):
                    token = str(uuid.uuid4())
                    users_col.update_one({"username": sib["username"]}, {"$set": {"session_token": token}})
                    st.session_state.username = sib["username"]
                    st.query_params["session"] = token
                    del st.query_params["profile_hub"]
                    st.rerun()
                    
        if len(siblings) < 5:
            st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
            st.info("You can create up to 5 completely separate vaults using this exact same email address. Just completely log out, go back to the Sign Up page, enter this email, and provide your phone number for validation.")

    st.write("<br><br>", unsafe_allow_html=True)
    if st.button("Close Profile Hub", use_container_width=True):
        del st.query_params["profile_hub"]
        st.rerun()


@st.dialog("✨ AI Assistant")
def render_ai_chat_fullscreen():
    # Centered chat interface inside full screen
    st.markdown("""<style>
        div[data-testid="stDialog"] > div[role="dialog"] {
            width: 100vw !important; max-width: 100vw !important;
            height: 100vh !important; max-height: 100vh !important;
            margin: 0 !important; border-radius: 0 !important;
            background: var(--bg-app) !important; padding: 20px 0 !important;
        }
        div[data-testid="stDialog"] button[aria-label="Close"] { top: 20px; right: 20px; transform: scale(1.5); }
    </style>""", unsafe_allow_html=True)
    
    _, center_col, _ = st.columns([1, 3, 1])
    
    with center_col:
        st.markdown('<div class="dashboard-title" style="margin-bottom: 5px;">Vault AI</div>', unsafe_allow_html=True)
        st.markdown("<p class='muted-text'>Ask me anything about your files, storage, account, or recent shares.</p>", unsafe_allow_html=True)
        
        if "ai_messages" not in st.session_state:
            st.session_state.ai_messages = [{"role": "assistant", "content": "Hello! I am your vault AI. How can I assist you today?"}]
        
        chat_container = st.container(height=500)
        with chat_container:
            for msg in st.session_state.ai_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        
        if prompt := st.chat_input("Ask a question about your vault..."):
            st.session_state.ai_messages.append({"role": "user", "content": prompt})
            
            # Exact, specific, short data-parsing logic
            total_files = files_col.count_documents({"username": st.session_state.username})
            total_images = files_col.count_documents({"username": st.session_state.username, "resource_type": "image"})
            total_videos = files_col.count_documents({"username": st.session_state.username, "resource_type": "video"})
            total_folders = folders_col.count_documents({"username": st.session_state.username, "folder_name": {"$ne": "root"}})
            
            lower_p = prompt.lower()
            if any(w in lower_p for w in ["how many", "count", "number of", "total", "how much"]):
                if any(w in lower_p for w in ["photo", "image", "pic"]):
                    reply = f"You have {total_images} photos."
                elif any(w in lower_p for w in ["video", "vid"]):
                    reply = f"You have {total_videos} videos."
                elif any(w in lower_p for w in ["folder", "album"]):
                    reply = f"You have {total_folders} albums."
                else:
                    reply = f"You have {total_files} items in total."
                    
            elif "latest" in lower_p or "recent" in lower_p and "upload" in lower_p:
                 recent_file = files_col.find_one({"username": st.session_state.username}, sort=[("_id", -1)])
                 if recent_file:
                     reply = f"Your most recent file was uploaded on {recent_file['_id'].generation_time.strftime('%b %d, %Y')}."
                 else:
                     reply = "You haven't uploaded anything yet."
                     
            elif "pin" in lower_p or "location" in lower_p:
                user_doc = users_col.find_one({"username": st.session_state.username})
                reply = f"Your vault PIN is {user_doc.get('pin_code')}."
                
            else:
                reply = f"I can check your data! For example, ask me 'how many images do I have?'."
                
            st.session_state.ai_messages.append({"role": "assistant", "content": reply})
            st.rerun()
            
        st.write("<br>", unsafe_allow_html=True)
        if st.button("Close AI Session", use_container_width=True):
            del st.query_params["ai_chat"]
            st.rerun()


# ---------------- SHARING ENGINE ----------------
@st.dialog("🔗 Share Media", width="large")
def share_media_dialog(target_id_str, mode):
    try:
        if mode == "folder":
            cf_id = None if target_id_str == "root" else ObjectId(target_id_str)
        else:
            selected_media_ids = [ObjectId(target_id_str)]
    except InvalidId:
        st.error("Invalid media or folder reference.")
        if st.button("Close"): 
            if "share_folder" in st.query_params: del st.query_params["share_folder"]
            if "share_file" in st.query_params: del st.query_params["share_file"]
            st.rerun()
        return

    curr_user = users_col.find_one({"username": st.session_state.username})
    user_pin = curr_user.get("pin_code", "")
    selected_media_ids = [] if mode == "folder" else selected_media_ids
    
    if mode == "folder":
        folder_files = list(files_col.find({"username": st.session_state.username, "folder_id": cf_id}))
        if not folder_files:
            st.info("No media files found to share in this folder.")
            if st.button("Close"): 
                if "share_folder" in st.query_params: del st.query_params["share_folder"]
                st.rerun()
            return
        st.markdown("### 1. Select Media Batch")
        media_options = {html.escape(f['filename']) if f.get('filename') else str(f['_id']): f['_id'] for f in folder_files}
        selected_media_filenames = st.multiselect("Select files to include in the batch share", list(media_options.keys()), default=list(media_options.keys()), key="ms_media")
        selected_media_ids = [media_options[name] for name in selected_media_filenames]
    else:
        st.markdown("### 1. Share File")
        file_doc = files_col.find_one({"_id": selected_media_ids[0]})
        if file_doc:
            st.write(f"Sharing: **{html.escape(file_doc.get('filename', 'Media Item'))}**")
    
    st.markdown("### 2. Discover Users")
    st.markdown("Select users to securely share this memory with.")
    tab_n, tab_s = st.tabs(["📍 Nearby Users", "🔍 Search Global"])
    selected_users = []
    
    with tab_n:
        nearby_users = list(users_col.find({"pin_code": user_pin, "username": {"$ne": st.session_state.username}}))
        if nearby_users:
            options = [u["username"] for u in nearby_users]
            sel_n = st.multiselect("Users in your area (Same PIN)", options, key="ms_nearby")
            selected_users.extend(sel_n)
        else:
            st.info("No users found with your PIN code.")
            
    with tab_s:
        sq = st.text_input("Search by username", key="search_user_input")
        if sq:
            s_res = list(users_col.find({"username": {"$regex": sq, "$options": "i"}, "username": {"$ne": st.session_state.username}}))
            s_opts = [u["username"] for u in s_res]
            sel_s = st.multiselect("Search Results", s_opts, key="ms_search")
            selected_users.extend(sel_s)
            
    final_selection = list(set(selected_users))
    st.write("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    
    if c1.button(f"Send {len(selected_media_ids)} items to {len(final_selection)} users", type="primary", disabled=len(final_selection)==0 or len(selected_media_ids)==0, use_container_width=True):
        for u in final_selection:
            existing = shares_col.find_one({"sender": st.session_state.username, "receiver": u, "media_ids": selected_media_ids})
            if existing: continue
                
            share_res = shares_col.insert_one({
                "sender": st.session_state.username, "receiver": u,
                "media_ids": selected_media_ids, "count": len(selected_media_ids), 
                "created_at": time.time(), "is_seen": False
            })
            msg_text = f"shared a memory with you." if mode == "file" else f"shared a {len(selected_media_ids)} memory batch with you."
            notifications_col.insert_one({
                "username": u, "sender": st.session_state.username, "type": "share", "share_id": share_res.inserted_id,
                "message": msg_text, "is_read": False, "created_at": time.time()
            })
            
        st.success("Shared successfully!")
        time.sleep(1)
        if "share_folder" in st.query_params: del st.query_params["share_folder"]
        if "share_file" in st.query_params: del st.query_params["share_file"]
        st.rerun()
        
    if c2.button("Cancel", use_container_width=True):
        if "share_folder" in st.query_params: del st.query_params["share_folder"]
        if "share_file" in st.query_params: del st.query_params["share_file"]
        st.rerun()

@st.dialog("📬 Shared Media Preview", width="large")
def preview_shared_dialog(notif_id_str):
    try:
        notif_oid = ObjectId(notif_id_str)
    except InvalidId:
        st.error("Invalid notification format.")
        if st.button("Close"): del st.query_params["preview_notif"]; st.rerun()
        return

    notif = notifications_col.find_one({"_id": notif_oid})
    if not notif:
        st.error("Notification not found.")
        if st.button("Close"): del st.query_params["preview_notif"]; st.rerun()
        return
        
    if notif.get("type") == "share_reaction":
        st.info(f"**{html.escape(notif['sender'])}** {html.escape(notif['message'])}")
        if st.button("Mark as Read & Close"):
            notifications_col.update_one({"_id": notif_oid}, {"$set": {"is_read": True}})
            del st.query_params["preview_notif"]
            st.rerun()
        return

    share = shares_col.find_one({"_id": notif.get("share_id")})
    if not share:
        st.error("Shared media no longer exists.")
        if st.button("Close"): del st.query_params["preview_notif"]; st.rerun()
        return
        
    media_ids = share.get("media_ids", [])
    if not media_ids:
        st.error("No media files found in this shared batch.")
        if st.button("Close"): del st.query_params["preview_notif"]; st.rerun()
        return

    st.markdown(f"**From:** {html.escape(notif['sender'])}")
    st.markdown(f"**Includes:** {share['count']} memory copies.")
    st.write("<br>", unsafe_allow_html=True)
    
    files_to_preview = list(files_col.find({"_id": {"$in": media_ids}}))
    preview_cols = st.columns(4)
    for p_idx, p_file in enumerate(files_to_preview):
        safe_preview_url = html.escape(p_file["url"])
        with preview_cols[p_idx % 4]:
            st.markdown('<div class="media-container-wrapper">', unsafe_allow_html=True)
            if p_file["resource_type"] == "image":
                img_html = f'<div class="square-media"><img src="{safe_preview_url}"></div>'
                st.markdown(img_html.replace('\n', ''), unsafe_allow_html=True)
            else:
                vid_thumb_preview = safe_preview_url.replace(".mp4", ".jpg").replace(".webm", ".jpg").replace(".mov", ".jpg")
                vid_html = f'<div class="square-media" style="position:relative;"><img src="{vid_thumb_preview}" onerror="this.src=\'https://cdn-icons-png.flaticon.com/512/2985/2985655.png\'"><div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); font-size:40px; color:white; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">▶️</div></div>'
                st.markdown(vid_html.replace('\n', ''), unsafe_allow_html=True)
            
            with st.popover("⋮"):
                btn_html = f'<a href="{safe_preview_url}" download target="_blank" style="display:block; padding: 8px 16px; border: 1.5px solid var(--border); border-radius: 8px; color: var(--text-primary); text-decoration: none; text-align: center; font-weight: 600; margin-bottom: 5px;">⬇️ Download</a>'
                st.markdown(btn_html.replace('\n', ''), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
    st.markdown("<hr style='border-color: rgba(255,255,255,0.2); margin-top: 30px;'>", unsafe_allow_html=True)
    
    # NEAT, MANAGEABLE SHARE REACTIONS 
    with st.popover("➕ Add Reaction"):
        e_cols = st.columns(4)
        for e_idx, em in enumerate(["🥰", "❤️", "🔥", "😂", "👍", "🎉", "✨", "🥺"]):
            if e_cols[e_idx % 4].button(em, key=f"sreact_{em}", use_container_width=True):
                notifications_col.insert_one({
                    "username": notif['sender'], "sender": st.session_state.username,
                    "type": "share_reaction", "message": f"reacted {em} to your shared memory.",
                    "is_read": False, "created_at": time.time()
                })
                st.success(f"Sent {em} to {html.escape(notif['sender'])}!")
                time.sleep(1)
                st.rerun()

    st.write("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button(f"📥 Save {share['count']} items to Album", type="primary", use_container_width=True):
        root = folders_col.find_one({"username": st.session_state.username, "parent_id": None})
        root_id = root["_id"] if root else None
        
        # ONE SINGLE FOLDER CREATION LOGIC FOR ALL SHARED MEDIA
        shared_folder = folders_col.find_one({"username": st.session_state.username, "folder_name": "Shared Media", "parent_id": root_id})
        if not shared_folder:
            res = folders_col.insert_one({"username": st.session_state.username, "folder_name": "Shared Media", "parent_id": root_id, "cover_photo": "", "is_locked": False})
            dest_f_id = res.inserted_id
        else:
            dest_f_id = shared_folder["_id"]
            
        files_col.insert_many([{
            "username": st.session_state.username, "folder_id": dest_f_id,
            "filename": f"Shared from {notif['sender']} - {file.get('filename','media')}",
            "url": file["url"], "public_id": file["public_id"], "resource_type": file["resource_type"],
            "tag": "", "tag_time": 0
        } for file in files_to_preview])

        notifications_col.update_one({"_id": ObjectId(notif_id_str)}, {"$set": {"is_read": True}})
        shares_col.update_one({"_id": share["_id"]}, {"$set": {"is_seen": True}})
        
        st.success("Saved to Shared Media album!")
        time.sleep(1)
        del st.query_params["preview_notif"]
        st.rerun()
        
    if c2.button("Mark Read & Close", use_container_width=True):
        notifications_col.update_one({"_id": ObjectId(notif_id_str)}, {"$set": {"is_read": True}})
        del st.query_params["preview_notif"]
        st.rerun()

# --- NATIVE FULL-SCREEN STORY RENDERER (Clean 3-Dot Hover UI) ---
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

    media_element = f"<img src='{safe_url}' style='max-width: 85vw; max-height: 85vh; object-fit: contain; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.6); pointer-events: none;'>" if item['resource_type'] == "image" else f"<video src='{safe_url}' controls autoplay loop playsinline style='max-width: 85vw; max-height: 85vh; object-fit: contain; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.6);'></video>"
    prev_button = f"<a href='{prev_search}' target='_parent' class='liquid-btn' style='left: 4%;'>◀</a>" if has_prev == "true" else ""
    next_button = f"<a href='{next_search}' target='_parent' class='liquid-btn' style='right: 4%;'>▶</a>" if has_next == "true" else ""

    # Clean 3-Dot Hover Menu for Story Reactions
    emojis = ["🥰", "❤️", "🔥", "😂", "👍", "🎉", "✨", "🥺"]
    react_html = '<div class="story-menu"><div class="story-menu-btn">⋮</div><div class="story-menu-content">'
    for em in emojis:
        r_link = get_nav_link(page="app", folder="root", story_group=group_idx, story_idx=story_idx, react=em)
        react_html += f'<a href="{r_link}" target="_parent" class="story-react-btn">{em}</a>'
    react_html += '</div></div>'

    lightbox_ui = f"""<div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.9); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); z-index: 9999999; display: flex; flex-direction: column; align-items: center; justify-content: center;"><style>.liquid-btn {{ position: absolute; display: flex; align-items: center; justify-content: center; width: 60px; height: 60px; border-radius: 50%; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.3); color: white; font-size: 24px; text-decoration: none; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4); transition: all 0.3s ease; cursor: pointer; z-index: 10000000; }} .liquid-btn:hover {{ background: rgba(255, 255, 255, 0.3); transform: scale(1.1); box-shadow: 0 8px 32px rgba(255, 255, 255, 0.2); color: white; }} .story-menu {{ position: absolute; top: 25px; left: 25px; z-index: 10000001; }} .story-menu-btn {{ width: 50px; height: 50px; border-radius: 50%; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.3); color: white; font-size: 24px; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4); }} .story-menu-content {{ display: none; position: absolute; top: 60px; left: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(20px); padding: 15px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.2); width: 220px; flex-wrap: wrap; gap: 12px; }} .story-menu:hover .story-menu-content {{ display: flex; flex-direction: row; }} .story-react-btn {{ font-size: 28px; text-decoration: none; transition: transform 0.2s ease; cursor: pointer; }} .story-react-btn:hover {{ transform: scale(1.3); }}</style><a href="{close_search}" target="_parent" class="liquid-btn" style="top: 25px; right: 25px;">✕</a>{react_html}<div style="position: absolute; top: 30px; color: white; font-family: sans-serif; font-size: 18px; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.5); z-index: 10000000;">{html.escape(group['label'])}</div>{prev_button}{next_button}<div style="position: absolute; bottom: 30px; color: white; font-family: sans-serif; font-size: 15px; font-weight: 600; background: rgba(255,255,255,0.15); padding: 8px 24px; border-radius: 30px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); letter-spacing: 1px; z-index: 10000000;">{story_idx + 1} / {len(items)}</div>{media_element}</div>"""
    st.markdown(lightbox_ui.replace('\n', ''), unsafe_allow_html=True)

    components.html(f"""
    <script>
        window.parent.fullscreenSwipeNext = "{next_search}"; window.parent.fullscreenSwipePrev = "{prev_search}";
        window.parent.hasFullscreenNext = {has_next}; window.parent.hasFullscreenPrev = {has_prev};
        if (!window.parent.fullscreenSwipeListenerAdded) {{
            let touchstartX = 0; let touchendX = 0;
            window.parent.document.addEventListener('touchstart', e => {{ touchstartX = e.changedTouches[0].screenX; }}, {{passive: true}});
            window.parent.document.addEventListener('touchend', e => {{
                touchendX = e.changedTouches[0].screenX;
                if (touchendX < touchstartX - 60 && window.parent.hasFullscreenNext) window.parent.location.search = window.parent.fullscreenSwipeNext;
                if (touchendX > touchstartX + 60 && window.parent.hasFullscreenPrev) window.parent.location.search = window.parent.fullscreenSwipePrev;
            }}, {{passive: true}});
            window.parent.fullscreenSwipeListenerAdded = true;
        }}
    </script>
    """, height=0)
    st.stop()


# ================= CORE CSS =================
def inject_global_css():
    css = """
    <style>
    :root {
        --bg-app: #f2f2f7; --bg-card: #ffffff; --bg-sidebar: #f2f2f7; --bg-input: #ffffff;
        --text-primary: #000000; --text-secondary: #8e8e93; --border: #d1d1d6; --accent: #007aff; --btn-hover: #e5e5ea;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-app: #000000; --bg-card: #1c1c1e; --bg-sidebar: #000000; --bg-input: #1c1c1e;
            --text-primary: #ffffff; --text-secondary: #8e8e93; --border: #38383a; --accent: #0a84ff; --btn-hover: #2c2c2e;
        }
    }
    .stApp { background-color: var(--bg-app) !important; color: var(--text-primary) !important; }
    p, h1, h2, h3, h4, h5, h6, span, label, li { color: var(--text-primary) !important; transition: color 0.3s ease; }
    
    /* ABSOLUTE OVERRIDES & SIDEBAR DESTRUCTION */
    header[data-testid="stHeader"] { display: none !important; opacity: 0 !important; pointer-events: none !important; height: 0 !important; }
    div[data-testid="stToolbar"] { display: none !important; pointer-events: none !important; }
    div[data-testid="stDecoration"] { display: none !important; pointer-events: none !important; }
    #MainMenu { visibility: hidden; } .stDeployButton { display: none !important; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    
    /* Ensure content is always interactable */
    div[data-testid="stAppViewBlockContainer"] { z-index: 10 !important; padding-top: 1rem !important; }
    div[data-testid="stMarkdownContainer"] { position: relative; z-index: 50; pointer-events: auto !important; }

    .title-text { color: var(--text-primary) !important; font-weight: 800; font-size: 32px; text-align: center; margin-bottom: 5px; }
    .sub-text { color: var(--text-secondary) !important; font-size: 15px; text-align: center; margin-bottom: 30px; }
    .brand-logo { font-size: 24px; font-weight: 800; color: var(--accent) !important; letter-spacing: 0.5px; text-decoration: none; }
    .muted-text { color: var(--text-secondary) !important; }

    .auth-container, .content-card {
        max-width: 480px !important; width: 90% !important; background-color: var(--bg-card) !important;
        padding: 50px 40px !important; border-radius: 20px !important; border: 1px solid var(--border) !important; margin: 8vh auto !important; 
        position: relative; z-index: 9999999 !important; pointer-events: auto !important;
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
    .native-link { color: var(--accent) !important; text-decoration: none; font-weight: 600; cursor: pointer;} .native-link:hover { text-decoration: underline; }
    
    .top-nav { display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; position: relative; z-index: 9999999 !important; pointer-events: auto !important; }
    .nav-links { display: flex; gap: 20px; align-items: center; position: relative; z-index: 9999999 !important; pointer-events: auto !important; }
    .nav-links a { color: var(--text-primary) !important; text-decoration: none; font-weight: 500; font-size: 15px; position: relative; z-index: 9999999 !important; pointer-events: auto !important; cursor: pointer; }
    .nav-links a:hover { color: var(--accent) !important; }

    .dashboard-title { font-size: 32px; font-weight: 800; color: var(--text-primary); }
    
    .story-wrapper { display: flex; overflow-x: auto; gap: 15px; padding: 10px 0 20px 0; margin-bottom: 10px; }
    .story-wrapper::-webkit-scrollbar { display: none; }
    .story-link { text-decoration: none; display: inline-block; }
    .story-item { display: flex; flex-direction: column; align-items: center; gap: 8px; min-width: 85px; cursor: pointer; transition: transform 0.2s; }
    .story-item:hover { transform: scale(1.05); }
    .story-ring { width: 76px; height: 76px; border-radius: 50%; padding: 3px; display: flex; align-items: center; justify-content: center; }
    .story-inner { width: 100%; height: 100%; border-radius: 50%; border: 3px solid var(--bg-app); overflow: hidden; background: var(--bg-card); display: flex; align-items: center; justify-content: center; font-size: 24px; }
    .story-inner img, .story-inner video { width: 100%; height: 100%; object-fit: cover; }
    .story-label { font-size: 12px; font-weight: 600; color: var(--text-primary); text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 80px;}

    /* PURE CSS HOVER EFFECTS */
    .album-link { text-decoration: none; display: block; }
    .album-card { margin-bottom: 15px; transition: transform 0.2s ease; position: relative; }
    .album-card:hover { transform: scale(1.02); }
    .folder-card { position: relative; width: 100%; aspect-ratio: 1/1; border-radius: 12px; background-color: var(--bg-card); border: 1px solid var(--border); display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 8px; transition: transform 0.2s ease; }
    .folder-card:hover { transform: scale(1.02); }

    .media-container-wrapper { position: relative; margin-bottom: 15px; cursor: pointer; }
    .media-container-wrapper:hover .square-media { transform: scale(1.02); }
    .square-media {
        width: 100%; aspect-ratio: 1/1; overflow: hidden; transition: transform 0.2s;
        border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); background: var(--bg-card); border: 1px solid var(--border);
    }
    .square-media img, .square-media video { width: 100%; height: 100%; object-fit: cover; }
    
    [data-testid="column"] { position: relative; }
    .media-container-wrapper [data-testid="stPopover"] {
        position: absolute !important; top: 8px !important; right: 8px !important; z-index: 10 !important;
    }
    .media-container-wrapper [data-testid="stPopover"] > button {
        background-color: rgba(0, 0, 0, 0.6) !important; color: white !important;
        border: none !important; border-radius: 50% !important; width: 32px !important; height: 32px !important;
        display: flex; align-items: center; justify-content: center; line-height: 0 !important;
        padding: 0 !important; font-size: 18px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    }
    .media-container-wrapper [data-testid="stPopover"] > button:hover { background-color: rgba(0, 0, 0, 0.9) !important; transform: scale(1.05); }
    
    .folder-options-btn [data-testid="stPopover"] > button {
        background-color: var(--bg-card) !important; color: var(--text-primary) !important;
        border: 1px solid var(--border) !important; border-radius: 8px !important; height: 38px !important;
        padding: 0 15px !important; font-weight: 600 !important; box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
    }
    .folder-options-btn [data-testid="stPopover"] > button:hover { background-color: var(--btn-hover) !important; }
    
    [data-testid="stFileUploader"] > div { background-color: var(--bg-card) !important; border: 1px dashed var(--border) !important; border-radius: 16px !important; padding: 20px !important; }
    
    .profile-header-widget { 
        display: inline-flex; align-items: center; gap: 12px; background: var(--bg-card); padding: 6px 16px 6px 6px; border-radius: 50px; 
        border: 1px solid var(--border); box-shadow: 0 2px 10px rgba(0,0,0,0.05); transition: transform 0.2s; cursor: pointer; 
        color: var(--text-primary) !important; position: relative; text-decoration: none;
    }
    .profile-header-widget:hover { transform: scale(1.02); text-decoration: none; }
    .profile-header-widget img { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; }
    .profile-header-widget span { font-weight: 600; font-size: 14px;}
    
    .profile-notif-dot {
        position: absolute; top: 2px; right: 8px; width: 11px; height: 11px;
        background-color: #ff3b30; border-radius: 50%; border: 1.5px solid var(--bg-card);
        box-shadow: 0 0 5px rgba(255, 59, 48, 0.5); z-index: 20;
    }

    .block-container { padding-bottom: 80px !important; min-height: 85vh; }
    
    /* PERFECTLY CLEAR NON-OVERLAPPING FOOTER */
    .custom-footer { 
        margin-top: 60px; padding: 20px; text-align: center; 
        border-top: 1px solid var(--border); color: var(--text-secondary); font-size: 13px;
    }
    
    .masonry-gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 18px; padding: 10px 0 40px 0; }
    .gallery-item { position: relative; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1); background: #000; aspect-ratio: 4/5; }
    .gallery-item img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s ease; opacity: 0.9; }
    .gallery-item:hover img { transform: scale(1.08); opacity: 1; }
    .gallery-overlay { position: absolute; bottom: 0; left: 0; width: 100%; background: linear-gradient(transparent, rgba(0,0,0,0.8)); padding: 20px 15px 15px 15px; pointer-events: none; }
    .gallery-title { color: white; font-size: 15px; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
    .gallery-date { color: #e5e5ea; font-size: 12px; font-weight: 500; }

    /* MASSIVE MOBILE TOUCH OVERHAUL */
    @media (max-width: 768px) {
        .auth-container, .content-card { border: none !important; border-radius: 0 !important; padding: 30px 20px !important; margin: 0 !important; width: 100% !important; max-width: 100% !important; pointer-events: auto !important;}
        .top-nav { padding: 15px 10px; flex-direction: column; gap: 15px; justify-content: center; text-align: center; z-index: 9999999 !important; pointer-events: auto !important;}
        .nav-links { gap: 15px; flex-wrap: wrap; justify-content: center; width: 100%; z-index: 9999999 !important; pointer-events: auto !important;}
        .nav-links a { font-size: 16px; padding: 12px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; flex: 1; min-width: 80px; font-weight: 600; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .brand-logo { font-size: 28px; margin-bottom: 10px;}
        .masonry-gallery { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; padding: 5px; }
        .gallery-title { font-size: 13px; }
        .block-container { padding-top: 1rem !important; } 
    }
    </style>
    """
    st.markdown(css.replace('\n', ''), unsafe_allow_html=True)


# ================= CATCH DIALOGS & LIGHTBOXES =================
if "share_folder" in st.query_params and st.session_state.logged_in:
    inject_global_css()
    share_media_dialog(st.query_params["share_folder"], mode="folder")

if "share_file" in st.query_params and st.session_state.logged_in:
    inject_global_css()
    share_media_dialog(st.query_params["share_file"], mode="file")

if "preview_notif" in st.query_params and st.session_state.logged_in:
    inject_global_css()
    preview_shared_dialog(st.query_params["preview_notif"])

if "profile_hub" in st.query_params and st.session_state.logged_in:
    inject_global_css()
    render_profile_hub_fullscreen()
    
if "ai_chat" in st.query_params and st.session_state.logged_in:
    inject_global_css()
    render_ai_chat_fullscreen()

if "story_group" in st.query_params and "story_idx" in st.query_params and st.session_state.logged_in:
    inject_global_css()
    render_story_fullscreen(int(st.query_params["story_group"]), int(st.query_params["story_idx"]))

elif "lightbox_idx" in st.query_params and st.session_state.logged_in:
    inject_global_css()
    
    folder_id_str = st.query_params.get("folder", "root")
    idx = int(st.query_params["lightbox_idx"])
    
    try:
        f_id = None if folder_id_str == "root" else ObjectId(folder_id_str)
    except InvalidId:
        f_id = None
    
    files_raw = list(files_col.find({"username": st.session_state.username, "folder_id": f_id}))
    pinned_files = sorted([f for f in files_raw if f.get("pin_order", 0) > 0], key=lambda x: x.get("pin_order", 0))
    unpinned_files = [f for f in files_raw if not f.get("pin_order", 0) > 0]
    files = pinned_files + unpinned_files
    
    if not files or idx >= len(files):
        if "lightbox_idx" in st.query_params: del st.query_params["lightbox_idx"]
        st.rerun()

    file = files[idx]
    has_next = "true" if idx < len(files) - 1 else "false"
    has_prev = "true" if idx > 0 else "false"
    
    session_token = html.escape(st.query_params.get('session', ''))
    safe_folder_id = html.escape(folder_id_str)
    next_search = f"?page=app&folder={safe_folder_id}&lightbox_idx={idx + 1}&session={session_token}"
    prev_search = f"?page=app&folder={safe_folder_id}&lightbox_idx={idx - 1}&session={session_token}"
    close_search = f"?page=app&folder={safe_folder_id}&session={session_token}"
    safe_url = html.escape(file['url'])

    media_element = f"<img src='{safe_url}' style='max-width: 85vw; max-height: 85vh; object-fit: contain; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.6); pointer-events: none;'>" if file['resource_type'] == "image" else f"<video src='{safe_url}' controls autoplay loop playsinline style='max-width: 85vw; max-height: 85vh; object-fit: contain; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.6);'></video>"
    prev_button = f"<a href='{prev_search}' target='_parent' class='liquid-btn' style='left: 4%;'>◀</a>" if has_prev == "true" else ""
    next_button = f"<a href='{next_search}' target='_parent' class='liquid-btn' style='right: 4%;'>▶</a>" if has_next == "true" else ""

    lightbox_ui = f"""<div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.9); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); z-index: 9999999; display: flex; align-items: center; justify-content: center;"><style>.liquid-btn {{ position: absolute; display: flex; align-items: center; justify-content: center; width: 60px; height: 60px; border-radius: 50%; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.3); color: white; font-size: 24px; text-decoration: none; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4); transition: all 0.3s ease; cursor: pointer; z-index: 10000000; }} .liquid-btn:hover {{ background: rgba(255, 255, 255, 0.3); transform: scale(1.1); box-shadow: 0 8px 32px rgba(255, 255, 255, 0.2); color: white; }}</style><a href="{close_search}" target="_parent" class="liquid-btn" style="top: 25px; right: 25px;">✕</a>{prev_button}{next_button}<div style="position: absolute; bottom: 30px; color: white; font-family: sans-serif; font-size: 15px; font-weight: 600; background: rgba(255,255,255,0.15); padding: 8px 24px; border-radius: 30px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); letter-spacing: 1px; z-index: 10000000;">{idx + 1} / {len(files)}</div>{media_element}</div>"""
    st.markdown(lightbox_ui.replace('\n', ''), unsafe_allow_html=True)

    components.html(f"""
    <script>
        window.parent.fullscreenSwipeNext = "{next_search}"; window.parent.fullscreenSwipePrev = "{prev_search}";
        window.parent.hasFullscreenNext = {has_next}; window.parent.hasFullscreenPrev = {has_prev};
        if (!window.parent.fullscreenSwipeListenerAdded) {{
            let touchstartX = 0; let touchendX = 0;
            window.parent.document.addEventListener('touchstart', e => {{ touchstartX = e.changedTouches[0].screenX; }}, {{passive: true}});
            window.parent.document.addEventListener('touchend', e => {{
                touchendX = e.changedTouches[0].screenX;
                if (touchendX < touchstartX - 60 && window.parent.hasFullscreenNext) window.parent.location.search = window.parent.fullscreenSwipeNext;
                if (touchendX > touchstartX + 60 && window.parent.hasFullscreenPrev) window.parent.location.search = window.parent.fullscreenSwipePrev;
            }}, {{passive: true}});
            window.parent.fullscreenSwipeListenerAdded = true;
        }}
    </script>
    """, height=0)
    st.stop()
    
else:
    components.html('<script>if (window.top.storyTimeout) { clearTimeout(window.top.storyTimeout); window.top.storyTimeout = null; }</script>', height=0)


# ================= PUBLIC ROUTING (LOGGED OUT) =================
if not st.session_state.logged_in:
    inject_global_css()
    
    if app_page not in ["landing", "policy", "contact", "auth"]:
        st.query_params["page"] = "landing"
        st.rerun()
    
    if app_page != "auth":
        nav_html = f"""<div class="top-nav"><a href="{get_nav_link('landing')}" target="_self" class="brand-logo">voidememo</a><div class="nav-links"><a href="{get_nav_link('landing')}" target="_self">Home</a><a href="{get_nav_link('policy')}" target="_self">Policy</a><a href="{get_nav_link('auth', 'login')}" target="_self" style="color: var(--accent) !important; font-weight: 700;">Log In</a></div></div>"""
        st.markdown(nav_html.replace('\n', ''), unsafe_allow_html=True)

        if app_page == "landing":
            st.markdown('<div class="title-text" style="font-size: 3.5rem; margin-top: 4rem;">Secure Your Memories</div>', unsafe_allow_html=True)
            st.markdown('<div class="sub-text" style="font-size: 1.25rem; max-width: 600px; margin: 0 auto 3rem auto;">Your personal digital bibliotheca. Access, organize, and protect your media with absolute privacy.</div>', unsafe_allow_html=True)
            
            btn_html = f'<div style="text-align: center; position: relative; z-index: 9999999 !important; pointer-events: auto !important;"><a href="{get_nav_link("auth", "signup")}" target="_self" style="background: var(--accent); color: #ffffff; padding: 14px 30px; border-radius: 50px; text-decoration: none; font-weight: 600; font-size: 16px; display: inline-block;">Create Free Vault</a></div>'
            st.markdown(btn_html.replace('\n', ''), unsafe_allow_html=True)
            st.write("<br><br><br><h3 style='text-align: center; margin-bottom: 30px;'>Community Vault Gallery</h3>", unsafe_allow_html=True)
            
            pipeline = [
                {"$match": {"resource_type": "image"}},
                {"$lookup": {"from": "folders", "localField": "folder_id", "foreignField": "_id", "as": "folder_info"}},
                {"$unwind": {"path": "$folder_info", "preserveNullAndEmptyArrays": True}},
                {"$match": {"folder_info.is_locked": {"$ne": True}}},
                {"$sample": {"size": 20}}
            ]
            community_images = list(files_col.aggregate(pipeline))
            
            fallback_urls = [
                "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?auto=format&fit=crop&w=600&q=80",
                "https://images.unsplash.com/photo-1506744626753-eda818465c40?auto=format&fit=crop&w=600&q=80",
                "https://images.unsplash.com/photo-1510784722466-f2aa9c52fff6?auto=format&fit=crop&w=600&q=80",
                "https://images.unsplash.com/photo-1444464666168-49b6264240ce?auto=format&fit=crop&w=600&q=80",
                "https://images.unsplash.com/photo-1532274402911-5a369e4c4bb5?auto=format&fit=crop&w=600&q=80",
                "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=600&q=80"
            ]
            
            urls_to_show = [img["url"] for img in community_images]
            while len(urls_to_show) < 20: urls_to_show.append(random.choice(fallback_urls))
                
            gallery_html = '<div class="masonry-gallery">'
            for url in urls_to_show:
                random_date = f"202{random.randint(3,6)} Memory"
                safe_url = html.escape(url)
                gallery_html += f'<div class="gallery-item"><img src="{safe_url}" loading="lazy"><div class="gallery-overlay"><div class="gallery-title">Community Vault ✨</div><div class="gallery-date">{random_date}</div></div></div>'
            gallery_html += '</div>'
            st.markdown(gallery_html.replace('\n', ''), unsafe_allow_html=True)
            
        elif app_page == "policy":
            st.markdown("""
            <div class="content-card" style="position: relative; z-index: 10; pointer-events: auto;">
                <h2>Privacy Policy & Permissions</h2>
                <p class="muted-text">Last Updated: April 2026</p>
                <hr style='border-color: var(--border);'>
                <h4>1. Data Collection</h4>
                <p>We collect minimal information necessary to provide you with secure access to your digital bibliotheca.</p>
                <h4>2. Media Storage Permissions</h4>
                <p>By uploading files to voidememo, you grant us the permission to securely host and deliver this content back to you.</p>
                <h4>3. Community Gallery Usage</h4>
                <p>As part of our dynamic community experience, uploaded images may be randomly selected and displayed anonymously on our public landing page. By uploading content to our platform, you acknowledge and explicitly consent to this anonymous public display. You can opt-out by setting any album to 'Private'.</p>
            </div>
            """, unsafe_allow_html=True)
            
        elif app_page == "contact":
            st.markdown("""
            <div class="content-card" style="text-align: center; position: relative; z-index: 10; pointer-events: auto;">
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
            forgot_html = f'<div style="text-align: right; margin-top: -10px; margin-bottom: 15px;"><a href="{get_nav_link("auth", "forgot")}" target="_self" class="muted-text" style="font-size: 13px; text-decoration: none; font-weight: 500; position:relative; z-index:9999999; pointer-events:auto;">Forgot Password?</a></div>'
            st.markdown(forgot_html.replace('\n', ''), unsafe_allow_html=True)
            
            if st.button("Sign In", type="primary", use_container_width=True):
                if not email or not pwd: st.error("Please enter email and password.")
                else:
                    result = login(email, pwd)
                    if result:
                        token = str(uuid.uuid4())
                        users_col.update_one({"username": result}, {"$set": {"session_token": token}})
                        st.session_state.logged_in = True; st.session_state.username = result
                        st.query_params["session"] = token; st.query_params["page"] = "app"; st.query_params["folder"] = "root"
                        if "view" in st.query_params: del st.query_params["view"]
                        st.rerun()
                    else: st.error("Invalid credentials")
                    
            signup_html = f'<div style="text-align: center; margin-top: 25px; position:relative; z-index:9999999; pointer-events:auto;"><span class="muted-text">New to our platform?</span> <a href="{get_nav_link("auth", "signup")}" target="_self" class="native-link">Sign Up</a></div>'
            st.markdown(signup_html.replace('\n', ''), unsafe_allow_html=True)

        elif auth_view == "signup":
            st.markdown('<div class="title-text">Sign Up</div><div class="sub-text">Create an account to build your vault.</div>', unsafe_allow_html=True)
            fname = st.text_input("First Name", placeholder="First Name", label_visibility="collapsed", key="s_fname")
            lname = st.text_input("Last Name", placeholder="Last Name", label_visibility="collapsed", key="s_lname")
            bday = st.date_input("Birthday", value=datetime.date(2000, 1, 1), min_value=datetime.date(1900, 1, 1), label_visibility="collapsed")
            pin_code = st.text_input("PIN / Zip Code", placeholder="Location PIN", label_visibility="collapsed", key="s_pin")
            s_email = st.text_input("Email", placeholder="you@example.com", label_visibility="collapsed", key="s_email")
            s_phone = st.text_input("Phone Number", placeholder="Phone Number (Required for multiple profiles)", label_visibility="collapsed", key="s_phone")
            s_pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="s_pwd")
            
            if st.button("Sign Up", type="primary", use_container_width=True):
                if not s_email or not s_pwd or not fname or not pin_code: st.error("Please fill all core required fields.")
                else:
                    result = register(s_email, s_pwd, fname, lname, bday, pin_code, s_phone)
                    if result == "MAX_ACCOUNTS":
                        st.error("Maximum of 5 profiles allowed per email address.")
                    elif result == "PHONE_REQUIRED":
                        st.error("Phone number is required when creating multiple accounts with the same email.")
                    elif result:
                        token = str(uuid.uuid4())
                        users_col.update_one({"username": result}, {"$set": {"session_token": token}})
                        st.session_state.logged_in = True; st.session_state.username = result
                        st.query_params["session"] = token; st.query_params["page"] = "app"; st.query_params["folder"] = "root"
                        if "view" in st.query_params: del st.query_params["view"]
                        st.rerun()
            login_html = f'<div style="text-align: center; margin-top: 25px; position:relative; z-index:9999999; pointer-events:auto;"><span class="muted-text">Already have an account?</span> <a href="{get_nav_link("auth", "login")}" target="_self" class="native-link">Sign In</a></div>'
            st.markdown(login_html.replace('\n', ''), unsafe_allow_html=True)

        elif auth_view == "forgot":
            st.markdown('<div class="title-text">Forgot Password</div>', unsafe_allow_html=True)
            if st.session_state.reset_step == 0:
                st.markdown('<div class="sub-text">Please enter your registered email</div>', unsafe_allow_html=True)
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
                st.markdown('<div class="sub-text">Enter the 6-digit code sent to your email</div>', unsafe_allow_html=True)
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
            login_html = f'<div style="text-align: center; margin-top: 25px; position:relative; z-index:9999999; pointer-events:auto;"><span class="muted-text">Remembered your password?</span> <a href="{get_nav_link("auth", "login")}" target="_self" class="native-link">Log In</a></div>'
            st.markdown(login_html.replace('\n', ''), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ================= DASHBOARD APP (LOGGED IN) =================
else:
    inject_global_css()
    st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container { max-width: 100% !important; padding-top: 1rem !important; }</style>", unsafe_allow_html=True)

    user_data = users_col.find_one({"username": st.session_state.username})
    
    # ---------------- ROOT RESOLUTION ----------------
    root_folder = folders_col.find_one({"username": st.session_state.username, "parent_id": None})
    if active_folder == "root" and root_folder: actual_folder_id = root_folder["_id"]
    else:
        try: actual_folder_id = ObjectId(active_folder)
        except InvalidId: actual_folder_id = root_folder["_id"] if root_folder else None

    current = folders_col.find_one({"_id": actual_folder_id})
    is_root = current is None or current.get("parent_id") is None

    prof_pic = user_data.get("profile_photo") or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
    display_name = html.escape(user_data.get("first_name", st.session_state.username))
    
    title_text = "Albums" if is_root else html.escape(current["folder_name"])
    if not is_root and current.get("is_locked"): title_text += " 🔒"

    # ================= DYNAMIC HEADER (REPLACES SIDEBAR AND TOP NAV) =================
    c_title, c_opt, c_prof = st.columns([2, 1, 3])
    
    with c_title: 
        if is_root:
            st.markdown(f'<div class="dashboard-title" style="color: var(--accent);">voidememo</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="dashboard-title">{title_text}</div>', unsafe_allow_html=True)
        
    with c_opt:
        if not is_root:
            st.markdown('<div class="folder-options-btn" style="display: flex; justify-content: flex-end;">', unsafe_allow_html=True)
            with st.popover("⋮ Options"):
                st.markdown("**Album Management**")
                if st.button("✏️ Rename Album", key=f"edit_{current['_id']}", use_container_width=True): rename_folder_dialog(current["_id"], current["folder_name"])
                if st.button("🗑 Delete Album", key=f"del_fold_{current['_id']}", use_container_width=True): delete_folder_dialog(current["_id"], current["folder_name"])
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                st.markdown("**Sharing & Privacy**")
                if st.button("🔗 Share Folder Media BATCH", key=f"share_folder_{current['_id']}", use_container_width=True):
                    st.query_params["share_folder"] = str(current['_id']) 
                    st.rerun()
                is_locked = current.get("is_locked", False)
                lock_btn_txt = "🔓 Make Public (Community)" if is_locked else "🔒 Lock Album (Private)"
                if st.button(lock_btn_txt, key=f"lock_fold_{current['_id']}", use_container_width=True):
                    folders_col.update_one({"_id": current["_id"]}, {"$set": {"is_locked": not is_locked}})
                    st.rerun()
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                st.markdown("**Add Content**")
                with st.form("upload_content_form", clear_on_submit=True):
                    uploaded_files = st.file_uploader("Upload Media", accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}", label_visibility="collapsed")
                    submit_button = st.form_submit_button("Sync Files", type="primary", use_container_width=True)
                    if submit_button and uploaded_files:
                        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "video/mp4", "video/webm", "video/quicktime"]
                        with st.spinner("Syncing to cloud..."):
                            for file in uploaded_files:
                                if file.type not in allowed_types:
                                    st.error(f"Security Policy Blocked: {html.escape(file.name)} is not an allowed image or video format.")
                                    continue
                                r_type = "video" if file.type.startswith("video") else "image"
                                file_size_mb = file.size / (1024 * 1024)
                                try:
                                    res = cloudinary.uploader.upload_large(file, resource_type=r_type, chunk_size=20000000) if file_size_mb > 50 else cloudinary.uploader.upload(file, resource_type=r_type)
                                    safe_filename = html.escape(file.name)
                                    files_col.insert_one({"username": st.session_state.username, "folder_id": current["_id"], "filename": safe_filename, "url": res["secure_url"], "public_id": res["public_id"], "resource_type": r_type, "tag": "", "tag_time": 0})
                                except Exception as e: st.error(f"Failed to upload {html.escape(file.name)}.")
                        st.session_state.uploader_key += 1; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with c_prof:
        ai_link = get_nav_link(page="app", folder=active_folder, ai_chat=1)
        
        if is_root:
            unread_notifs = list(notifications_col.find({"username": st.session_state.username, "is_read": False}).sort("created_at", -1))
            notif_dot_html = '<div class="profile-notif-dot"></div>' if unread_notifs else ''
            prof_link = get_nav_link(page="app", folder=active_folder, profile_hub=1)
            
            header_html = f'''
            <div style="display:flex; justify-content:flex-end; gap: 15px; align-items:center;">
                <a href="{ai_link}" target="_parent" class="profile-header-widget" style="text-decoration:none; padding: 6px 16px; border-radius: 50px; background: var(--accent); color: white !important; border: none; box-shadow: 0 4px 12px rgba(10, 132, 255, 0.3);">
                    <span style="font-size:16px;">✨</span><span style="color: white !important; font-weight: 700;">Ask AI</span>
                </a>
                <a href="{prof_link}" target="_parent" class="profile-header-widget" style="text-decoration:none;">
                    <img src="{html.escape(prof_pic)}"><span>{display_name}</span>{notif_dot_html}
                </a>
            </div>
            '''
        else:
            # Hide Profile icon inside folders, ONLY show Ask AI
            header_html = f'''
            <div style="display:flex; justify-content:flex-end; gap: 15px; align-items:center;">
                <a href="{ai_link}" target="_parent" class="profile-header-widget" style="text-decoration:none; padding: 6px 16px; border-radius: 50px; background: var(--accent); color: white !important; border: none; box-shadow: 0 4px 12px rgba(10, 132, 255, 0.3);">
                    <span style="font-size:16px;">✨</span><span style="color: white !important; font-weight: 700;">Ask AI</span>
                </a>
            </div>
            '''
        st.markdown(header_html.replace('\n', ''), unsafe_allow_html=True)


    st.markdown("<hr style='margin-bottom: 20px; border-color: rgba(0,0,0,0.05);'>", unsafe_allow_html=True)


    # --- DYNAMIC STORIES ---
    if is_root and st.session_state.story_groups:
        st.markdown(f'<h3 style="margin-bottom: 10px;">{title_text}</h3>', unsafe_allow_html=True)
        story_html = '<div class="story-wrapper">'
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
            
            story_html += f'<a href="{get_nav_link("app", folder="root", story_group=g_idx, story_idx=0)}" target="_parent" class="story-link"><div class="story-item"><div class="story-ring" style="background: {c};"><div class="story-inner">{thumb_html}</div></div><div class="story-label">{safe_label}</div></div></a>'
        
        story_html += '</div>'
        st.markdown(story_html.replace('\n', ''), unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)


    # --- BACK NAVIGATION (For Folders) ---
    if not is_root:
        back_url = get_nav_link(page="app", folder="root")
        st.markdown(f'<a href="{back_url}" target="_parent" class="native-link">← Back to Albums</a>', unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)


    # --- CREATE NEW ALBUM (Only in Root) ---
    if is_root:
        with st.expander("➕ Create New Album"):
            new_folder = st.text_input("New Album", placeholder="Album Name...", label_visibility="collapsed", key=f"folder_input_{st.session_state.folder_key}")
            if st.button("Create Album", type="primary"):
                clean_folder_name = str(new_folder).strip()
                if clean_folder_name:
                    folders_col.insert_one({"username": st.session_state.username, "folder_name": clean_folder_name, "parent_id": actual_folder_id, "cover_photo": "", "is_locked": False})
                    st.session_state.folder_key += 1; st.rerun()
        st.write("<br>", unsafe_allow_html=True)

    # --- CONTENT GRID (ALBUMS & MEDIA) ---
    folders = list(folders_col.find({"username": st.session_state.username, "parent_id": actual_folder_id}))
    
    files_raw = list(files_col.find({"username": st.session_state.username, "folder_id": actual_folder_id}))
    pinned_files = sorted([f for f in files_raw if f.get("pin_order", 0) > 0], key=lambda x: x.get("pin_order", 0))
    unpinned_files = [f for f in files_raw if not f.get("pin_order", 0) > 0]
    files = pinned_files + unpinned_files
    
    if not folders and not files:
        st.markdown('<p class="muted-text" style="text-align:center; margin-top: 50px;">This album is empty.</p>', unsafe_allow_html=True)

    # --- PERFECTED ALBUM COVERS ---
    if folders:
        f_cols = st.columns(4)
        for i, folder in enumerate(folders):
            with f_cols[i % 4]:
                cover = folder.get("cover_photo")
                folder_url = get_nav_link("app", folder=str(folder["_id"]))
                lock_indicator = '<div style="position:absolute; top:8px; right:8px; font-size:16px; background: rgba(0,0,0,0.5); padding: 4px; border-radius: 50%;">🔒</div>' if folder.get("is_locked") else ""
                safe_fname = html.escape(folder['folder_name'])
                
                if cover:
                    safe_cover = html.escape(cover)
                    html_str = f'<a href="{folder_url}" target="_parent" class="album-link" style="text-decoration: none;"><div class="album-card"><div style="width: 100%; aspect-ratio: 1/1; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid var(--border);">{lock_indicator}<img src="{safe_cover}" style="width: 100%; height: 100%; object-fit: cover;"></div><div style="font-weight: 600; font-size: 15px; color: var(--text-primary); text-align: left; padding-left: 4px; margin-top: 8px;">{safe_fname}</div></div></a>'
                    st.markdown(html_str.replace('\n', ''), unsafe_allow_html=True)
                else:
                    html_str = f'<a href="{folder_url}" target="_parent" class="album-link" style="text-decoration: none;"><div style="margin-bottom: 15px;"><div class="folder-card">{lock_indicator}<div style="font-size: 40px;">📁</div></div><div style="font-weight: 600; font-size: 15px; color: var(--text-primary); text-align: left; padding-left: 4px; margin-top: 8px;">{safe_fname}</div></div></a>'
                    st.markdown(html_str.replace('\n', ''), unsafe_allow_html=True)

    if files:
        st.write("<br>", unsafe_allow_html=True)
        img_cols = st.columns(4)
        for i, file in enumerate(files):
            with img_cols[i % 4]:
                st.markdown('<div class="media-container-wrapper">', unsafe_allow_html=True)
                
                safe_tag = html.escape(file.get("tag", ""))
                emoji_badge = f'<div style="position:absolute; top:8px; left:8px; font-size:20px; z-index:10; background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(5px); padding: 4px 8px; border-radius: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); pointer-events: none;">{safe_tag}</div>' if safe_tag else ""
                pin_badge = '<div style="position:absolute; top:8px; right:45px; font-size:18px; z-index:10; text-shadow: 0 2px 4px rgba(0,0,0,0.5); pointer-events: none;">📌</div>' if file.get("pin_order", 0) > 0 else ""
                
                session_token = html.escape(st.query_params.get('session', ''))
                lb_url = f"?page=app&folder={str(actual_folder_id) if actual_folder_id else 'root'}&lightbox_idx={i}&session={session_token}"
                safe_url = html.escape(file["url"])
                
                media_html = f'<a href="{lb_url}" target="_parent" style="text-decoration:none; display: block;">'
                if file["resource_type"] == "image":
                    media_html += f'<div class="square-media" style="position:relative;">{emoji_badge}{pin_badge}<img src="{safe_url}"></div>'
                else:
                    vid_thumb = safe_url.replace(".mp4", ".jpg").replace(".webm", ".jpg").replace(".mov", ".jpg")
                    media_html += f'<div class="square-media" style="position:relative;">{emoji_badge}{pin_badge}<img src="{vid_thumb}" onerror="this.src=\'https://cdn-icons-png.flaticon.com/512/2985/2985655.png\'"><div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); font-size:40px; color:white; text-shadow: 0 2px 4px rgba(0,0,0,0.5); pointer-events: none;">▶️</div></div>'
                media_html += '</a>'
                st.markdown(media_html.replace('\n', ''), unsafe_allow_html=True)

                with st.popover("⋮"):
                    st.markdown("**Actions**")
                    
                    if st.button("🔗 Share Media", key=f"share_{file['_id']}", use_container_width=True):
                        st.query_params["share_file"] = str(file['_id'])
                        st.rerun()
                        
                    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                    
                    if file.get("pin_order", 0) > 0:
                        if st.button("📌 Unpin Photo", key=f"unpin_{file['_id']}", use_container_width=True):
                            files_col.update_one({"_id": file["_id"]}, {"$unset": {"pin_order": ""}})
                            remaining_pins = list(files_col.find({"folder_id": actual_folder_id, "pin_order": {"$exists": True}}).sort("pin_order", 1))
                            for r_idx, r_file in enumerate(remaining_pins):
                                files_col.update_one({"_id": r_file["_id"]}, {"$set": {"pin_order": r_idx + 1}})
                            st.rerun()
                    else:
                        if st.button("📌 Pin Photo", key=f"pin_{file['_id']}", use_container_width=True):
                            max_pin = files_col.find_one({"folder_id": actual_folder_id, "pin_order": {"$exists": True}}, sort=[("pin_order", -1)])
                            next_pin = (max_pin.get("pin_order", 0) if max_pin else 0) + 1
                            files_col.update_one({"_id": file["_id"]}, {"$set": {"pin_order": next_pin}})
                            st.rerun()
                            
                    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                    dl_html = f'<a href="{safe_url}" download target="_blank" style="display:block; padding: 8px 16px; border: 1.5px solid var(--border); border-radius: 8px; color: var(--text-primary); text-decoration: none; text-align: center; font-weight: 600; margin-bottom: 5px;">⬇️ Download</a>'
                    st.markdown(dl_html.replace('\n', ''), unsafe_allow_html=True)
                    
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
                    
                    time_elapsed = time.time() - file.get("tag_time", 0)
                    is_locked = bool(file.get("tag")) and (time_elapsed < 86400) 
                    if is_locked:
                        if st.button(f"🔒 Locked ({safe_tag})", key=f"lock_{file['_id']}", use_container_width=True):
                            locked_reaction_dialog(86400 - time_elapsed)
                    else:
                        e_cols = st.columns(4)
                        for e_idx, em in enumerate(["🥰", "❤️", "🔥", "😂", "👍", "🎉", "✨", "🥺"]):
                            if e_cols[e_idx % 4].button(em, key=f"em_{file['_id']}_{e_idx}"):
                                files_col.update_one({"_id": file["_id"]}, {"$set": {"tag": em, "tag_time": time.time()}})
                                st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
                
    st.markdown('<div class="custom-footer">© 2026 voidememo. All rights reserved.</div>', unsafe_allow_html=True)