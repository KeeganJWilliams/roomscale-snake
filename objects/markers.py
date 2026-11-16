"""Which ArUco IDs mean what. Shared by the detector, the generator, and
(later) the code that builds a Layout from detected markers.

Reserved IDs (DICT_4X4_50 only has IDs 0-49):
    0-3    calibration corners (projected by the game, not printed)
    10-19  portals, in pairs: 10/11, 12/13, 14/15, 16/17, 18/19
    20-29  keys:  key 20+n opens gate 30+n
    30-39  gates
    40-49  walls
"""

from dataclasses import dataclass

import cv2

DICTIONARY_ID = cv2.aruco.DICT_4X4_50
MAX_ID = 49

CALIBRATION = "calibration"
PORTAL = "portal"
KEY = "key"
GATE = "gate"
WALL = "wall"
UNKNOWN = "unknown"

# Calibration corner order, matching the grid corners they're projected on.
CORNER_IDS = {0: "top_left", 1: "top_right", 2: "bottom_right", 3: "bottom_left"}


@dataclass(frozen=True)
class MarkerKind:
    """What a marker ID stands for.

    kind:  one of the constants above.
    group: links markers that belong together. For portals it's the pair
           number (10 and 11 are both group 0), for keys and gates it's the
           key/gate id (key 21 and gate 31 are both group 1), for calibration
           it's the corner index. None for walls and unknown IDs.
    """

    kind: str
    group: int | None = None


def classify(marker_id):
    marker_id = int(marker_id)
    if 0 <= marker_id <= 3:
        return MarkerKind(CALIBRATION, marker_id)
    if 10 <= marker_id <= 19:
        return MarkerKind(PORTAL, (marker_id - 10) // 2)
    if 20 <= marker_id <= 29:
        return MarkerKind(KEY, marker_id - 20)
    if 30 <= marker_id <= 39:
        return MarkerKind(GATE, marker_id - 30)
    if 40 <= marker_id <= MAX_ID:
        return MarkerKind(WALL)
    return MarkerKind(UNKNOWN)


def label(marker_id):
    """Short human-readable name, e.g. 'portal 1A', 'key 2', 'wall'."""
    k = classify(marker_id)
    if k.kind == CALIBRATION:
        return f"corner {CORNER_IDS[int(marker_id)].replace('_', ' ')}"
    if k.kind == PORTAL:
        return f"portal {k.group + 1}{'AB'[int(marker_id) % 2]}"
    if k.kind in (KEY, GATE):
        return f"{k.kind} {k.group + 1}"
    return k.kind


# IDs worth printing: everything reserved except the calibration corners,
# which the game projects instead.
PRINTABLE_IDS = [i for i in range(MAX_ID + 1)
                 if classify(i).kind not in (CALIBRATION, UNKNOWN)]
