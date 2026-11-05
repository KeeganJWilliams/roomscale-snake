"""Generate printable ArUco markers (DICT_4X4_50) as PNG files in ./markers/

Each image has a white border (the 'quiet zone') and the ID printed underneath.
Print them at about 6-7 cm for the black square, on MATTE paper.
"""
import os
import cv2
import numpy as np

DICTIONARY = cv2.aruco.DICT_4X4_50
IDS = range(0, 20)        # which IDs to generate (0-49 are valid for 4X4_50)
MARKER_PX = 600           # size of the black marker square in pixels
BORDER_PX = 150           # white border around it (>= 1 cell = 100 px here)
LABEL_PX = 80             # space below for the ID text

dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY)
os.makedirs("markers", exist_ok=True)

for marker_id in IDS:
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, MARKER_PX)
    h = MARKER_PX + 2 * BORDER_PX + LABEL_PX
    w = MARKER_PX + 2 * BORDER_PX
    canvas = np.full((h, w), 255, dtype=np.uint8)
    canvas[BORDER_PX:BORDER_PX + MARKER_PX, BORDER_PX:BORDER_PX + MARKER_PX] = marker
    cv2.putText(canvas, f"ID {marker_id}", (BORDER_PX, h - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 3, cv2.LINE_AA)
    cv2.imwrite(os.path.join("markers", f"marker_{marker_id:02d}.png"), canvas)

print(f"Saved {len(list(IDS))} markers to the 'markers' folder.")
