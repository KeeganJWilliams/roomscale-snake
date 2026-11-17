import pygame

from engine import Direction

from .base import Turn, now_ns

KEY_DIRECTIONS = {
    pygame.K_UP: Direction.UP,
    pygame.K_w: Direction.UP,
    pygame.K_DOWN: Direction.DOWN,
    pygame.K_s: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT,
    pygame.K_a: Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT,
    pygame.K_d: Direction.RIGHT,
}


class KeyboardInput:
    """Development controller: arrow keys or WASD.

    An InputSource like every other adapter: handle_event() collects
    pygame key presses, poll() hands the main loop Commands. It never
    emits PlayerLost, so the keyboard alone never pauses the game.
    """

    def __init__(self):
        self._latest = None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in KEY_DIRECTIONS:
            self._latest = Turn(KEY_DIRECTIONS[event.key], t_recv_ns=now_ns())

    def poll(self):
        """Return the most recent direction since the last poll, if any."""
        turn, self._latest = self._latest, None
        return [turn] if turn is not None else []

    def close(self):
        pass
