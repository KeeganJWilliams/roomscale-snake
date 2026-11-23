import time

import pygame

from engine import Direction

from .base import PadState, Turn, now_ns

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

# A tap lights its d-pad square at least this long, so quick presses show.
FLASH_S = 0.25


class KeyboardInput:
    """Development controller: arrow keys or WASD.

    An InputSource like every other adapter: handle_event() collects
    pygame key presses, poll() hands the main loop Commands. It never
    emits PlayerLost, so the keyboard alone never pauses the game.
    """

    def __init__(self, clock=time.monotonic):
        self._latest = None
        self._clock = clock
        self._held = set()     # pygame keys currently down
        self._flash = {}       # Direction -> time its square stops being lit

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in KEY_DIRECTIONS:
            direction = KEY_DIRECTIONS[event.key]
            self._latest = Turn(direction, t_recv_ns=now_ns())
            self._held.add(event.key)
            self._flash[direction] = self._clock() + FLASH_S
        elif event.type == pygame.KEYUP:
            self._held.discard(event.key)

    def poll(self):
        """Return the most recent direction since the last poll, if any."""
        turn, self._latest = self._latest, None
        return [turn] if turn is not None else []

    def zone_state(self):
        """What the d-pad panel shows for the keyboard, mirroring the FP2:
        the direction being pressed (held, or tapped in the last FLASH_S),
        otherwise "center", like a player standing still on the pad."""
        now = self._clock()
        lit = {KEY_DIRECTIONS[key] for key in self._held}
        lit |= {d for d, until in self._flash.items() if until > now}
        names = frozenset(d.name.lower() for d in lit)
        return PadState(occupied=names or frozenset({"center"}))

    def close(self):
        pass
