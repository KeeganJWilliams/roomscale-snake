"""Zone occupancy -> debounced steering commands.

Pure and synchronous: no I/O, no threads, no aiohomekit, and the clock is
injected, so the whole state machine is unit-testable and easy to retune.
"""

import time
from dataclasses import dataclass

from engine import Direction

from ..base import PlayerFound, PlayerLost, Turn

#: Zone names the config must define.
ZONE_NAMES = ("center", "up", "down", "left", "right")

#: The four that steer; "center" is neutral and keeps the current heading.
DIRECTION_ZONES = {
    "up": Direction.UP,
    "down": Direction.DOWN,
    "left": Direction.LEFT,
    "right": Direction.RIGHT,
}


@dataclass(frozen=True)
class ZoneEvent:
    """One OccupancyDetected change.

    key is 'aid.iid' (e.g. '1.13') because HomeKit zone names don't
    reliably match the Aqara app's, so zones are identified by id.
    """

    key: str
    occupied: bool
    t_recv_ns: int = 0


class Steering:
    """Turns raw zone on/off events into Commands.

    Rules (see FP2_INPUT_ADAPTER.md):
      - exactly one direction zone -> Turn once it has held debounce_ms
      - only center -> keep heading, and re-arm so the same direction can
        be chosen again next time
      - two direction zones -> ignored, the player is straddling a line
      - pad empty for lost_grace_ms -> one PlayerLost; the grace exists
        because the FP2 can briefly report every zone off mid-step
      - any zone back on after that -> PlayerFound
      - events from unmapped keys are ignored
    """

    def __init__(self, zones, debounce_ms=150, lost_grace_ms=1000,
                 clock=time.monotonic):
        self.by_key = {key: name for name, key in zones.items()}
        self.debounce_s = debounce_ms / 1000.0
        self.lost_grace_s = lost_grace_ms / 1000.0
        self.clock = clock

        self.occupied = set()
        self.candidate = None      # direction zone waiting out the debounce
        self.since = 0.0           # when candidate was first proposed
        self.cause = None          # the ZoneEvent that proposed it
        self.current = None        # direction already handed to the Engine
        # Start out "empty": if no event ever arrives (sensor missing or
        # nobody on the pad yet) the grace period still pauses the game.
        self.empty_since = self.clock()
        self.lost = False
        self._last = ZoneEvent("", False, 0)

    # --- input ---------------------------------------------------------------

    def update(self, event):
        """Apply one ZoneEvent. Returns the Commands it caused immediately."""
        zone = self.by_key.get(event.key)
        if zone is None:
            return []
        self._last = event

        if event.occupied:
            self.occupied.add(zone)
        else:
            self.occupied.discard(zone)

        if self.occupied:
            self.empty_since = None
        elif self.empty_since is None:
            self.empty_since = self.clock()

        commands = []
        if self.lost and self.occupied:
            self.lost = False
            commands.append(PlayerFound(event.t_recv_ns, event.key))

        active = [name for name in DIRECTION_ZONES if name in self.occupied]
        if len(active) == 1:
            self._propose(active[0], event)
        elif active or "center" in self.occupied:
            # Two direction zones at once means the player is straddling a
            # boundary: ambiguous, so cancel any pending turn rather than
            # letting the zone they happened to touch first win. Centre
            # alone is the same neutral state - keep the current heading.
            self._propose(None, event)
        # Nothing occupied: the empty-pad grace period handles it.
        return commands

    def mark_sensor_offline(self):
        """The sensor is unreachable: drop stale zone state and pause once."""
        self.occupied.clear()
        self.candidate, self.cause = None, None
        self.empty_since = self.clock()
        if self.lost:
            return []
        self.lost = True
        return [PlayerLost(self._last.t_recv_ns, self._last.key)]

    def _propose(self, zone, event):
        if zone != self.candidate:
            self.candidate, self.since, self.cause = zone, self.clock(), event

    # --- tick ----------------------------------------------------------------

    def tick(self):
        """Call every frame. Emits turns once a zone has held long enough."""
        now = self.clock()

        if self.empty_since is not None:
            if not self.lost and now - self.empty_since >= self.lost_grace_s:
                self.lost, self.candidate, self.cause = True, None, None
                return [PlayerLost(self._last.t_recv_ns, self._last.key)]
            return []

        candidate = self.candidate
        if candidate is None:
            # Standing in the centre: forget the last turn so stepping the
            # same way again counts as a new one.
            self.current = None
        elif candidate != self.current and now - self.since >= self.debounce_s:
            self.current = candidate
            # Stamped with the event that proposed this direction, not
            # whatever arrived last, so O3 measures the real latency.
            cause = self.cause or self._last
            return [Turn(DIRECTION_ZONES[candidate], cause.t_recv_ns, cause.key)]
        return []
