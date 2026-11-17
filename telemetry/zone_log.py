"""CSV log of FP2 zone events and the commands they produced (objective O3).

One row per zone event:

    t_recv_ns, zone_key, zone_name, occupied, command_emitted, t_command_ns

A row's command columns are filled in when that event caused a command, so
`t_command_ns - t_recv_ns` is the sensor-to-command latency. Because a turn
only fires once its zone has held out the debounce, an event's row is held
back until it either produces a command or can no longer produce one.
"""

import csv
import logging
import pathlib
import time

from input.base import PlayerFound, PlayerLost, Turn, now_ns

log = logging.getLogger(__name__)

DEFAULT_DIR = pathlib.Path(__file__).parent / "logs"
HEADER = ("t_recv_ns", "zone_key", "zone_name", "occupied",
          "command_emitted", "t_command_ns")


def command_name(command):
    if isinstance(command, Turn):
        return f"TURN_{command.direction.name}"
    if isinstance(command, PlayerLost):
        return "PLAYER_LOST"
    if isinstance(command, PlayerFound):
        return "PLAYER_FOUND"
    return type(command).__name__.upper()


class ZoneEventLog:
    """Append-only CSV writer. Never raises into the game loop."""

    def __init__(self, zones, path=None, directory=None, hold_ms=2000):
        self.names = {key: name for name, key in zones.items()}
        self.hold_ns = int(hold_ms * 1e6)
        self._pending = {}
        self._file = None
        self._writer = None

        if path is None:
            directory = pathlib.Path(directory or DEFAULT_DIR)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            path = directory / f"fp2_zones_{stamp}.csv"
        self.path = pathlib.Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            new = not self.path.exists() or self.path.stat().st_size == 0
            self._file = self.path.open("a", newline="")
            self._writer = csv.writer(self._file)
            if new:
                self._writer.writerow(HEADER)
                self._file.flush()
            log.info("FP2 telemetry -> %s", self.path)
        except OSError:
            log.exception("could not open %s; telemetry disabled", self.path)
            self._file = None

    # --- recording -----------------------------------------------------------

    def record(self, events, commands, t_command_ns=None):
        """Log one poll cycle's worth of events and the commands it emitted."""
        if self._writer is None:
            return
        t_command_ns = t_command_ns or now_ns()
        try:
            for event in events:
                key = (event.t_recv_ns, event.key)
                if key in self._pending:
                    self._write(self._pending.pop(key), None, None)
                self._pending[key] = event
            for command in commands:
                event = self._pending.pop((command.t_recv_ns, command.zone_key), None)
                self._write(event, command, t_command_ns)
            self._expire(t_command_ns)
            self._file.flush()
        except (OSError, ValueError):
            log.exception("FP2 telemetry write failed; disabling it")
            self._writer = None

    def _expire(self, now):
        """Flush events too old to still be waiting out a debounce."""
        stale = [key for key, event in self._pending.items()
                 if now - event.t_recv_ns > self.hold_ns]
        for key in stale:
            self._write(self._pending.pop(key), None, None)

    def _write(self, event, command, t_command_ns):
        if event is not None:
            row = [event.t_recv_ns, event.key, self.names.get(event.key, ""),
                   int(event.occupied)]
        else:
            # A command with no surviving event row (e.g. a dropped sensor).
            row = [command.t_recv_ns or "", command.zone_key,
                   self.names.get(command.zone_key, ""), ""]
        row += [command_name(command) if command else "", t_command_ns or ""]
        self._writer.writerow(row)

    def close(self):
        if self._writer is not None:
            try:
                for key in list(self._pending):
                    self._write(self._pending.pop(key), None, None)
                self._file.flush()
            except (OSError, ValueError):
                log.exception("FP2 telemetry flush failed")
        if self._file is not None:
            self._file.close()
            self._file = None
        self._writer = None
