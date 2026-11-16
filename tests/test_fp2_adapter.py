"""Adapter tests: a fake client feeds scripted ZoneEvents into the queue."""

import json
import pathlib
import tempfile
import threading
import time
import unittest

from engine import Direction
from input import Turn
from input.fp2.adapter import Fp2Input
from input.fp2.config import parse
from input.fp2.steering import ZoneEvent

RAW_CONFIG = {
    "alias": "fp2",
    "zones": {"center": "1.10", "up": "1.13", "down": "1.16",
              "left": "1.19", "right": "1.22"},
    "debounce_ms": 150,
    "lost_grace_ms": 1000,
}


class FakeClock:
    def __init__(self, now=500.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, ms):
        self.now += ms / 1000.0


class ScriptedClient:
    """Captures the adapter's callbacks so a test can play the sensor."""

    def __init__(self, config, on_event, on_status):
        self.config = config
        self.on_event = on_event
        self.on_status = on_status
        self.started = threading.Event()

    def run_forever(self, stop):
        self.started.set()
        while not stop.is_set():
            time.sleep(0.005)

    # --- what a test calls ---------------------------------------------------

    def send(self, key, occupied, t_recv_ns=0):
        self.on_event(ZoneEvent(key, occupied, t_recv_ns))

    def status(self, connected):
        self.on_status(connected)


class AdapterHarness(unittest.TestCase):
    def setUp(self):
        self.config = parse(RAW_CONFIG)
        self.clock = FakeClock()
        self.clients = []

        def factory(config, on_event, on_status):
            client = ScriptedClient(config, on_event, on_status)
            self.clients.append(client)
            return client

        self.source = Fp2Input(self.config, client_factory=factory,
                               clock=self.clock)
        self.client = self.clients[0]
        self.addCleanup(self.source.close)

    def poll(self, ms=0):
        if ms:
            self.clock.advance(ms)
        return self.source.poll()


class TestAdapter(AdapterHarness):
    def test_scripted_events_become_a_turn(self):
        self.client.send("1.10", True)              # standing in the centre
        self.assertEqual(self.poll(), [])
        self.client.send("1.10", False)
        self.client.send("1.13", True)              # stepped up
        self.assertEqual(self.poll(), [])           # debounce not served yet
        commands = self.poll(160)
        self.assertEqual([type(c).__name__ for c in commands], ["Turn"])
        self.assertEqual(commands[0].direction, Direction.UP)

    def test_events_queued_between_polls_are_all_applied(self):
        for key, occupied in (("1.10", True), ("1.10", False), ("1.19", True)):
            self.client.send(key, occupied)
        # All three land in one frame; the debounce runs from that frame.
        self.assertEqual(self.poll(), [])
        commands = self.poll(200)
        self.assertEqual([c.direction for c in commands], [Direction.LEFT])

    def test_unknown_zone_never_steers(self):
        self.client.send("1.10", True)
        self.poll()
        self.client.send("9.99", True)
        self.assertEqual(self.poll(500), [])

    def test_empty_pad_pauses_then_resumes(self):
        self.client.send("1.10", True)
        self.poll()
        self.client.send("1.10", False)
        self.assertEqual(self.poll(), [])
        self.assertEqual([type(c).__name__ for c in self.poll(1100)], ["PlayerLost"])
        self.client.send("1.10", True)
        self.assertEqual([type(c).__name__ for c in self.poll()], ["PlayerFound"])

    def test_disconnect_pauses_the_game_once(self):
        self.client.send("1.10", True)
        self.poll()
        self.client.status(False)
        self.assertEqual([type(c).__name__ for c in self.poll()], ["PlayerLost"])
        self.client.status(False)
        self.assertEqual(self.poll(2000), [], "one pause per dropout")
        self.client.status(True)
        self.client.send("1.13", True)
        commands = self.poll()
        self.assertEqual([type(c).__name__ for c in commands], ["PlayerFound"])

    def test_poll_never_blocks_when_nothing_happens(self):
        self.assertEqual(self.source.poll(), [])
        self.assertEqual(self.source.poll(), [])

    def test_start_runs_the_client_on_a_daemon_thread(self):
        self.source.start()
        self.assertTrue(self.client.started.wait(timeout=2.0))
        self.assertTrue(self.source._thread.daemon)
        self.source.start()  # idempotent
        self.assertEqual(len(self.clients), 1)
        self.source.close()
        self.assertIsNone(self.source._thread)


class TestFakeClientEndToEnd(unittest.TestCase):
    """The --fake path the game uses when no sensor is around."""

    def test_replayed_script_steers(self):
        from input.fp2.fake import FakeClient

        script = {"loop": False, "events": [
            {"at_ms": 0, "zone": "center", "occupied": True},
            {"at_ms": 20, "zone": "center", "occupied": False},
            {"at_ms": 25, "zone": "right", "occupied": True},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "script.json"
            path.write_text(json.dumps(script))
            config = parse(dict(RAW_CONFIG, debounce_ms=30, lost_grace_ms=5000))
            source = Fp2Input(
                config,
                client_factory=lambda c, ev, st: FakeClient(c, ev, st, script_path=path))
            try:
                source.start()
                deadline = time.monotonic() + 5.0
                turns = []
                while time.monotonic() < deadline and not turns:
                    turns = [c for c in source.poll() if isinstance(c, Turn)]
                    time.sleep(0.01)
            finally:
                source.close()
        self.assertEqual([t.direction for t in turns], [Direction.RIGHT])
        self.assertGreater(turns[0].t_recv_ns, 0, "turns carry a sensor timestamp")


if __name__ == "__main__":
    unittest.main()
