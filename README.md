# 🧠 Pi Server

A modular Flask-based backend for Raspberry Pi that provides REST APIs for **camera control**, **live streaming**, **LED management**, and **AWS S3 image uploads**.

## 🚀 Features

- 📸 Capture snapshots with the PiCamera2
- 🎥 MJPEG live stream from the Raspberry Pi camera
- 💡 LED control (on/off, brightness, blink on capture)
- ☁️ Direct image uploads to Amazon S3 with presigned URLs
- 🧩 Modular structure (`app.py`, `camera.py`, `led.py`, `storage.py`)
- 🔒 CORS enabled for external apps (e.g., mobile or web clients)

---

## 🧱 Project Structure

pi_server/
├── app.py # Main Flask app – registers routes and starts the server
├── camera.py # Camera handling (snapshot, stream)
├── led.py # LED control and helper functions
├── storage.py # AWS S3 upload and list logic
├── init.py # Makes the folder a Python package
└── .gitignore # Ignore build/cache files

yaml
Copy code

---

## ⚙️ Requirements

Install dependencies:
```bash
sudo apt update
sudo apt install python3-pip python3-flask python3-picamera2
pip install boto3 pillow flask-cors
▶️ Running the Server
bash
Copy code
cd ~/pi_server
python3 -m pi_server.app
The server starts on port 5000 by default:

cpp
Copy code
http://<pi-ip>:5000
🔌 API Endpoints
🩺 Health Check
bash
Copy code
GET /health
💡 LED Control
bash
Copy code
POST /led
{
  "state": "on" | "off"
}
📷 Take Snapshot
bash
Copy code
GET /camera/snapshot
☁️ Upload Snapshot to S3
bash
Copy code
POST /camera/upload
🎥 Live Stream
Open in browser:

arduino
Copy code
http://<pi-ip>:5000/camera/stream
☁️ AWS Setup
Create an S3 bucket (e.g. pi-photos-bucket)

Add AWS credentials in ~/.aws/credentials

Ensure environment variables:

bash
Copy code
export AWS_DEFAULT_REGION=eu-north-1
export S3_BUCKET=pi-photos-bucket
🧹 Cleanup
The app safely handles cleanup of GPIO and camera resources on shutdown:

python
Copy code
CTRL + C  # stops Flask and cleans up GPIO
🧑‍💻 Author
Anders
Built for Raspberry Pi with ❤️ and curiosity.

📜 License
MIT License
