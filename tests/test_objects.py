import random
import unittest

from engine import Direction, EventType, Game, GameState, Layout

# On a 10x10 grid the snake starts with its head at (5, 5) heading RIGHT,
# body (4, 5), (3, 5). Its first step lands on (6, 5).


def make_game(layout, **kwargs):
    kwargs.setdefault("rng", random.Random(0))
    kwargs.setdefault("width", 10)
    kwargs.setdefault("height", 10)
    game = Game(layout=layout, **kwargs)
    game.start()
    game.food = (0, 0)
    return game


def record(game):
    events = []
    game.events.subscribe(events.append)
    return events


def first(events, event_type):
    return next(e for e in events if e.type is event_type)


class TestPortals(unittest.TestCase):
    def test_entering_portal_moves_head_to_partner(self):
        game = make_game(Layout(portals=[((6, 5), (2, 8))]))
        events = record(game)
        game.step()
        self.assertEqual(game.snake.head, (2, 8))
        self.assertEqual(game.snake.direction, Direction.RIGHT)
        used = first(events, EventType.PORTAL_USED)
        self.assertEqual(used.data, {"entry": (6, 5), "exit": (2, 8)})

    def test_snake_keeps_heading_after_exit(self):
        game = make_game(Layout(portals=[((6, 5), (2, 8))]))
        game.step()
        game.step()
        self.assertEqual(game.snake.head, (3, 8))
        self.assertEqual(game.state, GameState.PLAYING)

    def test_body_follows_through_portal(self):
        game = make_game(Layout(portals=[((6, 5), (2, 8))]))
        for _ in range(3):
            game.step()
        self.assertEqual(list(game.snake.body), [(4, 8), (3, 8), (2, 8)])

    def test_portals_work_both_ways(self):
        game = make_game(Layout(portals=[((2, 8), (6, 5))]))
        game.step()
        self.assertEqual(game.snake.head, (2, 8))

    def test_blocked_exit_is_a_collision(self):
        # A 6-long snake goes through (6, 5) -> (6, 8), loops back up, and
        # re-enters (6, 5) while its body still covers the exit (6, 8).
        game = make_game(Layout(portals=[((6, 5), (6, 8))]), start_length=6)
        path = [None, None, Direction.UP, None, None, Direction.LEFT]
        events = record(game)
        for turn in path:
            if turn:
                game.set_direction(turn)
            game.step()
        # (6, 8) is a body cell that isn't the tail, so this is a self-hit.
        self.assertEqual(game.state, GameState.GAME_OVER)
        self.assertEqual(first(events, EventType.COLLISION).data["kind"], "self")

    def test_food_on_exit_is_eaten(self):
        game = make_game(Layout(portals=[((6, 5), (2, 8))]))
        # Food is never spawned on a portal, but the exit cell's neighbor works.
        game.food = (3, 8)
        game.step()
        game.step()
        self.assertEqual(game.score, 1)

    def test_food_never_spawns_on_portal(self):
        game = make_game(Layout(portals=[((6, 5), (2, 8))]))
        for _ in range(300):
            self.assertNotIn(game._spawn_food(), {(6, 5), (2, 8)})


class TestKeysAndGates(unittest.TestCase):
    def test_locked_gate_is_a_collision(self):
        game = make_game(Layout(gates={(6, 5): 1}))
        events = record(game)
        game.step()
        self.assertEqual(game.state, GameState.GAME_OVER)
        self.assertEqual(first(events, EventType.COLLISION).data["kind"], "gate")

    def test_key_unlocks_matching_gates(self):
        game = make_game(Layout(keys={(6, 5): 1},
                                gates={(8, 5): 1, (8, 6): 1, (9, 9): 2}))
        events = record(game)
        game.step()
        self.assertNotIn((6, 5), game.keys)
        self.assertEqual(game.locked_gates, {(9, 9): 2})
        collected = first(events, EventType.KEY_COLLECTED)
        self.assertEqual(collected.data, {"key_id": 1, "cell": (6, 5)})
        unlocked = first(events, EventType.GATE_UNLOCKED)
        self.assertEqual(unlocked.data["gate_id"], 1)
        self.assertEqual(set(unlocked.data["cells"]), {(8, 5), (8, 6)})

    def test_snake_passes_through_unlocked_gate(self):
        game = make_game(Layout(keys={(6, 5): 1}, gates={(8, 5): 1}))
        for _ in range(3):
            game.step()
        self.assertEqual(game.snake.head, (8, 5))
        self.assertEqual(game.state, GameState.PLAYING)

    def test_key_does_not_grow_or_score(self):
        game = make_game(Layout(keys={(6, 5): 1}, gates={(8, 5): 1}))
        game.step()
        self.assertEqual(len(game.snake), 3)
        self.assertEqual(game.score, 0)

    def test_key_without_gate_is_collected_quietly(self):
        game = make_game(Layout(keys={(6, 5): 3}))
        events = record(game)
        game.step()
        self.assertIn(EventType.KEY_COLLECTED, [e.type for e in events])
        self.assertNotIn(EventType.GATE_UNLOCKED, [e.type for e in events])

    def test_keys_and_gates_reset_each_round(self):
        game = make_game(Layout(keys={(6, 5): 1}, gates={(8, 5): 1}))
        game.step()
        self.assertEqual(game.locked_gates, {})
        game.restart()
        self.assertEqual(game.keys, {(6, 5): 1})
        self.assertEqual(game.locked_gates, {(8, 5): 1})

    def test_food_never_spawns_on_key_or_locked_gate(self):
        game = make_game(Layout(keys={(1, 1): 1}, gates={(2, 2): 1}))
        for _ in range(300):
            self.assertNotIn(game._spawn_food(), {(1, 1), (2, 2)})


class TestLayout(unittest.TestCase):
    def test_overlapping_objects_rejected(self):
        with self.assertRaises(ValueError):
            Game(layout=Layout(walls={(1, 1)}, keys={(1, 1): 1}))

    def test_out_of_bounds_rejected(self):
        with self.assertRaises(ValueError):
            Game(width=5, height=5, layout=Layout(portals=[((0, 0), (9, 9))]))

    def test_portal_must_be_a_pair(self):
        with self.assertRaises(ValueError):
            Game(layout=Layout(portals=[((0, 0), (1, 1), (2, 2))]))

    def test_object_on_snake_start_rejected(self):
        with self.assertRaises(ValueError):
            Game(width=10, height=10, layout=Layout(keys={(5, 5): 1}))

    def test_walls_argument_merges_with_layout(self):
        game = Game(width=10, height=10, walls={(0, 0)},
                    layout=Layout(walls={(9, 9)}))
        self.assertEqual(game.grid.walls, {(0, 0), (9, 9)})

    def test_load_layout_between_rounds(self):
        game = Game(width=10, height=10, rng=random.Random(0))
        game.load_layout(Layout(gates={(6, 5): 1}))
        game.start()
        game.food = (0, 0)
        game.step()
        self.assertEqual(game.state, GameState.GAME_OVER)

    def test_load_layout_refused_mid_round(self):
        game = make_game(Layout())
        with self.assertRaises(RuntimeError):
            game.load_layout(Layout(walls={(0, 0)}))
        game.pause()
        with self.assertRaises(RuntimeError):
            game.load_layout(Layout(walls={(0, 0)}))


if __name__ == "__main__":
    unittest.main()
