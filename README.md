🛡️ Raspberry Pi AI Security Dashboard
A professional-grade smart home security system for the Raspberry Pi. This system uses real-time face recognition to distinguish between "Owners" and "Intruders," providing a live web dashboard and instant Telegram alerts with photo proof.
✨ Features
AI Face Recognition: Uses deep learning to identify known faces.
Intruder Logic: Triggers alerts only if an unknown face is persistent (>3 seconds).
Web Interface: Live MJPEG video stream and a searchable history of all security events.
Telegram Integration: Real-time notifications and snapshots sent directly to your phone.
Hardware Optimized: Built specifically for the Picamera2 stack on Raspberry Pi OS (Bookworm).

🛠️ Hardware Requirements
Raspberry Pi 4 or 5
Raspberry Pi Camera Module (v2 or v3)
Active Internet Connection (for Telegram alerts)

⚙️ Installation & Setup
1. Clone the Project
Bash
git clone https://github.com/YOUR_USERNAME/Pi-Security-Dashboard.git
cd Pi-Security-Dashboard


2. Create the Hardware-Bridged Environment
Because the Pi's camera drivers are tied to system libraries, we must create a virtual environment that can "see" the system packages.
Bash
python3 -m venv --system-site-packages venv
source venv/bin/activate


3. Install Dependencies & Fix NumPy Version
Recent versions of NumPy (2.0+) are incompatible with the pre-compiled Pi camera binaries. We force a compatible version:
Bash
pip install python-dotenv Flask requests face_recognition
pip uninstall numpy -y
pip install "numpy<2"


4. Configuration
Create a .env file in the root directory to store your private credentials:
Plaintext
TELEGRAM_TOKEN=your_bot_token_here
CHAT_ID=your_chat_id_here



📸 Preparing Face Recognition
The system requires a "mathematical map" of your face to work.
Place a clear photo of yourself in the folder and name it owner.jpg.
Run the encoding script:
Bash
python encode_me.py


This creates known_faces.pkl, which the dashboard uses for comparison.

🚀 Running the Dashboard
Start the system:
Bash
python dashboard.py


View Live Stream: Open your browser to http://<your-pi-ip>:8000
View Logs: Navigate to http://<your-pi-ip>:8000/history

⚠️ Troubleshooting
Error
Cause
Solution
ValueError: numpy.dtype size changed
NumPy 2.0 Conflict
Run pip install "numpy<2" inside your venv.
known_faces.pkl not found
Missing face data
Ensure you have run encode_me.py with an owner.jpg.
Externally-managed-environment
Pi OS Security
Use the venv steps listed in the Installation section.
Camera not found
Libcamera/Picamera2
Ensure the camera is enabled in sudo raspi-config.


📝 License
This project is open-source and available under the MIT License.
