# app.py
import os
import io
import time
import atexit
import logging
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

from pi_server.led import setup_led, cleanup_led, led_on, led_off, led_blink
from pi_server.camera import get_camera, encode_jpeg, mjpeg_generator
from pi_server import storage

# ---- Logg ----
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pi_server")

app = Flask(__name__)
CORS(app)

# Initiera LED (enkelt)
setup_led()

# ===== S3 endpoints =====
@app.route("/s3/upload-url", methods=["POST"])
def s3_upload_url():
    data = request.get_json(force=True, silent=True) or {}
    filename = data.get("filename") or f"{int(time.time())}.bin"
    content_type = data.get("contentType") or storage.guess_content_type(filename)
    user_id = request.headers.get("X-User-Id", "anon")
    key = storage.key_for(user_id, filename)
    return jsonify({
        "key": key,
        "uploadUrl": storage.presign_put(key, content_type),
        "viewUrl": storage.presign_get(key),
    })

@app.route("/s3/view-url", methods=["POST"])
def s3_view_url():
    data = request.get_json(force=True)
    key = data["key"]
    return jsonify({"url": storage.presign_get(key)})

@app.route("/s3/list", methods=["GET"])
def s3_list():
    # Enkelt list-API (prefix kan styras via ?prefix=)
    prefix = request.args.get("prefix", "users/")
    resp = storage.s3.list_objects_v2(Bucket=storage.S3_BUCKET, Prefix=prefix, MaxKeys=100)
    items = [
        {"key": o["Key"], "size": o.get("Size", 0), "lastModified": o.get("LastModified").isoformat()}
        for o in resp.get("Contents", [])
    ] if "Contents" in resp else []
    return jsonify({"items": items, "truncated": resp.get("IsTruncated", False)})

# ===== Kamera endpoints =====
@app.route('/camera/snapshot', methods=['GET'])
def camera_snapshot():
    led_blink(0.25)
    cam = get_camera()
    arr = cam.capture_array()
    arr = arr[..., ::-1].copy()
    jpg = encode_jpeg(arr, quality=90)
    return Response(jpg, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

@app.route('/camera/upload', methods=['POST'])
def camera_upload():
    led_blink(0.25)
    user_id = request.headers.get("X-User-Id", "anon")
    filename = f"{int(time.time())}.jpg"
    key = storage.key_for(user_id, filename)

    cam = get_camera()
    arr = cam.capture_array()
    arr = arr[..., ::-1].copy()
    jpg = encode_jpeg(arr, quality=90)
    storage.upload_bytes(key, jpg, content_type="image/jpeg")

    return jsonify({"status": "uploaded", "viewUrl": storage.presign_get(key), "key": key})

# ---- Minimal watchdog: släck LED om stream inte stängs rent ----
_streaming = False
_last_frame_ts = 0.0

def _on_frame():
    global _last_frame_ts
    _last_frame_ts = time.time()

def _watchdog_loop():
    global _streaming, _last_frame_ts
    while True:
        if _streaming and (time.time() - _last_frame_ts > 3.0):
            _streaming = False
            led_off()
        time.sleep(5)

import threading
threading.Thread(target=_watchdog_loop, daemon=True).start()

@app.route('/camera/stream', methods=['GET'])
def camera_stream():
    global _streaming, _last_frame_ts
    _streaming = True
    _last_frame_ts = time.time()
    led_on()

    def gen():
        try:
            for frame in mjpeg_generator(target_fps=8, quality=80, on_frame=_on_frame):
                yield frame
        except (GeneratorExit, BrokenPipeError, ConnectionError):
            pass
        finally:
            _streaming = False
            led_off()

    resp = Response(
        stream_with_context(gen()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Connection": "close",
        },
    )

    @resp.call_on_close
    def _on_close():
        global _streaming
        _streaming = False
        led_off()

    return resp

# ===== Övrigt =====
@app.route('/led', methods=['POST'])
def control_led():
    data = request.json or {}
    state = (data.get('state') or '').lower()
    if state == 'on':
        led_on()
    else:
        led_off()
    return jsonify({"status": f"LED turned {state}"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

# Städa på exit
@atexit.register
def _cleanup():
    cleanup_led()

if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True, use_reloader=False)
