"""Steering state machine: the required cases from FP2_INPUT_ADAPTER.md.

The clock is injected, so nothing here sleeps.
"""

import unittest

from engine import Direction
from input import PlayerFound, PlayerLost, Turn
from input.fp2.steering import Steering, ZoneEvent

ZONES = {"center": "1.10", "up": "1.13", "down": "1.16",
         "left": "1.19", "right": "1.22"}
DEBOUNCE_MS = 150
GRACE_MS = 1000


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, ms):
        self.now += ms / 1000.0


class SteeringHarness(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.steering = Steering(ZONES, DEBOUNCE_MS, GRACE_MS, clock=self.clock)
        self.commands = []
        # Nobody is on the pad at construction; start the player in the
        # centre so each test begins from a settled state.
        self.enter("center")
        self.tick()
        self.commands.clear()

    # --- helpers -------------------------------------------------------------

    def send(self, zone, occupied, key=None):
        event = ZoneEvent(key or ZONES[zone], occupied,
                          t_recv_ns=int(self.clock.now * 1e9))
        self.commands += self.steering.update(event)

    def enter(self, zone):
        self.send(zone, True)

    def leave(self, zone):
        self.send(zone, False)

    def step(self, zone):
        """Move onto one zone, leaving whatever the player stood on before."""
        for standing in sorted(self.steering.occupied):
            if standing != zone:
                self.leave(standing)
        self.enter(zone)

    def tick(self, ms=0):
        if ms:
            self.clock.advance(ms)
        self.commands += self.steering.tick()
        return self.commands

    def turns(self):
        return [c.direction for c in self.commands if isinstance(c, Turn)]

    def kinds(self):
        return [type(c).__name__ for c in self.commands]


class TestTurns(SteeringHarness):
    def test_direction_held_past_debounce_turns_once(self):
        self.step("up")
        self.tick(DEBOUNCE_MS - 10)
        self.assertEqual(self.turns(), [])
        self.tick(20)
        self.assertEqual(self.turns(), [Direction.UP])
        self.tick(500)
        self.assertEqual(self.turns(), [Direction.UP], "turn must not repeat")

    def test_brief_touch_then_centre_does_not_turn(self):
        self.step("up")
        self.tick(DEBOUNCE_MS - 50)
        self.leave("up")
        self.enter("center")
        self.tick(DEBOUNCE_MS * 3)
        self.assertEqual(self.commands, [])

    def test_two_direction_zones_are_ignored_until_one_clears(self):
        self.leave("center")
        self.enter("left")
        self.enter("right")
        self.tick(DEBOUNCE_MS * 2)
        self.assertEqual(self.turns(), [], "straddling a boundary is ignored")
        self.leave("left")
        self.tick(DEBOUNCE_MS + 10)
        self.assertEqual(self.turns(), [Direction.RIGHT])

    def test_same_direction_twice_with_centre_between(self):
        self.step("up")
        self.tick(DEBOUNCE_MS + 10)
        self.step("center")
        self.tick(10)
        self.step("up")
        self.tick(DEBOUNCE_MS + 10)
        self.assertEqual(self.turns(), [Direction.UP, Direction.UP])

    def test_centre_keeps_the_heading(self):
        self.step("up")
        self.tick(DEBOUNCE_MS + 10)
        self.step("center")
        self.tick(DEBOUNCE_MS * 5)
        self.assertEqual(self.turns(), [Direction.UP], "centre must not steer")

    def test_unknown_zone_id_is_ignored(self):
        self.send("up", True, key="9.99")
        self.tick(DEBOUNCE_MS * 2)
        self.assertEqual(self.commands, [])
        self.assertEqual(self.steering.occupied, {"center"})

    def test_a_flicker_mid_step_does_not_restart_the_debounce(self):
        # The FP2 can drop every zone for a frame while the player moves.
        self.step("up")
        self.tick(100)
        self.leave("up")
        self.tick(20)
        self.enter("up")
        self.tick(40)
        self.assertEqual(self.turns(), [Direction.UP])


class TestLostAndFound(SteeringHarness):
    def test_short_gap_does_not_pause(self):
        self.leave("center")
        self.tick(GRACE_MS - 100)
        self.enter("center")
        self.tick(GRACE_MS * 2)
        self.assertEqual(self.commands, [])

    def test_empty_pad_past_grace_pauses_once_then_resumes(self):
        self.leave("center")
        self.tick(GRACE_MS - 10)
        self.assertEqual(self.commands, [])
        self.tick(20)
        self.assertEqual(self.kinds(), ["PlayerLost"])
        self.tick(GRACE_MS * 2)
        self.assertEqual(self.kinds(), ["PlayerLost"], "pause must fire once")

        self.enter("center")
        self.assertEqual(self.kinds(), ["PlayerLost", "PlayerFound"])
        self.tick(GRACE_MS * 2)
        self.assertEqual(self.kinds(), ["PlayerLost", "PlayerFound"])

    def test_no_events_at_all_still_pauses(self):
        steering = Steering(ZONES, DEBOUNCE_MS, GRACE_MS, clock=self.clock)
        self.clock.advance(GRACE_MS + 10)
        self.assertEqual([type(c).__name__ for c in steering.tick()], ["PlayerLost"])

    def test_offline_sensor_pauses_once_and_drops_stale_zones(self):
        self.assertEqual(self.steering.occupied, {"center"})
        commands = self.steering.mark_sensor_offline()
        self.assertEqual([type(c).__name__ for c in commands], ["PlayerLost"])
        self.assertEqual(self.steering.occupied, set())
        self.assertEqual(self.steering.mark_sensor_offline(), [])
        self.clock.advance(GRACE_MS * 2)
        self.assertEqual(self.steering.tick(), [])

    def test_returning_after_a_pause_can_steer_again(self):
        self.leave("center")
        self.tick(GRACE_MS + 10)
        self.enter("up")
        self.tick(DEBOUNCE_MS + 10)
        self.assertEqual(self.kinds(), ["PlayerLost", "PlayerFound", "Turn"])
        self.assertEqual(self.turns(), [Direction.UP])


class TestStamps(SteeringHarness):
    def test_turn_carries_the_event_that_proposed_it(self):
        self.leave("center")
        self.clock.advance(20)
        self.enter("up")
        t_up = int(self.clock.now * 1e9)
        # A later unrelated event must not steal the attribution.
        self.clock.advance(10)
        self.enter("center")
        self.tick(DEBOUNCE_MS + 10)
        turn = next(c for c in self.commands if isinstance(c, Turn))
        self.assertEqual(turn.t_recv_ns, t_up)
        self.assertEqual(turn.zone_key, ZONES["up"])

    def test_lost_is_stamped_with_the_event_that_emptied_the_pad(self):
        self.leave("center")
        t_off = int(self.clock.now * 1e9)
        self.tick(GRACE_MS + 10)
        lost = next(c for c in self.commands if isinstance(c, PlayerLost))
        self.assertEqual(lost.t_recv_ns, t_off)
        self.assertEqual(lost.zone_key, ZONES["center"])

    def test_found_is_stamped_with_its_own_event(self):
        self.leave("center")
        self.tick(GRACE_MS + 10)
        self.clock.advance(50)
        self.enter("left")
        found = next(c for c in self.commands if isinstance(c, PlayerFound))
        self.assertEqual(found.zone_key, ZONES["left"])
        self.assertEqual(found.t_recv_ns, int(self.clock.now * 1e9))


if __name__ == "__main__":
    unittest.main()
