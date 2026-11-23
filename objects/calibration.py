"""Camera-to-grid calibration.

The game projects four ArUco markers (IDs 0-3) at known spots in the grid's
corners. The camera finds them, and since we know both where each marker's
corners are in the camera image (pixels) and on the grid (cell units), we
can fit a homography that maps any camera pixel to a grid position.

Grid units: (0, 0) is the grid's top-left corner, (width, height) its
bottom-right corner, and cell (x, y) covers [x, x+1) x [y, y+1). This module
knows nothing about screen pixels, so the renderer and the scanner can't
disagree about where the markers are.
"""

import cv2
import numpy as np

from .markers import CORNER_IDS, DICTIONARY_ID

# Each calibration marker lives in a CORNER_CELLS x CORNER_CELLS block in its
# grid corner. The black square is inset by CORNER_INSET cells so there's a
# white quiet zone around it on the projected white background. Physical
# markers placed in these corner blocks are hidden by the projection during
# a scan, so keep them out of the corners.
CORNER_CELLS = 2
CORNER_INSET = 0.25


class CalibrationError(RuntimeError):
    """Calibration failed (missing corners, degenerate fit)."""


def corner_block_origin(marker_id, width, height):
    """Top-left of the corner block for calibration marker 0-3, in grid units."""
    name = CORNER_IDS[marker_id]
    x = 0 if name.endswith("left") else width - CORNER_CELLS
    y = 0 if name.startswith("top") else height - CORNER_CELLS
    return x, y


def corner_targets(width, height):
    """{marker_id: (left, top, size)} for the black square of each projected
    calibration marker, in grid units."""
    size = CORNER_CELLS - 2 * CORNER_INSET
    targets = {}
    for marker_id in CORNER_IDS:
        bx, by = corner_block_origin(marker_id, width, height)
        targets[marker_id] = (bx + CORNER_INSET, by + CORNER_INSET, size)
    return targets


def corner_cells(width, height):
    """Every grid cell covered by a calibration corner block."""
    cells = set()
    for marker_id in CORNER_IDS:
        bx, by = corner_block_origin(marker_id, width, height)
        cells.update((bx + i, by + j) for i in range(CORNER_CELLS)
                     for j in range(CORNER_CELLS))
    return cells


def marker_corner_points(left, top, size):
    """The 4 corners of an upright square, in the order OpenCV reports a
    detected marker's corners: top-left, top-right, bottom-right, bottom-left."""
    return np.array([[left, top], [left + size, top],
                     [left + size, top + size], [left, top + size]], dtype=np.float64)


def calibration_marker_bitmap(marker_id, bit_px=40):
    """Black-and-white image of one projected calibration marker (no border)."""
    dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY_ID)
    return cv2.aruco.generateImageMarker(dictionary, marker_id, 6 * bit_px)


class Calibration:
    """Maps camera pixels to grid positions."""

    def __init__(self, homography, rms_error_cells):
        self.homography = homography
        self.rms_error_cells = rms_error_cells   # fit quality, in cells

    @classmethod
    def from_corners(cls, observed, width, height):
        """Fit from observed calibration markers.

        observed: {marker_id: 4x2 array of camera-pixel corners} for IDs 0-3.
        Uses all 16 marker corners, not just the 4 centers, for a steadier fit.
        """
        missing = [CORNER_IDS[i].replace("_", " ") for i in CORNER_IDS if i not in observed]
        if len(missing) == len(CORNER_IDS):
            raise CalibrationError(
                "camera can't see any calibration markers. Check that it's pointed "
                "at the projection and the room isn't too bright.")
        if missing:
            raise CalibrationError(
                "camera can't see the " + ", ".join(missing) + " calibration marker"
                + ("s" if len(missing) > 1 else "")
                + ". Check that the whole grid is in the camera's view.")

        targets = corner_targets(width, height)
        src = np.vstack([np.asarray(observed[i], dtype=np.float64).reshape(4, 2)
                         for i in CORNER_IDS])
        dst = np.vstack([marker_corner_points(*targets[i]) for i in CORNER_IDS])
        homography, _ = cv2.findHomography(src, dst, 0)
        if homography is None:
            raise CalibrationError("couldn't fit the camera-to-grid transform")

        mapped = cv2.perspectiveTransform(src.reshape(-1, 1, 2), homography).reshape(-1, 2)
        rms = float(np.sqrt(np.mean(np.sum((mapped - dst) ** 2, axis=1))))
        return cls(homography, rms)

    def to_grid(self, points):
        """Camera pixels (N x 2) -> grid units (N x 2)."""
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.homography).reshape(-1, 2)

    def cell_at(self, point):
        """Camera pixel (x, y) -> the grid cell it falls in (may be off-grid)."""
        gx, gy = self.to_grid([point])[0]
        return int(np.floor(gx)), int(np.floor(gy))
