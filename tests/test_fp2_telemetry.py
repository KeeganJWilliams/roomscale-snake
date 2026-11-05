"""The O3 latency log: one row per zone event, joined to its command."""

import csv
import pathlib
import tempfile
import unittest

from engine import Direction
from input import PlayerFound, PlayerLost, Turn
from input.fp2.steering import ZoneEvent
from telemetry import ZoneEventLog
from telemetry.zone_log import HEADER

ZONES = {"center": "1.10", "up": "1.13", "down": "1.16",
         "left": "1.19", "right": "1.22"}

MS = 1_000_000


class TestZoneEventLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "logs" / "zones.csv"
        self.log = ZoneEventLog(ZONES, path=self.path)

    def rows(self):
        self.log.close()
        with self.path.open(newline="") as handle:
            return list(csv.DictReader(handle))

    def test_header_and_directory_are_created(self):
        self.assertTrue(self.path.parent.is_dir())
        self.log.close()
        with self.path.open(newline="") as handle:
            self.assertEqual(next(csv.reader(handle)), list(HEADER))

    def test_event_row_is_joined_to_the_turn_it_caused(self):
        event = ZoneEvent("1.13", True, t_recv_ns=1000 * MS)
        self.log.record([event], [], t_command_ns=1000 * MS)
        turn = Turn(Direction.UP, t_recv_ns=1000 * MS, zone_key="1.13")
        self.log.record([], [turn], t_command_ns=1160 * MS)

        rows = self.rows()
        self.assertEqual(len(rows), 1, "the event is logged once, with its command")
        row = rows[0]
        self.assertEqual(row["zone_key"], "1.13")
        self.assertEqual(row["zone_name"], "up")
        self.assertEqual(row["occupied"], "1")
        self.assertEqual(row["command_emitted"], "TURN_UP")
        latency_ms = (int(row["t_command_ns"]) - int(row["t_recv_ns"])) / MS
        self.assertAlmostEqual(latency_ms, 160)

    def test_event_that_causes_nothing_is_still_logged(self):
        event = ZoneEvent("1.10", False, t_recv_ns=1000 * MS)
        self.log.record([event], [], t_command_ns=1000 * MS)
        self.assertEqual(self.rows()[0]["command_emitted"], "")

    def test_pause_and_resume_are_logged(self):
        off = ZoneEvent("1.10", False, t_recv_ns=1000 * MS)
        self.log.record([off], [], t_command_ns=1000 * MS)
        self.log.record([], [PlayerLost(1000 * MS, "1.10")], t_command_ns=2000 * MS)
        back = ZoneEvent("1.10", True, t_recv_ns=3000 * MS)
        self.log.record([back], [PlayerFound(3000 * MS, "1.10")],
                        t_command_ns=3001 * MS)
        self.assertEqual([r["command_emitted"] for r in self.rows()],
                         ["PLAYER_LOST", "PLAYER_FOUND"])

    def test_stale_events_are_flushed_rather_than_held_forever(self):
        self.log.record([ZoneEvent("1.13", True, t_recv_ns=1000 * MS)], [],
                        t_command_ns=1000 * MS)
        self.assertEqual(len(self.log._pending), 1)
        self.log.record([], [], t_command_ns=9000 * MS)
        self.assertEqual(self.log._pending, {})
        self.assertEqual(len(self.rows()), 1)

    def test_events_sharing_a_timestamp_are_kept_apart(self):
        # The client stamps one HomeKit callback once, so a step off centre
        # and onto "up" can arrive with the same t_recv_ns.
        batch = [ZoneEvent("1.10", False, t_recv_ns=1000 * MS),
                 ZoneEvent("1.13", True, t_recv_ns=1000 * MS)]
        self.log.record(batch, [], t_command_ns=1000 * MS)
        self.log.record([], [Turn(Direction.UP, 1000 * MS, "1.13")],
                        t_command_ns=1150 * MS)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        by_key = {row["zone_key"]: row for row in rows}
        self.assertEqual(by_key["1.13"]["command_emitted"], "TURN_UP")
        self.assertEqual(by_key["1.10"]["command_emitted"], "")

    def test_command_without_a_matching_event_still_logs(self):
        self.log.record([], [PlayerLost(0, "")], t_command_ns=5000 * MS)
        row = self.rows()[0]
        self.assertEqual(row["command_emitted"], "PLAYER_LOST")
        self.assertEqual(row["t_recv_ns"], "")

    def test_a_write_failure_does_not_reach_the_game(self):
        self.log._file.close()          # simulate the disk going away
        self.log.record([ZoneEvent("1.13", True, 1000 * MS)], [])
        self.assertIsNone(self.log._writer)
        self.log.record([ZoneEvent("1.13", False, 2000 * MS)], [])  # no raise

    def test_unopenable_path_disables_logging_quietly(self):
        path = pathlib.Path(self.tmp.name) / "zones.csv" / "nope.csv"
        (pathlib.Path(self.tmp.name) / "zones.csv").write_text("not a directory")
        with self.assertLogs("telemetry.zone_log", level="ERROR"):
            log = ZoneEventLog(ZONES, path=path)
        log.record([ZoneEvent("1.13", True, 0)], [])
        log.close()


if __name__ == "__main__":
    unittest.main()
