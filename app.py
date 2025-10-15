#!/usr/bin/env python3
# app.py — main entry point for Flask server

import time
import threading
import logging
import atexit
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS

# Local modules
from led import setup_led, cleanup_led, led_on, led_off, led_blink
from camera import mjpeg_generator
from storage import create_presigned_upload_url, create_presigned_view_url, list_s3_objects

# ===== Flask setup =====
app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pi_server")

# Initialize LED
setup_led()

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
        log.info(f"Calling led_off(), current LED state: {_led_state}")
        led_off()
        _led_state = False
        log.info(f"LED forced off successfully, new state: {_led_state}")
    except Exception as e:
        log.error(f"Failed to turn off LED: {e}")

def _force_led_on():
    """Force LED on and update state"""
    global _led_state
    try:
        led_on()
        _led_state = True
        log.info("LED forced on")
    except Exception as e:
        log.error(f"Failed to turn on LED: {e}")

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
    log.info("Stop stream request received")
    with _stream_lock:
        stopped_count = 0
        log.info(f"Current sessions before stop: {list(_stream_sessions.keys())}")
        
        # First, mark all sessions as inactive to stop camera generation
        for session_id in list(_stream_sessions.keys()):
            if _stream_sessions[session_id]["active"]:
                _stream_sessions[session_id]["active"] = False
                stopped_count += 1
                log.info(f"Marked session {session_id} as inactive")
        
        # Clear all sessions immediately
        _stream_sessions.clear()
        log.info("Cleared all sessions")
        
        # Force LED off regardless
        log.info(f"About to force LED off, current LED state: {_led_state}")
        _force_led_off()
        log.info(f"Stopped {stopped_count} sessions and forced LED off. Final LED state: {_led_state}")
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
    led_blink(duration=0.5)
    image_bytes = take_snapshot(quality=90)
    return Response(image_bytes, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

@app.route("/camera/upload", methods=["POST"])
def camera_upload():
    """Take a snapshot and upload it to S3, return the S3 URLs"""
    from camera import take_snapshot
    import boto3
    import uuid
    
    # Flash LED before taking snapshot
    led_blink(duration=0.5)
    
    # Take snapshot
    image_bytes = take_snapshot(quality=90)
    
    # Generate S3 key
    filename = f"{int(time.time())}.jpg"
    user_id = request.headers.get("X-User-Id", "anon")
    key = f"users/{user_id}/{uuid.uuid4()}-{filename}"
    
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

# ====== Debug & admin ======
@app.route("/debug/sessions", methods=["GET"])
def debug_sessions():
    with _stream_lock:
        return jsonify({
            "active_sessions": len(_stream_sessions),
            "sessions": _stream_sessions
        })

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

@app.route("/debug/cleanup", methods=["POST"])
def debug_cleanup():
    """Manually clean up all sessions"""
    with _stream_lock:
        session_count = len(_stream_sessions)
        for session_id in list(_stream_sessions.keys()):
            _stream_sessions[session_id]["active"] = False
        _stream_sessions.clear()
        _force_led_off()
    return jsonify({"status": "cleaned up", "sessions_removed": session_count, "led_state": _led_state})

@app.route("/led/status", methods=["GET"])
def led_status():
    """Get current LED status"""
    return jsonify({"led_on": _led_state, "active_sessions": len(_stream_sessions)})

@app.route("/led/test", methods=["POST"])
def test_led():
    """Test LED functionality - turn on for 2 seconds then off"""
    try:
        log.info("Testing LED functionality")
        _force_led_on()
        time.sleep(2)
        _force_led_off()
        return jsonify({"status": "success", "message": "LED test completed"})
    except Exception as e:
        log.error(f"LED test failed: {e}")
        return jsonify({"status": "error", "message": f"LED test failed: {str(e)}"}), 500

# ====== Cleanup ======
@atexit.register
def _cleanup():
    """Clean up resources on exit."""
    cleanup_led()

# ====== Main ======
def main():
    log.info("🚀 Starting Flask Pi Server...")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True, use_reloader=False)

if __name__ == "__main__":
    main()
