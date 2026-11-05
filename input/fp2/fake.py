"""Replay a scripted zone-event file instead of talking to a real FP2.

Lets the whole game be run end to end without hardware:

    python main.py --input fp2 --fake config/fp2_fake_script.json

Script format (at_ms is milliseconds from the start of the replay):

    {"loop": true,
     "events": [{"at_ms": 0, "zone": "center", "occupied": true},
                {"at_ms": 900, "zone": "up", "occupied": true}]}

Each event names either a "zone" ("center"/"up"/"down"/"left"/"right",
looked up in the FP2 config) or a raw "key" like "1.13".
"""

import json
import logging
import pathlib
import time

from ..base import now_ns
from .config import ConfigError
from .steering import ZONE_NAMES, ZoneEvent

log = logging.getLogger(__name__)

TICK_S = 0.01


def load_script(path, zones):
    """Parse a script file into [(delay_s, ZoneEvent)] plus a loop flag."""
    path = pathlib.Path(path)
    if not path.exists():
        raise ConfigError(f"fake script {path} not found")
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}") from exc

    if isinstance(raw, list):
        raw = {"events": raw}
    entries = raw.get("events")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f'{path}: expected a non-empty "events" list')

    script = []
    for index, entry in enumerate(entries):
        if "key" in entry:
            key = str(entry["key"])
        else:
            name = entry.get("zone")
            if name not in ZONE_NAMES:
                raise ConfigError(
                    f"{path}: event {index} needs a \"key\", or a \"zone\" from "
                    f"{', '.join(ZONE_NAMES)}; got {name!r}")
            key = zones[name]
        at_ms = entry.get("at_ms", 0)
        if not isinstance(at_ms, (int, float)) or isinstance(at_ms, bool):
            raise ConfigError(f"{path}: event {index} has a non-numeric at_ms")
        script.append((at_ms / 1000.0, key, bool(entry.get("occupied", True))))

    script.sort(key=lambda item: item[0])
    return script, bool(raw.get("loop", False))


class FakeClient:
    """Stands in for Fp2Client, with the same run_forever(stop) contract."""

    def __init__(self, config, on_event, on_status=None, script_path=None):
        self.on_event = on_event
        self.on_status = on_status or (lambda connected: None)
        self.script, self.loop = load_script(script_path, config.zones)
        self.duration_s = self.script[-1][0]

    def run_forever(self, stop):
        log.info("FP2 fake client: replaying %d events%s",
                 len(self.script), " on a loop" if self.loop else "")
        self.on_status(True)
        while not stop.is_set():
            start = time.monotonic()
            for at_s, key, occupied in self.script:
                while not stop.is_set() and time.monotonic() - start < at_s:
                    time.sleep(TICK_S)
                if stop.is_set():
                    return
                self.on_event(ZoneEvent(key, occupied, now_ns()))
            if not self.loop:
                break
            # Pause a beat before looping so the pad doesn't jump mid-step.
            while not stop.is_set() and time.monotonic() - start < self.duration_s + 0.5:
                time.sleep(TICK_S)
        # Script finished: hold the last state rather than faking a dropout.
        while not stop.is_set():
            time.sleep(TICK_S)
