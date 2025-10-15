# camera.py
import io
import time
import threading
from picamera2 import Picamera2
from PIL import Image

_cam = None
_lock = threading.Lock()
_conf = {"size": (1280, 720), "format": "RGB888"}

def get_camera():
    global _cam
    if _cam is not None:
        return _cam
    with _lock:
        if _cam is not None:
            return _cam
        cam = Picamera2()
        cfg = cam.create_video_configuration(main=_conf, buffer_count=4)
        cam.configure(cfg)
        cam.start()
        _cam = cam
        return _cam

def encode_jpeg(arr, quality=85) -> bytes:
    im = Image.fromarray(arr)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def take_snapshot(quality=85) -> bytes:
    """Take a single snapshot and return JPEG bytes."""
    cam = get_camera()
    arr = cam.capture_array()
    arr = arr[..., ::-1].copy()  # BGR -> RGB
    return encode_jpeg(arr, quality=quality)

def mjpeg_generator(target_fps=8, quality=80, on_frame=lambda: None, should_continue=lambda: True):
    """Yieldar MJPEG-frames. on_frame() anropas för varje frame (t.ex. watchdog).
    should_continue() kontrollerar om generatorn ska fortsätta köra."""
    cam = get_camera()
    boundary = b"--frame"
    frame_interval = 1.0 / float(target_fps)
    next_time = time.time()
    while should_continue():
        arr = cam.capture_array()
        arr = arr[..., ::-1].copy()  # BGR -> RGB
        jpg = encode_jpeg(arr, quality=quality)
        on_frame()
        yield (
            boundary + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n"
        )
        next_time += frame_interval
        sleep_time = next_time - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)
