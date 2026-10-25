import random
from enum import Enum

from .direction import Direction
from .events import Event, EventBus, EventType
from .grid import Grid
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
    """

    def __init__(self, width=20, height=15, walls=(), start_length=3,
                 start_direction=Direction.RIGHT, rng=None, events=None):
        self.grid = Grid(width, height, walls)
        self.start_length = start_length
        self.start_direction = start_direction
        self.rng = rng or random.Random()
        self.events = events or EventBus()

        self.state = GameState.READY
        self.best = 0
        self._reset_round()

    def _reset_round(self):
        start = (self.grid.width // 2, self.grid.height // 2)
        self.snake = Snake(start, self.start_direction, self.start_length)
        for cell in self.snake.body:
            if self.grid.is_blocked(cell):
                raise ValueError(f"snake start cell {cell} is blocked")
        self.score = 0
        self.tick_count = 0
        self.won = False
        self.food = self._spawn_food()

    def _emit(self, event_type, **data):
        self.events.emit(Event(event_type, self.tick_count, data))

    def _spawn_food(self):
        free = [cell for cell in self.grid.cells()
                if not self.grid.is_blocked(cell) and cell not in self.snake]
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
        grow = new_head == self.food

        collision = self._collision_at(new_head, grow)
        if collision:
            self._emit(EventType.COLLISION, kind=collision, cell=new_head)
            self._end()
            return

        self.snake.move(grow)
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
        # The tail moves out of the way this tick unless the snake is growing.
        if cell in self.snake and not (cell == self.snake.tail and not grow):
            return "self"
        return None

    def _end(self):
        self.state = GameState.GAME_OVER
        new_best = self.score > self.best
        self.best = max(self.best, self.score)
        self._emit(EventType.GAME_OVER, score=self.score, best=self.best,
                   new_best=new_best, won=self.won)
