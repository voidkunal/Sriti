# Sriti
A Web application where you store your memories !

📁 Memory Vault: Private Cloud Storage Dashboard
Memory Vault is a secure, high-performance web application designed for private media storage. It features a modern Liquid Glass (Glassmorphism) UI, real-time statistics, and a persistent session management system. Users can create directories, upload images or videos, and interact with their content through a gamified reaction system.

🚀 The Approach
The project was built with a focus on Minimalist Sophistication. The goal was to combine the power of a backend-heavy application with a frontend that feels light, modern, and intuitive.

1. UI/UX Design Strategy

Liquid Glass Theme: Using high-level CSS injection, the app utilizes backdrop-filter: blur() and semi-transparent RGBA backgrounds to create a frosted glass effect that adapts to the moving gradients of the background.

Dashboard Layout: Inspired by admin panels, the UI is split into a persistent sidebar navigation and a main content area that provides high-level metrics (Total Files, Folders, and Storage Breakdown).

Responsive Modals: Destructive actions (Deletion/Renaming) are handled via centered popup dialogs to ensure user intent and prevent accidental data loss.

2. Technical Infrastructure

Frontend: Built with Streamlit, customized heavily with HTML/CSS injection to bypass standard component limitations.

Database: MongoDB Atlas serves as the primary metadata store, tracking user credentials, folder hierarchies, and file details.

Cloud Storage: Integrated with Cloudinary API for secure, optimized hosting of images and videos.

Security: Passwords are never stored in plain text; they are secured using SHA-256 Hashing.

✨ Key Features
🔐 Persistent Authentication

Refresh Persistence: Uses UUID-based session tokens stored in the URL query parameters and MongoDB. This ensures that clicking "Refresh" in the browser does not log the user out.

Secure Sign-up/Login: email and username-based authentication.

📂 Advanced File Management

Root Control: The main dashboard is for folder creation and high-level stats.

Directory Logic: Uploading is enabled only once inside a specific folder to keep the root directory organized.

Safe Deletion: A recursive deletion algorithm ensures that when a folder is deleted, all sub-folders and their corresponding files are wiped from both MongoDB and Cloudinary storage.

📊 Real-time Insights

Live Clock: A Javascript-injected header clock providing real-time local time.

Storage Breakdown: A Plotly-powered dynamic pie chart that analyzes the user's storage usage (Photos vs. Other Files).

🎮 Gamified Interaction

Emoji Reactions: Users can react to their files with custom emojis.

24-Hour Cooldown: Once a reaction is set, it is locked for 24 hours to encourage thoughtful interaction. A countdown timer shows exactly when the lock will expire.

🛠️ Tech Stack
Component	Technology
Language	Python 3.x
Framework	Streamlit
Database	MongoDB (PyMongo)
Media Hosting	Cloudinary
Visualization	Plotly
Styling	CSS3 (Glassmorphism)