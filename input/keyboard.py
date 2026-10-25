import pygame

from engine import Direction

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

    Like every input adapter it only produces Directions. The main loop
    calls poll() once per frame and passes the result to the game, so
    the Sensy One and FP2 adapters can share the same poll() interface.
    """

    def __init__(self):
        self._latest = None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in KEY_DIRECTIONS:
            self._latest = KEY_DIRECTIONS[event.key]

    def poll(self):
        """Return the most recent direction since the last poll, or None."""
        direction, self._latest = self._latest, None
        return direction
