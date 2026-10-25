import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger(__name__)


class EventType(Enum):
    GAME_START = "game_start"
    DIRECTION_CHANGED = "direction_changed"
    FOOD_EATEN = "food_eaten"
    COLLISION = "collision"
    GAME_OVER = "game_over"
    PAUSED = "paused"
    RESUMED = "resumed"


@dataclass(frozen=True)
class Event:
    type: EventType
    tick: int
    data: dict = field(default_factory=dict)
    # Monotonic timestamp so telemetry can measure latency between stages.
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)


class EventBus:
    """Engine -> listeners (render, ambient, telemetry).

    Listeners only react to events. A listener that raises is logged and
    skipped so a failing ambient device can never break gameplay.
    """

    def __init__(self):
        self._handlers = defaultdict(list)
        self._all_handlers = []

    def subscribe(self, handler, event_type=None):
        """Call handler(event) for event_type, or for every event if None."""
        if event_type is None:
            self._all_handlers.append(handler)
        else:
            self._handlers[event_type].append(handler)

    def emit(self, event):
        for handler in self._all_handlers + self._handlers[event.type]:
            try:
                handler(event)
            except Exception:
                log.exception("Event handler %r failed on %s", handler, event.type)
