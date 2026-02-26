import cv2
import face_recognition
import pickle
import time
import os
import sqlite3
import requests
import threading
from datetime import datetime
from flask import Flask, Response, render_template_string, send_from_directory
from picamera2 import Picamera2
from dotenv import load_dotenv

# Load secrets from .env file
load_dotenv()

# --- CONFIG ---
# These now pull from your .env file for security
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Relative paths make the project portable across different machines
DB_PATH = "known_faces.pkl" 
LOG_DIR = "logs"
SQL_DB = "security_log.db"

# Ensure log directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(SQL_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (timestamp TEXT, person TEXT, confidence TEXT, snapshot_path TEXT)''')
    conn.commit()
    conn.close()

def log_event(person, confidence, frame):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{person}_{file_timestamp}.jpg"
    filepath = os.path.join(LOG_DIR, filename)
   
    # Save the physical image snapshot
    cv2.imwrite(filepath, frame)
   
    # Save metadata to SQLite
    conn = sqlite3.connect(SQL_DB)
    c = conn.cursor()
    c.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (timestamp, person, confidence, filename))
    conn.commit()
    conn.close()
    print(f"📝 Logged: {person} at {timestamp}")

# --- FLASK SETUP ---
app = Flask(__name__)
output_frame = None
lock = threading.Lock()

# Main Dashboard HTML
HTML_PAGE = """
<html>
    <head><title>Pi Security</title><style>
        body { background: #1a1a1a; color: white; font-family: sans-serif; text-align: center; }
        .nav { margin: 20px; }
        .nav a { color: #00ff00; margin: 0 15px; text-decoration: none; border: 1px solid #00ff00; padding: 8px 15px; border-radius: 5px; }
        .nav a:hover { background: #00ff00; color: black; }
        img { border: 5px solid #333; border-radius: 10px; max-width: 80%; margin-top: 10px; }
    </style></head>
    <body>
        <h1>🛡️ Live Security Feed</h1>
        <div class="nav"><a href="/">LIVE VIEW</a> <a href="/history">EVENT HISTORY</a></div>
        <img src="/video_feed">
    </body>
</html>
"""

# History Table HTML
HISTORY_PAGE = """
<html>
    <head><title>History</title><style>
        body { background: #1a1a1a; color: white; font-family: sans-serif; }
        table { width: 90%; margin: 20px auto; border-collapse: collapse; background: #222; }
        th, td { padding: 12px; border: 1px solid #444; text-align: left; }
        th { background: #333; color: #00ff00; }
        img { width: 120px; border-radius: 5px; cursor: pointer; }
        .nav { text-align: center; margin: 20px; }
        .nav a { color: #00ff00; text-decoration: none; font-weight: bold; }
    </style></head>
    <body>
        <h1 style="text-align:center;">🕵️ Detection History</h1>
        <div class="nav"><a href="/">← Back to Live Feed</a></div>
        <table>
            <tr><th>Timestamp</th><th>Person</th><th>Confidence</th><th>Snapshot</th></tr>
            {% for row in rows %}
            <tr>
                <td>{{ row[0] }}</td>
                <td style="color: {{ '#00ff00' if row[1]=='Owner' else '#ff4444' }}">{{ row[1] }}</td>
                <td>{{ row[2] }}</td>
                <td><a href="/logs/{{ row[3] }}" target="_blank"><img src="/logs/{{ row[3] }}"></a></td>
            </tr>
            {% endfor %}
        </table>
    </body>
</html>
"""

@app.route('/')
def index(): return render_template_string(HTML_PAGE)

@app.route('/history')
def history():
    conn = sqlite3.connect(SQL_DB)
    c = conn.cursor()
    c.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return render_template_string(HISTORY_PAGE, rows=rows)

@app.route('/logs/<filename>')
def serve_log(filename):
    return send_from_directory(LOG_DIR, filename)

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with lock:
                if output_frame is None: continue
                (flag, encodedImage) = cv2.imencode(".jpg", output_frame)
            yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- TELEGRAM ALERTS ---
def send_telegram(msg, frame):
    try:
        _, img_encoded = cv2.imencode('.jpg', frame)
        files = {'photo': ('image.jpg', img_encoded.tobytes())}
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={'chat_id': CHAT_ID, 'text': msg})
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data={'chat_id': CHAT_ID}, files=files)
    except Exception as e:
        print(f"Telegram Error: {e}")

# --- AI PROCESSING ---
def run_ai():
    global output_frame
    init_db()
    
    # Load known face data
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found. Please create face encodings first.")
        return

    with open(DB_PATH, "rb") as f:
        known_encodings = [pickle.load(f)["Owner"]]

    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
    picam2.start()

    last_log_time = 0
    last_telegram_time = 0
    unknown_start_time = None

    while True:
        frame_raw = picam2.capture_array()
        frame_bgr = cv2.cvtColor(frame_raw, cv2.COLOR_RGBA2BGR)
        small_frame = cv2.resize(frame_bgr, (0, 0), fx=0.25, fy=0.25)
        rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_small)
        face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

        owner_found = False
        anyone_present = len(face_encodings) > 0

        for face_encoding in face_encodings:
            face_distances = face_recognition.face_distance(known_encodings, face_encoding)
            confidence = f"{round((1 - face_distances[0]) * 100, 1)}%" if len(face_distances) > 0 else "0%"
           
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.55)
            if True in matches:
                owner_found = True
                # Log Owner every 5 minutes
                if time.time() - last_log_time > 300:
                    log_event("Owner", confidence, frame_bgr)
                    last_log_time = time.time()
                # Telegram Greeting (30 min cooldown)
                if time.time() - last_telegram_time > 1800:
                    send_telegram("👋 Owner is home.", frame_bgr)
                    last_telegram_time = time.time()
           
        # Intruder Logic (3 second persistent face)
        if anyone_present and not owner_found:
            if unknown_start_time is None: unknown_start_time = time.time()
            elif time.time() - unknown_start_time > 3:
                log_event("Unknown", "-", frame_bgr)
                send_telegram("⚠️ INTRUDER ALERT: Unknown person detected!", frame_bgr)
                unknown_start_time = None
        else:
            unknown_start_time = None

        # Draw UI boxes
        for (top, right, bottom, left) in face_locations:
            color = (0, 255, 0) if owner_found else (0, 0, 255)
            cv2.rectangle(frame_bgr, (left*4, top*4), (right*4, bottom*4), color, 2)

        with lock:
            output_frame = frame_bgr.copy()

if __name__ == "__main__":
    threading.Thread(target=run_ai, daemon=True).start()
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)

