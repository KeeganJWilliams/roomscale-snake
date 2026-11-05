"""Find which camera index is which. Run:  python list_cameras.py
Saves a test photo from each working camera (camera_0.jpg, camera_1.jpg, ...)
so you can open them and see which one is the ELP camera.
"""
import time
import cv2

for index in range(4):
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        print(f"Index {index}: cannot open")
        continue
    frame = None
    for _ in range(60):          # give the camera up to ~3 s to warm up
        ok, frame = cap.read()
        if ok and frame is not None:
            break
        time.sleep(0.05)
    if frame is None:
        print(f"Index {index}: opened but no frames (permission problem or wrong device)")
    else:
        h, w = frame.shape[:2]
        cv2.imwrite(f"camera_{index}.jpg", frame)
        print(f"Index {index}: OK, {w}x{h}, saved camera_{index}.jpg")
    cap.release()
