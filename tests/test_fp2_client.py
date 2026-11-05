"""Client tests. Skipped where aiohomekit isn't installed, since the rest
of the game must run without it.
"""

import asyncio
import importlib.util
import pathlib
import tempfile
import threading
import unittest

from input.fp2.config import parse

HAS_AIOHOMEKIT = importlib.util.find_spec("aiohomekit") is not None

RAW_CONFIG = {
    "zones": {"center": "1.10", "up": "1.13", "down": "1.16",
              "left": "1.19", "right": "1.22"},
}


def occupancy_service(iid, name, value, service_type="86"):
    return {
        "type": service_type,
        "characteristics": [
            {"type": "23", "iid": iid - 1, "value": name},
            {"type": "71", "iid": iid, "value": value},
        ],
    }


@unittest.skipUnless(HAS_AIOHOMEKIT, "aiohomekit not installed")
class TestFindZoneSensors(unittest.TestCase):
    def setUp(self):
        from input.fp2.client import find_zone_sensors

        self.find = find_zone_sensors

    def test_finds_every_occupancy_characteristic(self):
        accessories = [{
            "aid": 1,
            "services": [
                {"type": "3E", "characteristics": [{"type": "23", "value": "FP2"}]},
                occupancy_service(13, "Zone 1", 1),
                occupancy_service(16, "Zone 2", 0),
            ],
        }]
        self.assertEqual(self.find(accessories),
                         [("1.13", "Zone 1"), ("1.16", "Zone 2")])

    def test_ignores_services_that_are_not_occupancy_sensors(self):
        accessories = [{"aid": 1, "services": [
            occupancy_service(13, "Light", 1, service_type="43")]}]
        self.assertEqual(self.find(accessories), [])

    def test_accepts_full_length_uuids_and_missing_names(self):
        accessories = [{"aid": 2, "services": [{
            "type": "00000086-0000-1000-8000-0026BB765291",
            "characteristics": [
                {"type": "00000071-0000-1000-8000-0026BB765291", "iid": 9, "value": 0}],
        }]}]
        self.assertEqual(self.find(accessories), [("2.9", "?")])

    def test_tolerates_an_accessory_with_no_services(self):
        self.assertEqual(self.find([{"aid": 1}]), [])


@unittest.skipUnless(HAS_AIOHOMEKIT, "aiohomekit not installed")
class TestPairingErrors(unittest.TestCase):
    def test_missing_pairing_file_is_reported_not_retried(self):
        from input.fp2.client import Fp2Client, PairingMissing

        with tempfile.TemporaryDirectory() as tmp:
            config = parse(RAW_CONFIG)
            config.pairing_file = pathlib.Path(tmp) / "pairing.json"
            statuses = []
            client = Fp2Client(config, lambda event: None, statuses.append)
            with self.assertRaises(PairingMissing) as caught:
                asyncio.run(client.run(threading.Event(), retry=False))
        self.assertIn("aiohomekitctl pair", str(caught.exception))
        self.assertEqual(statuses, [False], "a dropout pauses the game")

    def test_run_forever_never_raises_into_the_game(self):
        from input.fp2.client import Fp2Client

        with tempfile.TemporaryDirectory() as tmp:
            config = parse(RAW_CONFIG)
            config.pairing_file = pathlib.Path(tmp) / "pairing.json"
            stop = threading.Event()
            statuses = []
            client = Fp2Client(config, lambda event: None, statuses.append)

            thread = threading.Thread(target=client.run_forever, args=(stop,),
                                      daemon=True)
            with self.assertLogs("input.fp2.client", level="WARNING"):
                thread.start()
                for _ in range(200):
                    if statuses:
                        break
                    threading.Event().wait(0.01)
            stop.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "the client thread honours stop")
        self.assertEqual(statuses[0], False)


@unittest.skipUnless(HAS_AIOHOMEKIT, "aiohomekit not installed")
class TestDispatch(unittest.TestCase):
    def test_homekit_payload_becomes_zone_events(self):
        from input.fp2.client import Fp2Client

        events = []
        client = Fp2Client(parse(RAW_CONFIG), events.append)
        client._dispatch({(1, 10): {"value": 0}, (1, 13): {"value": 1},
                          (1, 16): {}})
        self.assertEqual([(e.key, e.occupied) for e in events],
                         [("1.10", False), ("1.13", True)])
        self.assertTrue(all(e.t_recv_ns > 0 for e in events))
        self.assertEqual(len({e.t_recv_ns for e in events}), 1,
                         "one callback is stamped once")


if __name__ == "__main__":
    unittest.main()
