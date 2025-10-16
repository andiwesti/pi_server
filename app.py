#!/usr/bin/env python3
# app.py — main entry point for Flask server

import time
import threading
import logging
import atexit
from datetime import datetime
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS

# Local modules
from led import setup_led, cleanup_led, led_on, led_off
from camera import mjpeg_generator
from storage import create_presigned_upload_url, create_presigned_view_url, list_s3_objects

# ===== Flask setup =====
app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pi_server")

# LED will be initialized in main() function

# ===== Session tracking for camera streams =====
_stream_sessions = {}
_stream_lock = threading.Lock()
_led_state = False  # Track LED state globally

def _create_session():
    """Create a new unique streaming session."""
    import uuid
    sid = str(uuid.uuid4())
    with _stream_lock:
        _stream_sessions[sid] = {
            "created": time.time(),
            "last_yield": None,
            "active": True,
            "led_on": False
        }
    return sid

def _stop_session(sid):
    """Stop a specific session and turn off LED if no sessions remain."""
    global _led_state
    with _stream_lock:
        if sid in _stream_sessions:
            _stream_sessions[sid]["active"] = False
            if _stream_sessions[sid].get("led_on"):
                _force_led_off()
                log.info(f"LED turned off for session {sid}")
            del _stream_sessions[sid]
            log.info(f"Stopped stream session: {sid}")

        # Always turn off LED when stopping a session
        _force_led_off()

def _force_led_off():
    """Force LED off and update state"""
    global _led_state
    try:
        led_off()
        _led_state = False
    except Exception as e:
        log.error(f"Failed to turn off LED: {e}")

def _force_led_on():
    """Force LED on and update state"""
    global _led_state
    try:
        led_on()
        _led_state = True
    except Exception as e:
        log.error(f"Failed to turn on LED: {e}")

def _flash_led_for_capture():
    """Flash LED for capture, then restore to stream state if streaming"""
    global _led_state
    was_streaming = any(s.get("led_on", False) for s in _stream_sessions.values())
    
    # Flash off-on-off
    led_off()
    time.sleep(0.1)
    led_on()
    time.sleep(0.1)
    led_off()
    time.sleep(0.1)
    
    # Restore LED state based on streaming status
    if was_streaming:
        led_on()
        _led_state = True
    else:
        _led_state = False

def _cleanup_stale_sessions():
    """Clean up sessions that haven't yielded frames in 3 seconds"""
    current_time = time.time()
    stale_sessions = []
    
    with _stream_lock:
        for session_id, session in _stream_sessions.items():
            if session["active"]:
                # Clean up sessions that never yielded (last_yield is None) and are older than 5 seconds
                if session["last_yield"] is None and (current_time - session["created"] > 5.0):
                    log.warning(f"Cleaning up session {session_id} - never yielded frames after 5 seconds")
                    _stop_session(session_id)
                    stale_sessions.append(session_id)
                # Clean up sessions that yielded but haven't yielded in 3 seconds
                elif session["last_yield"] and (current_time - session["last_yield"] > 3.0):
                    log.warning(f"Cleaning up stale session {session_id} - no activity for 3+ seconds")
                    _stop_session(session_id)
                    stale_sessions.append(session_id)
        
        # Remove stale sessions from tracking
        for session_id in stale_sessions:
            if session_id in _stream_sessions:
                del _stream_sessions[session_id]
        
        # If we cleaned up sessions, force LED off
        if stale_sessions:
            _force_led_off()
            log.info(f"Cleaned up {len(stale_sessions)} stale sessions and forced LED off")

def _watchdog_loop():
    """Background thread to clean up stale sessions"""
    while True:
        _cleanup_stale_sessions()
        time.sleep(2)  # Check every 2 seconds

# Start watchdog thread
threading.Thread(target=_watchdog_loop, daemon=True).start()

# ====== Routes ======

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/s3/upload-url", methods=["POST"])
def s3_upload_url():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(create_presigned_upload_url(data))

@app.route("/s3/view-url", methods=["POST"])
def s3_view_url():
    data = request.get_json(force=True)
    return jsonify(create_presigned_view_url(data))

@app.route("/s3/list", methods=["GET"])
def s3_list():
    prefix = request.args.get("prefix", "users/")
    return jsonify(list_s3_objects(prefix))

@app.route('/camera/stream', methods=['GET'])
def camera_stream():
    # Get or create session ID
    session_id = request.args.get('session_id')
    if not session_id:
        session_id = _create_session()
        log.info(f"Created new stream session: {session_id}")
    else:
        # Resume existing session
        if session_id not in _stream_sessions:
            return jsonify({"error": "Invalid session ID"}), 400
        _stream_sessions[session_id]["active"] = True
        log.info(f"Resumed stream session: {session_id}")
    
    # Turn on LED for this session
    _force_led_on()
    _stream_sessions[session_id]["led_on"] = True

    def gen():
        def should_continue():
            """Check if the session is still active - this stops the camera from generating frames"""
            return session_id in _stream_sessions and _stream_sessions[session_id]["active"]
        
        try:
            for frame in mjpeg_generator(
                target_fps=8, 
                quality=80, 
                on_frame=lambda: _on_frame_session(session_id),
                should_continue=should_continue
            ):
                # Try to yield the frame - this will raise an exception if client disconnected
                try:
                    yield frame
                except (GeneratorExit, BrokenPipeError, ConnectionError, OSError, IOError) as e:
                    # Client disconnected during yield
                    log.info(f"Client disconnected during yield for session {session_id}: {type(e).__name__}")
                    break
                    
        except (GeneratorExit, BrokenPipeError, ConnectionError, OSError, IOError):
            # Client disconnected
            log.info(f"Client disconnected for session {session_id}")
        except Exception as e:
            log.warning(f"Unexpected exception in stream generator for session {session_id}: {e}")
        finally:
            # Clean up session
            _stop_session(session_id)

    def _on_frame_session(sid):
        """Update session timestamp when frame is yielded"""
        if sid in _stream_sessions:
            _stream_sessions[sid]["last_yield"] = time.time()

    # Create response
    resp = Response(
        stream_with_context(gen()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Connection": "close",
            "X-Session-ID": session_id,  # Include session ID in response headers
        },
    )

    return resp

@app.route("/camera/stream/stop", methods=["POST"])
def stop_camera_stream():
    """Stop all active camera streams and turn off LED"""
    with _stream_lock:
        stopped_count = 0
        
        # First, mark all sessions as inactive to stop camera generation
        for session_id in list(_stream_sessions.keys()):
            if _stream_sessions[session_id]["active"]:
                _stream_sessions[session_id]["active"] = False
                stopped_count += 1
        
        # Clear all sessions immediately
        _stream_sessions.clear()
        
        # Force LED off regardless
        _force_led_off()
    return jsonify({"status": "stopped", "sessions_stopped": stopped_count, "led_state": _led_state})

@app.route("/camera/stream/state", methods=["GET"])
def camera_stream_state():
    """Get the current state of camera streams"""
    with _stream_lock:
        active_sessions = len([s for s in _stream_sessions.values() if s["active"]])
        return jsonify({
            "streaming": active_sessions > 0,
            "active_sessions": active_sessions,
            "led_on": any(s.get("led_on", False) for s in _stream_sessions.values())
        })

@app.route("/camera/snapshot", methods=["GET"])
def camera_snapshot():
    from camera import take_snapshot
    # Flash LED before taking snapshot
    _flash_led_for_capture()
    image_bytes = take_snapshot(quality=90)
    return Response(image_bytes, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

@app.route("/camera/upload", methods=["POST"])
def camera_upload():
    """Take a snapshot and upload it to S3, return the S3 URLs"""
    from camera import take_snapshot
    import boto3
    import uuid
    
    # Flash LED before taking snapshot
    _flash_led_for_capture()
    
    # Take snapshot
    image_bytes = take_snapshot(quality=90)
    
    # Generate S3 key with human-readable timestamp + short session ID
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_id = request.headers.get("X-Session-Id", str(uuid.uuid4())[:6])
    filename = f"photo_{timestamp}_{session_id}.jpg"
    user_id = request.headers.get("X-User-Id", "anon")
    key = f"users/{user_id}/{filename}"
    
    # Upload to S3
    s3 = boto3.client("s3", region_name="eu-north-1")
    s3.put_object(
        Bucket="pi-photos-bucket",
        Key=key,
        Body=image_bytes,
        ContentType="image/jpeg"
    )
    
    # Generate view URL
    view_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": "pi-photos-bucket", "Key": key},
        ExpiresIn=3600,
    )
    
    return jsonify({
        "status": "uploaded",
        "key": key,
        "viewUrl": view_url
    })

# ====== LED Control ======
@app.route("/led", methods=["POST"])
def control_led():
    """Manually control LED on/off"""
    try:
        data = request.get_json() or {}
        state = (data.get('state') or '').lower()
        if state == 'on':
            _force_led_on()
            return jsonify({"status": "success", "message": "LED turned on", "led_state": _led_state})
        else:
            _force_led_off()
            return jsonify({"status": "success", "message": "LED turned off", "led_state": _led_state})
    except Exception as e:
        log.error(f"Error controlling LED: {e}")
        return jsonify({"status": "error", "message": f"Failed to control LED: {str(e)}", "led_state": _led_state}), 500

@app.route("/led/status", methods=["GET"])
def led_status():
    """Get current LED status"""
    return jsonify({"led_on": _led_state, "active_sessions": len(_stream_sessions)})

@app.route("/brightness", methods=["POST", "OPTIONS"])
def brightness_control():
    """Handle brightness control requests"""
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json() or {}
    brightness = data.get('brightness', 100)
    
    # For now, just return success since we don't have brightness control
    # You could implement PWM brightness control here if needed
    return jsonify({"status": "success", "brightness": brightness})

# ====== Main ======
def main():
    log.info("🚀 Starting Flask Pi Server...")
    
    # Initialize LED
    setup_led()
    
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True, use_reloader=False)

if __name__ == "__main__":
    main()
