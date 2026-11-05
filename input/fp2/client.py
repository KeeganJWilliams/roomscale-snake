"""HomeKit client for the Aqara FP2.

The only module in the game that imports aiohomekit, so everything else
runs on a machine that never installed it.

The FP2 has no local API of its own. We read it over HAP-IP on the LAN
with this laptop as the HomeKit controller. Each zone drawn in the Aqara
app shows up as its own Occupancy Sensor service; we subscribe to every
OccupancyDetected characteristic the config names and turn each change
into a ZoneEvent.
"""

import asyncio
import logging

from aiohomekit import Controller
from aiohomekit.characteristic_cache import CharacteristicCacheFile
from aiohomekit.uuid import normalize_uuid
from aiohomekit.zeroconf import ZeroconfServiceListener
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

from ..base import now_ns
from .steering import ZoneEvent

log = logging.getLogger(__name__)

OCCUPANCY_SENSOR = normalize_uuid("86")    # HomeKit Occupancy Sensor service
OCCUPANCY_DETECTED = normalize_uuid("71")  # its 0/1 characteristic
NAME = normalize_uuid("23")

HAP_SERVICE = "_hap._tcp.local."
POLL_INTERVAL_S = 0.2
MAX_BACKOFF_S = 30.0


def find_zone_sensors(accessories):
    """Return [(key 'aid.iid', name)] for every OccupancyDetected characteristic.

    One of them covers the whole detection area rather than a drawn zone;
    `identify` is how the team tells them apart.
    """
    zones = []
    for accessory in accessories:
        for service in accessory.get("services", ()):
            if normalize_uuid(service["type"]) != OCCUPANCY_SENSOR:
                continue
            name, key = "?", None
            for char in service.get("characteristics", ()):
                kind = normalize_uuid(char["type"])
                if kind == NAME:
                    name = char.get("value", "?")
                elif kind == OCCUPANCY_DETECTED:
                    key = f'{accessory["aid"]}.{char["iid"]}'
            if key:
                zones.append((key, name))
    return zones


class PairingMissing(Exception):
    """The pairing file has no entry for our alias."""


class Fp2Client:
    """Subscribes to zone occupancy and reports ZoneEvents.

    on_event(ZoneEvent) and on_status(bool) are called from the client's
    own thread, so they must be cheap and thread-safe - the adapter just
    puts them on a queue.
    """

    def __init__(self, config, on_event, on_status=None, subscribe_all=False):
        self.config = config
        self.on_event = on_event
        self.on_status = on_status or (lambda connected: None)
        self.subscribe_all = subscribe_all

    # --- thread entry point --------------------------------------------------

    def run_forever(self, stop):
        """Run until `stop` (a threading.Event) is set. Never raises."""
        try:
            asyncio.run(self.run(stop))
        except Exception:
            log.exception("FP2 client stopped; the game keeps running")
            self.on_status(False)

    async def run(self, stop, retry=True):
        """Connect, and keep reconnecting with backoff until stopped.

        retry=False is for the setup CLI, where a missing pairing should
        say so and quit instead of looping. The game always retries, so a
        sensor that comes back needs no restart.
        """
        backoff = 1.0
        while not stop.is_set():
            try:
                await self._session(stop)
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except PairingMissing:
                # A setup mistake, not a flaky network: retrying cannot fix it.
                self.on_status(False)
                if not retry:
                    raise
                log.warning("FP2 not paired yet; checking again in %.0fs", backoff)
                await self._sleep(backoff, stop)
                backoff = min(backoff * 2, MAX_BACKOFF_S)
            except Exception as exc:
                self.on_status(False)
                if not retry:
                    raise
                log.warning("FP2 unreachable (%s); retrying in %.0fs", exc, backoff)
                await self._sleep(backoff, stop)
                backoff = min(backoff * 2, MAX_BACKOFF_S)

    # --- one connection ------------------------------------------------------

    async def _session(self, stop):
        async with self._pairing() as pairing:
            keys = await self._keys(pairing)
            pairing.dispatcher_connect(self._dispatch)
            await pairing.subscribe(keys)
            # Read the current values so steering starts with the player's
            # real position instead of assuming an empty pad.
            self._dispatch(await pairing.get_characteristics(keys))
            self.on_status(True)
            log.info("FP2 connected: watching %d zone sensors", len(keys))
            await self._watch(pairing, keys, stop)

    async def list_zones(self):
        """One-shot: every occupancy sensor the FP2 exposes."""
        async with self._pairing() as pairing:
            return find_zone_sensors(await pairing.list_accessories_and_characteristics())

    def _pairing(self):
        return _PairingSession(self.config)

    async def _keys(self, pairing):
        if not self.subscribe_all:
            return self.config.subscriptions()
        accessories = await pairing.list_accessories_and_characteristics()
        return [tuple(int(part) for part in key.split("."))
                for key, _ in find_zone_sensors(accessories)]

    async def _watch(self, pairing, keys, stop):
        """Hold the connection open and notice if the sensor drops off.

        aiohomekit only dispatches availability when a device comes back,
        so we watch the flag ourselves to catch it going away.
        """
        available = True
        while not stop.is_set():
            now_available = bool(getattr(pairing, "is_available", True))
            if now_available != available:
                available = now_available
                self.on_status(available)
                log.warning("FP2 %s", "back" if available else "stopped responding")
                if available:
                    await pairing.subscribe(keys)
            await asyncio.sleep(POLL_INTERVAL_S)

    def _dispatch(self, data):
        """aiohomekit callback: {(aid, iid): {"value": 0|1}}."""
        t_recv_ns = now_ns()
        for (aid, iid), payload in data.items():
            value = payload.get("value")
            if value is None:
                continue
            self.on_event(ZoneEvent(f"{aid}.{iid}", bool(value), t_recv_ns))

    @staticmethod
    async def _sleep(seconds, stop):
        """Sleep, but wake up early when asked to stop."""
        deadline = asyncio.get_running_loop().time() + seconds
        while not stop.is_set() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(min(POLL_INTERVAL_S, seconds))


class _PairingSession:
    """`async with` around zeroconf + controller + our paired accessory."""

    def __init__(self, config):
        self.config = config
        self._zc = None
        self._browser = None
        self._controller = None

    async def __aenter__(self):
        # Checked before anything is opened: load_data() ignores a missing
        # file, which would otherwise surface as a baffling missing alias.
        if not self.config.pairing_file.exists():
            raise PairingMissing(
                f"{self.config.pairing_file} not found. Pair the FP2 once with "
                "`aiohomekitctl pair -a fp2 -d <DEVICE_ID> -p <SETUP_CODE>`.")

        self._zc = AsyncZeroconf()
        self._controller = Controller(
            async_zeroconf_instance=self._zc,
            char_cache=CharacteristicCacheFile(self.config.char_cache_file))
        await self._zc.__aenter__()
        self._browser = AsyncServiceBrowser(self._zc.zeroconf, [HAP_SERVICE],
                                            listener=ZeroconfServiceListener())
        await self._controller.__aenter__()
        try:
            self._controller.load_data(str(self.config.pairing_file))
            try:
                return self._controller.aliases[self.config.alias]
            except KeyError:
                raise PairingMissing(
                    f"no pairing called {self.config.alias!r} in "
                    f"{self.config.pairing_file}. Known aliases: "
                    f"{', '.join(self._controller.aliases) or 'none'}.") from None
        except BaseException:
            await self.__aexit__(*(None, None, None))
            raise

    async def __aexit__(self, *exc_info):
        if self._controller is not None:
            await self._controller.__aexit__(*exc_info)
            self._controller = None
        if self._browser is not None:
            await self._browser.async_cancel()
            self._browser = None
        if self._zc is not None:
            await self._zc.__aexit__(*exc_info)
            self._zc = None
