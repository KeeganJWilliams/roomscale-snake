import random
import unittest

from engine import Direction, EventType, Game, GameState, Ticker


def make_game(**kwargs):
    kwargs.setdefault("rng", random.Random(0))
    game = Game(**kwargs)
    game.start()
    return game


class RecordingListener:
    def __init__(self, game):
        self.events = []
        game.events.subscribe(self.events.append)

    def types(self):
        return [e.type for e in self.events]


class TestMovement(unittest.TestCase):
    def test_moves_one_cell_per_step(self):
        game = make_game(width=10, height=10)
        game.food = (0, 0)
        head = game.snake.head
        game.step()
        self.assertEqual(game.snake.head, (head[0] + 1, head[1]))
        self.assertEqual(len(game.snake), 3)

    def test_turn_applies_on_next_step(self):
        game = make_game(width=10, height=10)
        game.food = (0, 0)
        hx, hy = game.snake.head
        self.assertTrue(game.set_direction(Direction.UP))
        self.assertEqual(game.snake.direction, Direction.RIGHT)
        game.step()
        self.assertEqual(game.snake.head, (hx, hy - 1))

    def test_reverse_is_ignored(self):
        game = make_game()
        self.assertFalse(game.set_direction(Direction.LEFT))

    def test_two_quick_turns_cannot_reverse_into_self(self):
        game = make_game(width=10, height=10)
        game.food = (0, 0)
        # Moving RIGHT: UP is valid, then LEFT is still checked against RIGHT.
        game.set_direction(Direction.UP)
        self.assertFalse(game.set_direction(Direction.LEFT))
        game.step()
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertEqual(game.snake.direction, Direction.UP)

    def test_input_ignored_when_not_playing(self):
        game = make_game()
        game.pause()
        self.assertFalse(game.set_direction(Direction.UP))


class TestFoodAndScore(unittest.TestCase):
    def test_eating_grows_and_scores(self):
        game = make_game(width=10, height=10)
        listener = RecordingListener(game)
        hx, hy = game.snake.head
        game.food = (hx + 1, hy)
        game.step()
        self.assertEqual(len(game.snake), 4)
        self.assertEqual(game.score, 1)
        self.assertIn(EventType.FOOD_EATEN, listener.types())
        self.assertNotIn(game.food, game.snake)

    def test_food_never_spawns_on_wall_or_snake(self):
        walls = {(x, 0) for x in range(10)}
        game = make_game(width=10, height=10, walls=walls)
        for _ in range(200):
            food = game._spawn_food()
            self.assertNotIn(food, walls)
            self.assertNotIn(food, game.snake)

    def test_filling_the_grid_wins(self):
        game = make_game(width=3, height=1, start_length=2)
        game.food = (2, 0)
        game.step()
        self.assertEqual(game.state, GameState.GAME_OVER)
        self.assertTrue(game.won)


class TestCollisions(unittest.TestCase):
    def test_boundary_ends_game(self):
        game = make_game(width=5, height=5)
        game.food = (0, 0)
        listener = RecordingListener(game)
        for _ in range(3):
            game.step()
        self.assertEqual(game.state, GameState.GAME_OVER)
        collision = next(e for e in listener.events if e.type is EventType.COLLISION)
        self.assertEqual(collision.data["kind"], "boundary")

    def test_wall_ends_game(self):
        game = make_game(width=10, height=10, walls={(6, 5)})
        game.food = (0, 0)
        listener = RecordingListener(game)
        game.step()
        collision = next(e for e in listener.events if e.type is EventType.COLLISION)
        self.assertEqual(collision.data["kind"], "wall")

    def test_self_collision(self):
        game = make_game(width=10, height=10, start_length=5)
        game.food = (0, 0)
        for d in (Direction.UP, Direction.LEFT, Direction.DOWN):
            game.set_direction(d)
            game.step()
        self.assertEqual(game.state, GameState.GAME_OVER)

    def test_can_follow_own_tail(self):
        # A 4-long snake turning in a tight square moves into the cell its
        # tail is leaving, which is legal.
        game = make_game(width=10, height=10, start_length=4)
        game.food = (0, 0)
        for d in (Direction.UP, Direction.LEFT, Direction.DOWN, Direction.RIGHT):
            game.set_direction(d)
            game.step()
        self.assertEqual(game.state, GameState.PLAYING)


class TestStates(unittest.TestCase):
    def test_pause_freezes_and_resume_continues(self):
        game = make_game(width=10, height=10)
        game.food = (0, 0)
        head = game.snake.head
        game.pause(reason="stale_input")
        game.step()
        self.assertEqual(game.snake.head, head)
        game.resume()
        game.step()
        self.assertNotEqual(game.snake.head, head)

    def test_restart_keeps_best(self):
        game = make_game(width=10, height=10)
        hx, hy = game.snake.head
        game.food = (hx + 1, hy)
        game.step()
        game._end()
        self.assertEqual(game.best, 1)
        game.restart()
        self.assertEqual(game.score, 0)
        self.assertEqual(game.best, 1)
        self.assertEqual(game.state, GameState.PLAYING)

    def test_failing_listener_does_not_break_game(self):
        game = make_game(width=10, height=10)

        def broken(event):
            raise RuntimeError("Hue bridge offline")

        game.events.subscribe(broken)
        with self.assertLogs("engine.events", level="ERROR"):
            game.pause()
        self.assertEqual(game.state, GameState.PAUSED)


class TestTicker(unittest.TestCase):
    def test_fixed_rate(self):
        ticker = Ticker(cells_per_second=4)
        # 10 seconds at 60 fps; allow one tick of float rounding at the edge.
        total = sum(ticker.update(1 / 60) for _ in range(600))
        self.assertAlmostEqual(total, 40, delta=1)

    def test_long_stall_is_capped(self):
        ticker = Ticker(cells_per_second=4, max_ticks_per_update=5)
        self.assertEqual(ticker.update(10.0), 5)
        self.assertEqual(ticker.update(0.0), 0)


if __name__ == "__main__":
    unittest.main()
