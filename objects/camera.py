"""Open a camera on Windows, macOS, or Linux, or an RTSP/video URL.

OpenCV's default backend (CAP_ANY) picks AVFoundation on macOS and
Media Foundation on Windows, so no platform-specific flags are needed.
"""

import time

import cv2


def parse_source(source):
    """'0' -> 0 (camera index); anything else (rtsp://..., a file) stays a string."""
    if isinstance(source, int):
        return source
    return int(source) if str(source).isdigit() else source


def open_camera(source=0, width=None, height=None, fps=None):
    """Open a camera index or URL. Raises RuntimeError if it can't be opened."""
    source = parse_source(source)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        hint = ("Run `python -m objects.list_cameras` to see which indexes work. "
                "On macOS, the terminal/VS Code also needs Camera permission "
                "(System Settings > Privacy & Security > Camera).")
        raise RuntimeError(f"Could not open camera {source!r}. {hint}")
    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if fps:
        cap.set(cv2.CAP_PROP_FPS, fps)
    return cap


def read_frame(cap, timeout=3.0):
    """Read one frame, retrying while the camera warms up.

    The first reads often fail right after opening (macOS permission prompt,
    Windows driver start-up), so keep trying for `timeout` seconds.
    Returns the frame, or None if nothing arrived in time.
    """
    deadline = time.monotonic() + timeout
    while True:
        ok, frame = cap.read()
        if ok and frame is not None:
            return frame
        if time.monotonic() > deadline:
            return None
        time.sleep(0.05)


def frame_size(cap):
    return int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
