"""The tutorial: every step waits for the player, no game over, and the run
is logged for the user study. No sensor needed: the pad is a fake."""

import csv
import os
import tempfile
import unittest

from engine import Direction
from input import PlayerFound, PlayerLost, Turn
from telemetry.tutorial_log import write_tutorial_log
from tutorial import Tutorial
from tutorial.tutorial import DEFAULT_SPEED, MOVE_CELLS

TICK = 1.0 / DEFAULT_SPEED + 1e-4    # time for the snake to move one cell
TURN_DEMO = MOVE_CELLS * TICK + 0.5  # long enough to finish showing a turn


class FakePad:
    def __init__(self):
        self.zones = set()

    def __call__(self):
        return frozenset(self.zones)


def run(tutorial, seconds, dt=0.05):
    for _ in range(int(seconds / dt)):
        tutorial.update(dt)


def ticks(tutorial, n):
    for _ in range(n):
        tutorial.update(TICK)


def run_until(tutorial, kind, seconds=10, dt=0.05):
    """Run until the tutorial reaches a step of this kind (and no further)."""
    for _ in range(int(seconds / dt)):
        if tutorial.step.kind == kind:
            return
        tutorial.update(dt)
    raise AssertionError(f"never reached {kind}; stuck on {tutorial.step.name}")


def do_turns(tutorial, pad=None):
    """Answer the four turn prompts (and the center prompts between them)."""
    for direction in (Direction.UP, Direction.LEFT, Direction.DOWN, Direction.RIGHT):
        assert tutorial.step.kind == "turn", tutorial.step
        if pad is not None:
            pad.zones = {direction.name.lower()}   # standing on that square
        tutorial.handle(Turn(direction))
        run(tutorial, TURN_DEMO)
        if pad is not None and tutorial.step.kind == "center":
            pad.zones = {"center"}
            run(tutorial, 0.1)


def wait_ready(tutorial):
    """Let the practice level's "Get ready..." pause run out."""
    while tutorial._hold:
        tutorial.update(0.05)


def drive_portal(tutorial):
    """Steer the portal practice: right 3, then up 3 into the ring at (13, 4)."""
    wait_ready(tutorial)
    ticks(tutorial, 3)                       # (13, 7)
    tutorial.handle(Turn(Direction.UP))
    ticks(tutorial, 3)                       # into the portal, out at (4, 10)


def drive_gate(tutorial):
    """Steer the gate practice: up, right onto the key, down, right through."""
    wait_ready(tutorial)
    ticks(tutorial, 3)                       # up to (10, 4)
    tutorial.handle(Turn(Direction.RIGHT))
    ticks(tutorial, 3)                       # key at (11, 4), then on to (13, 4)
    tutorial.handle(Turn(Direction.DOWN))
    ticks(tutorial, 3)                       # (13, 7)
    tutorial.handle(Turn(Direction.RIGHT))
    ticks(tutorial, 2)                       # through the gate at x=14


class TestKeyboardTutorial(unittest.TestCase):
    def test_full_run_without_a_pad(self):
        t = Tutorial(20, 15, has_pad=False)
        self.assertNotIn("stand", [s.name for s in t.steps])
        self.assertTrue(t.step.title.startswith("Press the UP arrow"))

        do_turns(t)
        self.assertEqual(t.step.kind, "cruise")
        run_until(t, "portal")
        self.assertEqual(t.hint, "Get ready...")
        drive_portal(t)
        run_until(t, "gate")
        drive_gate(t)
        run(t, 2.5)                          # "Nice!" pause
        self.assertEqual(t.step.kind, "done")
        self.assertIsNotNone(t.completion_seconds)
        run(t, 5)
        self.assertTrue(t.finished)
        self.assertFalse(t.assisted)

    def test_keep_going_step_stays_up_long_enough_to_read(self):
        t = Tutorial(20, 15)
        do_turns(t)
        self.assertEqual(t.step.kind, "cruise")
        run_until(t, "portal")
        cruise = next(r for r in t.records if r.name == "cruise")
        self.assertGreaterEqual(cruise.seconds, 4.5)

    def test_wrong_turn_is_counted_and_hinted(self):
        t = Tutorial(20, 15)
        t.handle(Turn(Direction.LEFT))
        self.assertEqual(t.step.direction, Direction.UP)   # didn't move on
        self.assertIn("That was LEFT", t.hint)
        self.assertEqual(t.records[-1].wrong_turns, 1)

    def test_snake_waits_for_the_player(self):
        t = Tutorial(20, 15)
        head = t.game.snake.head
        run(t, 5)
        self.assertEqual(t.game.snake.head, head)
        self.assertEqual(t.step.kind, "turn")

    def test_crash_restarts_practice_instead_of_game_over(self):
        t = Tutorial(20, 15)
        while t.step.kind != "gate":
            t.skip()
            while t.step.kind == "turn" and t._moves_left:
                t.update(0.05)
        wait_ready(t)
        t.handle(Turn(Direction.RIGHT))     # straight at the locked gate
        ticks(t, 5)
        self.assertEqual(t.step.kind, "gate")
        self.assertEqual(t.records[-1].retries, 1)
        self.assertIn("KEY first", t.hint)
        self.assertEqual(t.game.snake.head, (10, 7))   # fresh attempt

    def test_skip_marks_the_run_assisted(self):
        t = Tutorial(20, 15)
        t.skip()
        run(t, TURN_DEMO)
        self.assertEqual(t.step.direction, Direction.LEFT)
        self.assertTrue(t.records[0].skipped)
        self.assertTrue(t.assisted)

    def test_abort(self):
        t = Tutorial(20, 15)
        t.abort()
        self.assertTrue(t.finished and t.aborted)

    def test_small_grid_skips_practice(self):
        t = Tutorial(12, 10)
        self.assertNotIn("gate", [s.name for s in t.steps])


class TestPadTutorial(unittest.TestCase):
    def setUp(self):
        self.pad = FakePad()
        self.t = Tutorial(20, 15, has_pad=True, pad_zones=self.pad)

    def test_waits_for_the_center_square(self):
        self.assertEqual(self.t.step.kind, "stand")
        run(self.t, 2)
        self.assertEqual(self.t.step.kind, "stand")
        self.pad.zones = {"center"}
        run(self.t, 0.1)
        self.assertEqual(self.t.step.kind, "turn")
        self.assertEqual(self.t.step.target_zone, "up")

    def test_must_return_to_center_between_turns(self):
        self.pad.zones = {"center"}
        run(self.t, 0.1)
        self.pad.zones = {"up"}
        self.t.handle(Turn(Direction.UP))
        run(self.t, TURN_DEMO)
        self.assertEqual(self.t.step.kind, "center")
        run(self.t, 2)
        self.assertEqual(self.t.step.kind, "center")   # still standing on UP

    def test_full_run_with_the_pad(self):
        self.pad.zones = {"center"}
        run(self.t, 0.1)
        do_turns(self.t, self.pad)
        self.assertEqual(self.t.step.kind, "cruise")

        # Cruise only moves while the player stays on the center square.
        self.pad.zones = {"left"}
        head = self.t.game.snake.head
        run(self.t, 2)
        self.assertEqual(self.t.game.snake.head, head)
        self.assertIn("CENTER", self.t.hint)
        self.pad.zones = {"center"}
        run_until(self.t, "leave")
        self.pad.zones = set()
        self.t.handle(PlayerLost())
        self.assertEqual(self.t.step.kind, "return")
        self.pad.zones = {"center"}
        self.t.handle(PlayerFound())
        self.assertEqual(self.t.step.kind, "portal")

        drive_portal(self.t)
        run_until(self.t, "gate")
        drive_gate(self.t)
        run(self.t, 2.5)
        self.assertEqual(self.t.step.kind, "done")
        self.assertFalse(self.t.assisted)

    def test_stepping_off_mid_lesson_freezes_it(self):
        self.pad.zones = {"center"}
        run(self.t, 0.1)
        self.pad.zones = {"up"}
        self.t.handle(Turn(Direction.UP))
        self.t.handle(PlayerLost())
        head = self.t.game.snake.head
        run(self.t, 2)
        self.assertEqual(self.t.game.snake.head, head)
        self.assertIn("back onto the pad", self.t.hint)
        self.t.handle(PlayerFound())
        run(self.t, TURN_DEMO)
        self.assertEqual(self.t.step.kind, "center")


class TestPracticePacing(unittest.TestCase):
    def setUp(self):
        self.t = Tutorial(20, 15)
        while self.t.step.kind != "portal":
            self.t.skip()
            while self.t.step.kind == "turn" and self.t._moves_left:
                self.t.update(0.05)

    def test_portal_takes_a_turn_to_reach(self):
        (entry, exit_), = self.t.game.layout.portals
        head = self.t.game.snake.head
        self.assertNotEqual(entry[1], head[1], "entrance shouldn't be straight ahead")
        self.assertGreater(entry[0], head[0])
        self.assertLess(entry[1], head[1])

    def test_level_waits_before_moving(self):
        head = self.t.game.snake.head
        run(self.t, 1.9)
        self.assertEqual(self.t.game.snake.head, head)
        run(self.t, 0.3 + TICK)
        self.assertNotEqual(self.t.game.snake.head, head)
        self.assertEqual(self.t.hint, "")

    def test_key_takes_a_turn_to_reach(self):
        self.t.skip()                        # past the portal to the gate level
        (key, _), = self.t.game.keys.items()
        head = self.t.game.snake.head        # heading UP
        self.assertNotEqual(key[0], head[0], "key shouldn't be straight ahead")
        self.assertLess(key[1], head[1])

    def test_going_straight_up_misses_the_key(self):
        self.t.skip()
        wait_ready(self.t)
        ticks(self.t, 8)                     # into the top wall
        self.assertEqual(self.t.step.kind, "gate")
        self.assertEqual(self.t.records[-1].retries, 1)
        self.assertTrue(self.t.game.keys, "key still there on the fresh attempt")

    def test_going_straight_misses_the_portal(self):
        wait_ready(self.t)
        ticks(self.t, 12)                    # into the right wall
        self.assertEqual(self.t.step.kind, "portal")
        self.assertEqual(self.t.records[-1].retries, 1)


class TestTutorialLog(unittest.TestCase):
    def test_rows_and_total(self):
        t = Tutorial(20, 15)
        t.handle(Turn(Direction.DOWN))   # wrong
        t.skip()
        run(t, TURN_DEMO)
        t.abort()
        with tempfile.TemporaryDirectory() as tmp:
            path = write_tutorial_log(t, directory=tmp)
            with open(path, newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["step"], "turn_up")
        self.assertEqual(rows[0]["wrong_turns"], "1")
        self.assertEqual(rows[0]["skipped"], "1")
        self.assertEqual(rows[-1]["step"], "ABORTED")
        self.assertEqual(rows[-1]["skipped"], "1")


class TestTutorialScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        cls.pygame = pygame

    @classmethod
    def tearDownClass(cls):
        cls.pygame.quit()

    def test_draws_and_restores_the_main_game(self):
        from engine import Game
        from input import PadState
        from render.screen import WARNING, ScreenRenderer

        main_game = Game()
        renderer = ScreenRenderer(main_game,
                                  pad_state=lambda: PadState(frozenset({"center"})))
        pad = FakePad()
        pad.zones = {"center"}
        t = Tutorial(20, 15, has_pad=True, pad_zones=pad)
        run(t, 0.1)                              # past "stand"; now "step forward"
        self.assertEqual(t.step.target_zone, "up")
        surface = self.pygame.Surface((1280, 760))
        renderer.draw_tutorial(surface, t)
        self.assertIs(renderer.game, main_game)
        self.assertIsNone(renderer.pad_target)
        # The d-pad panel (right of the 960px board) outlines the target square.
        cell, left, top, panel = renderer._layout(surface)
        self.assertIsNotNone(panel)
        outlined = any(tuple(surface.get_at((x, y)))[:3] == WARNING
                       for x in range(panel.left, panel.right, 2)
                       for y in range(panel.top, panel.bottom, 2))
        self.assertTrue(outlined)


class TestFp2PadZones(unittest.TestCase):
    def test_reports_occupied_zone_names(self):
        from input.fp2.adapter import Fp2Input
        from input.fp2.config import parse
        from input.fp2.steering import ZoneEvent

        config = parse({"alias": "fp2", "debounce_ms": 0, "lost_grace_ms": 1000,
                        "zones": {"center": "1.10", "up": "1.13", "down": "1.16",
                                  "left": "1.19", "right": "1.22"}})
        fp2 = Fp2Input(config, client_factory=lambda *args: None)
        fp2._queue.put(ZoneEvent("1.10", True))
        fp2.poll()
        self.assertEqual(fp2.zone_state().occupied, {"center"})


if __name__ == "__main__":
    unittest.main()
