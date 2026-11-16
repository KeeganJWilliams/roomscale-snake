"""Generate printable ArUco markers (DICT_4X4_50) as PNGs in ./markers/

    python -m objects.generate_markers              # all printable reserved IDs
    python -m objects.generate_markers --ids 10 11  # just these

Each image has a white border (the "quiet zone") and its ID and role
printed underneath. Calibration corners (0-3) are skipped by default since
the game projects them. Print on MATTE paper, no glossy lamination.

Print size isn't fixed yet: each marker should appear ~40-60 px wide in the
camera image, so work it out once projection size and camera distance are
measured.
"""

import argparse
import os

import cv2
import numpy as np

from .markers import DICTIONARY_ID, MAX_ID, PRINTABLE_IDS, label

MARKER_PX = 600   # black marker square (4x4 data + 1-cell border = 6 cells, 100 px each)
BORDER_PX = 150   # white quiet zone, at least one cell wide
LABEL_PX = 80     # space below for the text


def render_marker(dictionary, marker_id):
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, MARKER_PX)
    h = MARKER_PX + 2 * BORDER_PX + LABEL_PX
    w = MARKER_PX + 2 * BORDER_PX
    canvas = np.full((h, w), 255, dtype=np.uint8)
    canvas[BORDER_PX:BORDER_PX + MARKER_PX, BORDER_PX:BORDER_PX + MARKER_PX] = marker
    cv2.putText(canvas, f"ID {marker_id}  {label(marker_id)}", (BORDER_PX, h - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 1.4, 0, 3, cv2.LINE_AA)
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", type=int, nargs="+", default=PRINTABLE_IDS,
                        help=f"marker IDs to generate (0-{MAX_ID})")
    parser.add_argument("--out", default="markers", help="output folder")
    args = parser.parse_args()

    bad = [i for i in args.ids if not 0 <= i <= MAX_ID]
    if bad:
        parser.error(f"IDs must be 0-{MAX_ID}: {bad}")

    dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY_ID)
    os.makedirs(args.out, exist_ok=True)
    for marker_id in args.ids:
        path = os.path.join(args.out, f"marker_{marker_id:02d}.png")
        cv2.imwrite(path, render_marker(dictionary, marker_id))
    print(f"Saved {len(args.ids)} markers to '{args.out}'.")


if __name__ == "__main__":
    main()
