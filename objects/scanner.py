"""Scan the wall between rounds: calibrate from the projected corner markers,
find the paper markers, and build a Layout.

The caller (main.py) shows the calibration screen first, then calls scan().
Nothing here touches pygame or the engine's state, so it can be tested with
synthetic frames.
"""

import time
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from engine import Layout

from .calibration import Calibration, CalibrationError, corner_cells
from .camera import open_camera, read_frame
from .detector import MarkerDetector
from .layout_builder import build_layout
from .markers import CALIBRATION, CORNER_IDS, classify


class ScanError(RuntimeError):
    """The scan couldn't produce a layout (no camera, corners not visible...)."""


@dataclass
class ScanResult:
    layout: Layout
    calibration: Calibration
    warnings: list = field(default_factory=list)
    frames: int = 0


def analyze(detections_per_frame, width, height, reserved=(), min_fraction=0.6):
    """Turn several frames' worth of detections into a ScanResult.

    A calibration corner counts if it's seen in at least min_fraction of the
    frames; its position is averaged across them. A paper marker counts if
    the same (ID, cell) shows up in at least min_fraction of the frames, so
    one glitchy frame can't add or remove an object.
    """
    n = len(detections_per_frame)
    if n == 0:
        raise ScanError("no camera frames to scan")
    need = max(1, int(np.ceil(min_fraction * n)))

    corner_seen = {i: [] for i in CORNER_IDS}
    for detections in detections_per_frame:
        for d in detections:
            if d.id in corner_seen:
                corner_seen[d.id].append(d.corners)
    observed = {i: np.mean(seen, axis=0) for i, seen in corner_seen.items()
                if len(seen) >= need}
    try:
        calibration = Calibration.from_corners(observed, width, height)
    except CalibrationError as e:
        raise ScanError(str(e)) from e

    votes = Counter()
    for detections in detections_per_frame:
        # set(): a marker seen twice in one frame (impossible, but cheap) votes once.
        votes.update({(d.id, calibration.cell_at(d.center)) for d in detections
                      if classify(d.id).kind != CALIBRATION})
    placements = [key for key, count in votes.items() if count >= need]

    warnings = []
    if calibration.rms_error_cells > 0.25:
        warnings.append(f"calibration is rough ({calibration.rms_error_cells:.2f} cells "
                        "of error); check the camera is steady and the corners are flat")
    hidden = set(corner_cells(width, height))
    layout, layout_warnings = build_layout(placements, width, height,
                                           reserved=set(reserved) | hidden)
    return ScanResult(layout, calibration, warnings + layout_warnings, n)


class Scanner:
    """Owns the camera. Opened on the first scan and kept open, so later
    scans don't pay the camera's start-up time again."""

    def __init__(self, source, frames=10, settle_s=0.5, min_fraction=0.6,
                 width=1920, height=1080):
        self.source = source
        self.frames = frames
        self.settle_s = settle_s
        self.min_fraction = min_fraction
        self.size = (width, height)
        self.detector = MarkerDetector()
        self._cap = None

    def _camera(self):
        if self._cap is None:
            try:
                self._cap = open_camera(self.source, *self.size)
            except RuntimeError as e:
                raise ScanError(str(e)) from e
        return self._cap

    def scan(self, width, height, reserved=(), tick=None):
        """Capture frames and analyze them. Call while the calibration screen
        is showing. tick() is called between frames (e.g. pygame.event.pump)
        so the window stays responsive."""
        cap = self._camera()

        # Throw away frames for a moment: the camera buffers old frames, and
        # the projector and auto-exposure need time to catch up with the
        # calibration screen.
        deadline = time.monotonic() + self.settle_s
        while time.monotonic() < deadline:
            if read_frame(cap) is None:
                raise ScanError("camera stopped sending frames")
            if tick:
                tick()

        detections = []
        for _ in range(self.frames):
            frame = read_frame(cap)
            if frame is None:
                raise ScanError("camera stopped sending frames")
            detections.append(self.detector.detect(frame))
            if tick:
                tick()
        return analyze(detections, width, height, reserved, self.min_fraction)

    def close(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
