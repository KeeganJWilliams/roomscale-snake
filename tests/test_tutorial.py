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
from tutorial.tutorial import PRACTICE_SPEED

TICK = 1.0 / PRACTICE_SPEED + 1e-4   # one practice tick


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
        run(tutorial, 1.5)
        if pad is not None and tutorial.step.kind == "center":
            pad.zones = {"center"}
            run(tutorial, 0.1)


def drive_gate(tutorial):
    """Steer the gate practice: up past the key, right, down, right through."""
    ticks(tutorial, 5)                       # up to (10, 2), key collected on the way
    tutorial.handle(Turn(Direction.RIGHT))
    ticks(tutorial, 2)                       # (12, 2)
    tutorial.handle(Turn(Direction.DOWN))
    ticks(tutorial, 5)                       # (12, 7)
    tutorial.handle(Turn(Direction.RIGHT))
    ticks(tutorial, 3)                       # through the gate at x=14


class TestKeyboardTutorial(unittest.TestCase):
    def test_full_run_without_a_pad(self):
        t = Tutorial(20, 15, has_pad=False)
        self.assertNotIn("stand", [s.name for s in t.steps])
        self.assertTrue(t.step.title.startswith("Press the UP arrow"))

        do_turns(t)
        self.assertEqual(t.step.kind, "cruise")
        run_until(t, "portal")
        run_until(t, "gate")                 # the portal is straight ahead
        drive_gate(t)
        run(t, 1.5)                          # "Nice!" pause
        self.assertEqual(t.step.kind, "done")
        self.assertIsNotNone(t.completion_seconds)
        run(t, 5)
        self.assertTrue(t.finished)
        self.assertFalse(t.assisted)

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
        t.handle(Turn(Direction.RIGHT))     # straight at the locked gate
        ticks(t, 5)
        self.assertEqual(t.step.kind, "gate")
        self.assertEqual(t.records[-1].retries, 1)
        self.assertIn("KEY first", t.hint)
        self.assertEqual(t.game.snake.head, (10, 7))   # fresh attempt

    def test_skip_marks_the_run_assisted(self):
        t = Tutorial(20, 15)
        t.skip()
        run(t, 1.5)
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
        run(self.t, 1.5)
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

        run_until(self.t, "gate")
        drive_gate(self.t)
        run(self.t, 1.5)
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
        run(self.t, 1.5)
        self.assertEqual(self.t.step.kind, "center")


class TestTutorialLog(unittest.TestCase):
    def test_rows_and_total(self):
        t = Tutorial(20, 15)
        t.handle(Turn(Direction.DOWN))   # wrong
        t.skip()
        run(t, 1.5)
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
        from render.screen import ScreenRenderer, SNAKE_HEAD

        main_game = Game()
        renderer = ScreenRenderer(main_game)
        t = Tutorial(20, 15, has_pad=True, pad_zones=FakePad())
        surface = self.pygame.Surface((1280, 800))
        renderer.draw_tutorial(surface, t, pad_zones={"center"})
        self.assertIs(renderer.game, main_game)
        # The pad's center square is lit.
        from render.screen import PAD_CELL
        cx = 1280 - 3 * PAD_CELL - 16 + PAD_CELL + PAD_CELL // 2
        cy = 26 + PAD_CELL + PAD_CELL // 2
        self.assertEqual(tuple(surface.get_at((cx, cy)))[:3], SNAKE_HEAD)


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
        self.assertEqual(fp2.pad_zones(), {"center"})


if __name__ == "__main__":
    unittest.main()
