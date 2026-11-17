"""Read Aqara FP2 zone occupancy directly on the laptop over HomeKit (no Home Assistant).

Setup (once):
    pip install aiohomekit
    aiohomekitctl discover -u                      # find the FP2's Device ID
    aiohomekitctl pair -a fp2 -d <DEVICE_ID> -p <SETUP_CODE>

Then:
    python fp2_zones.py list        # show every zone sensor as aid.iid
    python fp2_zones.py identify    # walk into each zone, see which aid.iid turns on
    python fp2_zones.py run         # print steering directions using zones.json

zones.json (fill in from `identify`):
    {"center": "1.10", "up": "1.13", "down": "1.16", "left": "1.19", "right": "1.22"}
"""

import asyncio
import json
import pathlib
import sys
import time

from aiohomekit import Controller
from aiohomekit.characteristic_cache import CharacteristicCacheFile
from aiohomekit.uuid import normalize_uuid
from aiohomekit.zeroconf import ZeroconfServiceListener
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

PAIRING_FILE = pathlib.Path.home() / ".local/share/aiohomekit/pairing.json"
ALIAS = "fp2"
ZONES_FILE = pathlib.Path(__file__).with_name("zones.json")

OCCUPANCY_SENSOR = normalize_uuid("86")    # HomeKit Occupancy Sensor service
OCCUPANCY_DETECTED = normalize_uuid("71")  # its 0/1 characteristic
NAME = normalize_uuid("23")

DEBOUNCE_S = 0.15  # a new zone must hold this long before it counts as a turn
LOST_GRACE_S = 1.0  # pad empty this long -> pause (zones briefly all read off mid-step)
DIRECTIONS = ("up", "down", "left", "right")


def find_zone_sensors(accessories):
    """Return [(key 'aid.iid', name)] for every OccupancyDetected characteristic."""
    zones = []
    for acc in accessories:
        for svc in acc["services"]:
            if normalize_uuid(svc["type"]) != OCCUPANCY_SENSOR:
                continue
            name, key = "?", None
            for ch in svc["characteristics"]:
                t = normalize_uuid(ch["type"])
                if t == NAME:
                    name = ch.get("value", "?")
                elif t == OCCUPANCY_DETECTED:
                    key = f'{acc["aid"]}.{ch["iid"]}'
            if key:
                zones.append((key, name))
    return zones


class Steering:
    """Turns raw zone on/off events into debounced direction commands."""

    def __init__(self, zone_map, on_direction, on_lost):
        self.by_key = {v: k for k, v in zone_map.items()}  # 'aid.iid' -> 'up'
        self.occupied = set()
        self.on_direction, self.on_lost = on_direction, on_lost
        self.candidate, self.since, self.current = None, 0.0, None
        self.empty_since, self.paused = None, False

    def update(self, key, value):
        zone = self.by_key.get(key)
        if zone is None:
            return
        (self.occupied.add if value else self.occupied.discard)(zone)
        self.empty_since = time.monotonic() if not self.occupied else None
        active = [d for d in DIRECTIONS if d in self.occupied]
        if len(active) == 1:
            self._propose(active[0])
        elif "center" in self.occupied and not active:
            self._propose(None)            # back in center: keep heading
        # two direction zones at once (straddling a boundary): ignore

    def _propose(self, zone):
        if zone != self.candidate:
            self.candidate, self.since = zone, time.monotonic()

    def tick(self):
        """Call often (e.g. every game frame); emits a turn once the zone has held."""
        now = time.monotonic()
        if self.empty_since is not None:
            if not self.paused and now - self.empty_since >= LOST_GRACE_S:
                self.paused, self.candidate = True, None
                self.on_lost()             # nobody on the pad: pause the game
            return
        self.paused = False
        c = self.candidate
        if c and c != self.current and now - self.since >= DEBOUNCE_S:
            self.current = c
            self.on_direction(c)
        elif c is None:
            self.current = None            # allow turning the same way again


async def main(mode):
    zc = AsyncZeroconf()
    controller = Controller(async_zeroconf_instance=zc,
                            char_cache=CharacteristicCacheFile(PAIRING_FILE.parent / "charmap.json"))
    async with zc:
        browser = AsyncServiceBrowser(zc.zeroconf, ["_hap._tcp.local.", "_hap._udp.local."], listener=ZeroconfServiceListener())
        async with controller:
            controller.load_data(PAIRING_FILE)
            pairing = controller.aliases[ALIAS]
            zones = find_zone_sensors(await pairing.list_accessories_and_characteristics())

            if mode == "list":
                for key, name in zones:
                    print(f"{key:>8}  {name}")
                return

            if mode == "run":
                zone_map = json.loads(ZONES_FILE.read_text())
                t0 = time.monotonic()
                stamp = lambda: f"{(time.monotonic() - t0) * 1000:9.0f} ms"
                steer = Steering(zone_map,
                                 on_direction=lambda d: print(stamp(), "TURN", d),
                                 on_lost=lambda: print(stamp(), "player lost -> pause"))

            def handler(data):
                for (aid, iid), v in data.items():
                    key, value = f"{aid}.{iid}", v.get("value")
                    if mode == "identify":
                        print(f"{time.strftime('%H:%M:%S')}  {key}  {'ON ' if value else 'off'}")
                    else:
                        steer.update(key, value)

            pairing.dispatcher_connect(handler)
            await pairing.subscribe([tuple(map(int, k.split("."))) for k, _ in zones])
            print(f"Watching {len(zones)} zone sensors. Ctrl+C to stop.")
            while True:
                if mode == "run":
                    steer.tick()
                await asyncio.sleep(0.01)
        await browser.async_cancel()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "identify"
    if mode not in ("list", "identify", "run"):
        sys.exit(__doc__)
    try:
        asyncio.run(main(mode))
    except KeyboardInterrupt:
        pass
