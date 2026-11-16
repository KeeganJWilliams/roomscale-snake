"""Objects: find ArUco markers on the projected wall and turn them into game objects.

Kept separate from the engine: the engine never imports this package. The
plan is for Objects to build an engine.Layout and hand it to
game.load_layout() between rounds.
"""

from .detector import Detection, MarkerDetector, draw_detections
from .markers import MarkerKind, classify, label

__all__ = ["Detection", "MarkerDetector", "MarkerKind", "classify", "draw_detections",
           "label"]
