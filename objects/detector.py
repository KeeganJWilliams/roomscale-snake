"""ArUco marker detection on a single frame. No camera code here, so it can
be tested with synthetic images and reused for live video or still photos.

Uses the ArucoDetector API that's been in plain opencv-python since 4.7
(older tutorials use cv2.aruco.detectMarkers, which no longer exists).
"""

from dataclasses import dataclass

import cv2
import numpy as np

from .markers import DICTIONARY_ID, MarkerKind, classify


@dataclass(frozen=True)
class Detection:
    id: int
    center: tuple          # (x, y) in camera pixels
    corners: np.ndarray    # 4x2 float array, clockwise from the marker's top-left

    @property
    def kind(self) -> MarkerKind:
        return classify(self.id)


class MarkerDetector:
    def __init__(self, dictionary_id=DICTIONARY_ID):
        dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        params.adaptiveThreshWinSizeMax = 53   # helps with uneven lighting
        self._detector = cv2.aruco.ArucoDetector(dictionary, params)

    def detect(self, frame):
        """Return a list of Detections sorted by ID. Accepts BGR or grayscale."""
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _rejected = self._detector.detectMarkers(gray)
        if ids is None:
            return []
        found = []
        for c, marker_id in zip(corners, ids.flatten()):
            pts = c.reshape(4, 2)
            cx, cy = pts.mean(axis=0)
            found.append(Detection(int(marker_id), (float(cx), float(cy)), pts))
        found.sort(key=lambda d: d.id)
        return found


def draw_detections(frame, detections):
    """Outline detected markers on a BGR frame in place (for debug windows)."""
    if detections:
        corners = [d.corners.reshape(1, 4, 2).astype(np.float32) for d in detections]
        ids = np.array([[d.id] for d in detections], dtype=np.int32)
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)
    return frame
