import random
from dataclasses import replace
from enum import Enum

from .direction import Direction
from .events import Event, EventBus, EventType
from .grid import Grid
from .layout import Layout
from .snake import Snake


class GameState(Enum):
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


class Game:
    """Snake rules and state. Knows nothing about input devices or drawing.

    Input adapters call set_direction(); the main loop calls step() once
    per tick (see Ticker); everything else listens on game.events.
    Physical objects (portals, keys, gates, wall markers) arrive as a
    Layout, either here or through load_layout() between rounds.
    """

    def __init__(self, width=20, height=15, walls=(), start_length=3,
                 start_direction=Direction.RIGHT, rng=None, events=None,
                 layout=None):
        self.width = width
        self.height = height
        self._apply_layout(layout or Layout(), extra_walls=walls)
        self.start_length = start_length
        self.start_direction = start_direction
        self.rng = rng or random.Random()
        self.events = events or EventBus()

        self.state = GameState.READY
        self.best = 0
        self._reset_round()

    def _apply_layout(self, layout, extra_walls=()):
        if extra_walls:
            layout = replace(layout, walls=layout.walls | set(extra_walls))
        layout.validate(self.width, self.height)
        self.layout = layout
        self.grid = Grid(self.width, self.height, layout.walls)
        self._portal_links = layout.portal_links()

    def load_layout(self, layout):
        """Swap in a new object map. Only allowed between rounds, so the
        play-field never changes under the player mid-round."""
        if self.state in (GameState.PLAYING, GameState.PAUSED):
            raise RuntimeError("load_layout() is only allowed between rounds")
        self._apply_layout(layout)
        self._reset_round()

    def _reset_round(self):
        start = (self.grid.width // 2, self.grid.height // 2)
        self.snake = Snake(start, self.start_direction, self.start_length)
        occupied = self.layout.occupied_cells()
        for cell in self.snake.body:
            if not self.grid.in_bounds(cell) or cell in occupied:
                raise ValueError(f"snake start cell {cell} is blocked by the layout")
        # Keys reappear and gates re-lock every round.
        self.keys = dict(self.layout.keys)
        self.locked_gates = dict(self.layout.gates)
        self.score = 0
        self.tick_count = 0
        self.won = False
        self.food = self._spawn_food()

    def _emit(self, event_type, **data):
        self.events.emit(Event(event_type, self.tick_count, data))

    def _spawn_food(self):
        # Food never lands on an object. Unlocked gates count as open floor.
        free = [cell for cell in self.grid.cells()
                if not self.grid.is_blocked(cell)
                and cell not in self.snake
                and cell not in self._portal_links
                and cell not in self.keys
                and cell not in self.locked_gates]
        return self.rng.choice(free) if free else None

    # --- state transitions -------------------------------------------------

    def start(self):
        """Begin a fresh round (also used to restart after game over)."""
        self._reset_round()
        self.state = GameState.PLAYING
        self._emit(EventType.GAME_START)

    def restart(self):
        self.start()

    def pause(self, reason=None):
        """Pause play, e.g. on player request or when sensor data goes stale."""
        if self.state is GameState.PLAYING:
            self.state = GameState.PAUSED
            self._emit(EventType.PAUSED, reason=reason)

    def resume(self):
        if self.state is GameState.PAUSED:
            self.state = GameState.PLAYING
            self._emit(EventType.RESUMED)

    # --- input ---------------------------------------------------------------

    def set_direction(self, direction):
        """Queue a turn for the next tick. Returns False if it was ignored."""
        if self.state is not GameState.PLAYING:
            return False
        return self.snake.queue_turn(direction)

    # --- tick ----------------------------------------------------------------

    def step(self):
        """Advance the game by one tick."""
        if self.state is not GameState.PLAYING:
            return

        self.tick_count += 1
        if self.snake.apply_turn():
            self._emit(EventType.DIRECTION_CHANGED, direction=self.snake.direction)

        new_head = self.snake.next_head()
        portal_entry = None
        if new_head in self._portal_links:
            # Stepping into a portal puts the head on its partner; the snake
            # keeps its heading and the body follows through over later ticks.
            portal_entry = new_head
            new_head = self._portal_links[new_head]
        grow = new_head == self.food

        collision = self._collision_at(new_head, grow)
        if collision:
            self._emit(EventType.COLLISION, kind=collision, cell=new_head)
            self._end()
            return

        self.snake.move(grow, to=new_head)
        if portal_entry is not None:
            self._emit(EventType.PORTAL_USED, entry=portal_entry, exit=new_head)
        if new_head in self.keys:
            self._collect_key(new_head)
        if grow:
            self.score += 1
            self.food = self._spawn_food()
            self._emit(EventType.FOOD_EATEN, cell=new_head, score=self.score)
            if self.food is None:
                self.won = True
                self._end()

    def _collision_at(self, cell, grow):
        if not self.grid.in_bounds(cell):
            return "boundary"
        if cell in self.grid.walls:
            return "wall"
        if cell in self.locked_gates:
            return "gate"
        # The tail moves out of the way this tick unless the snake is growing.
        if cell in self.snake and not (cell == self.snake.tail and not grow):
            return "self"
        return None

    def _collect_key(self, cell):
        key_id = self.keys.pop(cell)
        self._emit(EventType.KEY_COLLECTED, key_id=key_id, cell=cell)
        opened = [c for c, gate_id in self.locked_gates.items() if gate_id == key_id]
        for c in opened:
            del self.locked_gates[c]
        if opened:
            self._emit(EventType.GATE_UNLOCKED, gate_id=key_id, cells=tuple(opened))

    def _end(self):
        self.state = GameState.GAME_OVER
        new_best = self.score > self.best
        self.best = max(self.best, self.score)
        self._emit(EventType.GAME_OVER, score=self.score, best=self.best,
                   new_best=new_best, won=self.won)
