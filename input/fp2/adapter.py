"""Bridge between the async HomeKit client and the synchronous game loop.

The client runs its asyncio loop on a daemon background thread and drops
ZoneEvents on a thread-safe queue. The game loop calls poll() once per
frame, which drains the queue through the Steering state machine and
returns the Commands for that frame. Nothing here blocks, and a sensor
that disappears pauses the game instead of stalling it.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass

from .steering import Steering, ZoneEvent

log = logging.getLogger(__name__)

JOIN_TIMEOUT_S = 2.0


@dataclass(frozen=True)
class SensorStatus:
    """Queued alongside events so poll() sees connects and drops in order."""

    connected: bool


def default_client_factory(config, on_event, on_status):
    # Imported here so the rest of the game runs without aiohomekit.
    from .client import Fp2Client

    return Fp2Client(config, on_event, on_status)


class Fp2Input:
    """InputSource backed by an Aqara FP2.

    telemetry is an optional telemetry.ZoneEventLog; main.py supplies one
    so this module stays free of file I/O.
    """

    def __init__(self, config, client_factory=None, telemetry=None,
                 clock=time.monotonic):
        self.config = config
        self.telemetry = telemetry
        self.steering = Steering(config.zones, config.debounce_ms,
                                 config.lost_grace_ms, clock)
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        factory = client_factory or default_client_factory
        self.client = factory(config, self._queue.put, self._put_status)

    def _put_status(self, connected):
        self._queue.put(SensorStatus(connected))

    def start(self):
        """Start the client thread. Returns self so it can be chained."""
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self.client.run_forever,
                                        args=(self._stop,),
                                        name="fp2-client", daemon=True)
        self._thread.start()
        return self

    # --- InputSource ---------------------------------------------------------

    def poll(self):
        """Drain the queue and return this frame's Commands."""
        events, commands = [], []
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, ZoneEvent):
                events.append(item)
                commands += self.steering.update(item)
            elif isinstance(item, SensorStatus) and not item.connected:
                commands += self.steering.mark_sensor_offline()
        commands += self.steering.tick()

        if self.telemetry is not None and (events or commands):
            self.telemetry.record(events, commands)
        return commands

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=JOIN_TIMEOUT_S)
            if self._thread.is_alive():
                log.warning("FP2 client thread did not stop; it is a daemon, "
                            "so it will not hold up exit")
            self._thread = None
        if self.telemetry is not None:
            self.telemetry.close()
