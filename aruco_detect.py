"""Live ArUco marker detection (macOS, OpenCV 4.7+).

Controls:  Esc or q = quit
Tip: if you see the MacBook's built-in camera instead of the ELP camera,
change CAMERA_INDEX to 1 (or 2).
"""
import time
import cv2

# ---------------- Settings you may want to change ----------------
CAMERA_INDEX = 0                      # 0 = usually built-in cam, 1 = usually the external ELP
DICTIONARY = cv2.aruco.DICT_4X4_50    # must match the markers you printed
WIDTH, HEIGHT, FPS = 1920, 1080, 30   # drop to 1280x720 if this doesn't work
# ------------------------------------------------------------------

cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_AVFOUNDATION)
if not cap.isOpened():
    raise SystemExit(
        "Could not open the camera. Check the camera index, and that VS Code/Terminal "
        "has Camera permission (System Settings > Privacy & Security > Camera)."
    )

cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
cap.set(cv2.CAP_PROP_FPS, FPS)
print("Actual resolution:",
      int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "x", int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY)
params = cv2.aruco.DetectorParameters()
params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
params.adaptiveThreshWinSizeMax = 53   # helps with uneven lighting
detector = cv2.aruco.ArucoDetector(dictionary, params)

last_ids = None
failures = 0
while True:
    ok, frame = cap.read()
    if not ok or frame is None:
        # The first frames often fail on macOS while the camera warms up or the
        # permission prompt is showing, so retry for a few seconds before giving up.
        failures += 1
        if failures > 100:
            print("Failed to read frames from the camera. Check Camera permission "
                  "and CAMERA_INDEX (run list_cameras.py).")
            break
        time.sleep(0.05)
        continue
    failures = 0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is not None:
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        found = sorted(int(i) for i in ids.flatten())
        for c, marker_id in zip(corners, ids.flatten()):
            cx, cy = c[0].mean(axis=0)   # marker center in pixels
            # TODO (snake game): map (cx, cy) to a grid cell and use marker_id
            #                    to decide portal / item / etc.
    else:
        found = []

    if found != last_ids:                # only print when the set of markers changes
        print("Detected IDs:", found)
        last_ids = found

    cv2.imshow("ArUco detection (Esc to quit)", cv2.resize(frame, (960, 540)))
    key = cv2.waitKey(1) & 0xFF
    if key in (27, ord("q")):
        break

cap.release()
cv2.destroyAllWindows()
