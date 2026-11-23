import pygame

from engine import GameState

BACKGROUND = (12, 14, 20)
BORDER = (70, 78, 96)
WALL = (110, 116, 130)
FOOD = (235, 70, 80)
SNAKE_HEAD = (120, 230, 120)
SNAKE_BODY = (60, 170, 80)
TEXT = (235, 235, 235)
# One color per portal pair and per key/gate id, so players can see what
# goes with what. Portals and keys/gates use separate sets so a portal is
# never mistaken for a gate. Colors wrap around if there are more ids.
PORTAL_COLORS = [
    (80, 160, 255),   # blue
    (40, 220, 210),   # teal
    (255, 255, 255),  # white
]
KEY_COLORS = [
    (255, 170, 40),   # orange
    (200, 90, 255),   # purple
    (255, 230, 70),   # yellow
    (255, 120, 190),  # pink
]
OVERLAY = (0, 0, 0, 160)

# The on-screen d-pad mirrors the taped floor pad: lit zones are the ones
# the FP2 currently reports, so a player can see the sensor keeping up.
DPAD_DEAD = (26, 29, 38)
DPAD_IDLE = (46, 52, 66)
DPAD_EDGE = (70, 78, 96)
DPAD_GLYPH = (150, 158, 176)
DPAD_ON = (120, 230, 120)
DPAD_CENTER_ON = (90, 165, 255)

HUD_HEIGHT = 40
GUTTER = 10
# Below this the leftover strip is too cramped for a readable pad.
DPAD_MIN_PX = 120
# 3x3 pad: corners are the unassigned dead zones on the floor.
DPAD_CELLS = {"up": (1, 0), "left": (0, 1), "center": (1, 1),
              "right": (2, 1), "down": (1, 2)}
DPAD_DEAD_CELLS = ((0, 0), (2, 0), (0, 2), (2, 2))


def compute_layout(width, height, cols, rows):
    """Place the play area and, in the leftover space, the d-pad panel.

    The cell size is worked out from the whole window first, so the play
    area is exactly the size it would be with no d-pad at all. Whatever
    is left over becomes the panel and the grid shifts off it; if there is
    too little to be legible, the panel is None and the grid stays
    centred as before.
    """
    cell = max(1, min(width // cols, (height - HUD_HEIGHT) // rows))
    grid_w, grid_h = cell * cols, cell * rows
    slack_x = width - grid_w
    slack_y = height - HUD_HEIGHT - grid_h

    if slack_x >= DPAD_MIN_PX and slack_x >= slack_y:
        # Widest strip is beside the grid: pad on the right, grid flush left.
        return (cell, 0, HUD_HEIGHT + slack_y // 2,
                pygame.Rect(grid_w, HUD_HEIGHT, slack_x, height - HUD_HEIGHT))
    if slack_y >= DPAD_MIN_PX:
        # Widest strip is below: pad along the bottom, grid pushed up.
        return (cell, slack_x // 2, HUD_HEIGHT,
                pygame.Rect(0, HUD_HEIGHT + grid_h, width, slack_y))
    return cell, slack_x // 2, HUD_HEIGHT + slack_y // 2, None


class ScreenRenderer:
    """Draws the game to a pygame surface. Reads game state, never changes it.

    The grid is scaled to fit the window and centered, so resizing or
    switching to the projector's resolution just works. Keystone is
    handled by the projector itself, so no warping happens here.
    """

    def __init__(self, game, pad_state=None):
        self.game = game
        # Optional callable returning the live pad state (.occupied, .lost).
        # None for keyboard-only play, where the pad is drawn as a legend.
        self.pad_state = pad_state
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 64)

    def _layout(self, surface):
        grid = self.game.grid
        width, height = surface.get_size()
        return compute_layout(width, height, grid.width, grid.height)

    def draw(self, surface):
        surface.fill(BACKGROUND)
        cell, left, top, panel = self._layout(surface)

        def rect(x, y, inset=0):
            return pygame.Rect(left + x * cell + inset, top + y * cell + inset,
                               cell - 2 * inset, cell - 2 * inset)

        grid = self.game.grid
        pygame.draw.rect(surface, BORDER,
                         (left, top, cell * grid.width, cell * grid.height), 2)
        for x, y in grid.walls:
            pygame.draw.rect(surface, WALL, rect(x, y))
        self._draw_objects(surface, cell, rect)

        if self.game.food is not None:
            pygame.draw.rect(surface, FOOD, rect(*self.game.food, inset=cell // 6),
                             border_radius=cell // 3)

        for i, (x, y) in enumerate(self.game.snake.body):
            color = SNAKE_HEAD if i == 0 else SNAKE_BODY
            pygame.draw.rect(surface, color, rect(x, y, inset=1), border_radius=cell // 5)

        if panel is not None:
            self._draw_dpad(surface, panel)
        self._draw_hud(surface)
        self._draw_overlay(surface)

    @staticmethod
    def _color(index, palette):
        return palette[index % len(palette)]

    def _draw_objects(self, surface, cell, rect):
        game = self.game
        thick = max(2, cell // 8)

        # Portals: a ring in the pair's color.
        for i, pair in enumerate(game.layout.portals):
            for x, y in pair:
                pygame.draw.ellipse(surface, self._color(i, PORTAL_COLORS), rect(x, y, inset=cell // 10),
                                    thick)

        # Gates: solid with bars while locked, a faint outline once open.
        for (x, y), gate_id in game.layout.gates.items():
            color = self._color(gate_id, KEY_COLORS)
            r = rect(x, y)
            if (x, y) in game.locked_gates:
                pygame.draw.rect(surface, color, r)
                for i in range(1, 3):
                    bx = r.left + r.width * i // 3
                    pygame.draw.line(surface, BACKGROUND, (bx, r.top), (bx, r.bottom - 1),
                                     max(1, thick // 2))
            else:
                pygame.draw.rect(surface, color, r, 1)

        # Keys: a diamond in the color of the gates they open.
        for (x, y), key_id in game.keys.items():
            r = rect(x, y, inset=cell // 5)
            points = [r.midtop, r.midright, r.midbottom, r.midleft]
            pygame.draw.polygon(surface, self._color(key_id, KEY_COLORS), points)

    def _draw_dpad(self, surface, panel):
        """Draw the floor d-pad, lighting the zones the sensor reports.

        Purely a mirror of the input state: with no sensor attached it is
        still drawn, unlit, as a legend for the taped layout.
        """
        state = self.pad_state() if self.pad_state is not None else None
        occupied = frozenset(getattr(state, "occupied", None) or ())
        lost = bool(getattr(state, "lost", False))

        pad = panel.inflate(-2 * GUTTER, -2 * GUTTER)
        caption_h = self.small_font.get_height() + GUTTER
        size = min(pad.width, pad.height - caption_h)
        if size < DPAD_MIN_PX:
            return

        cell = size // 3
        side = cell * 3
        ox = pad.centerx - side // 2
        oy = pad.top + max(0, (pad.height - caption_h - side) // 2)
        gap = max(2, cell // 14)
        radius = max(3, cell // 8)

        def cell_rect(cx, cy):
            return pygame.Rect(ox + cx * cell, oy + cy * cell,
                               cell, cell).inflate(-2 * gap, -2 * gap)

        # Unassigned corners, so the shape reads as the floor layout.
        for cx, cy in DPAD_DEAD_CELLS:
            pygame.draw.rect(surface, DPAD_DEAD, cell_rect(cx, cy),
                             border_radius=radius)

        for name, (cx, cy) in DPAD_CELLS.items():
            r = cell_rect(cx, cy)
            active = name in occupied and not lost
            if active:
                fill = DPAD_CENTER_ON if name == "center" else DPAD_ON
            else:
                fill = DPAD_IDLE
            pygame.draw.rect(surface, fill, r, border_radius=radius)
            pygame.draw.rect(surface, DPAD_EDGE, r, 2, border_radius=radius)
            glyph = BACKGROUND if active else DPAD_GLYPH
            if name == "center":
                pygame.draw.circle(surface, glyph, r.center,
                                   max(3, min(r.width, r.height) // 7), 2)
            else:
                self._draw_arrow(surface, r, name, glyph)

        if self.pad_state is None:
            caption = "floor d-pad"
        elif lost:
            caption = "no player on pad"
        elif occupied:
            caption = " + ".join(sorted(occupied))
        else:
            caption = "pad empty"
        label = self.small_font.render(caption, True, DPAD_GLYPH)
        surface.blit(label, label.get_rect(midtop=(pad.centerx, oy + side + GUTTER)))

    @staticmethod
    def _draw_arrow(surface, r, name, color):
        cx, cy = r.center
        h = max(3, min(r.width, r.height) // 4)
        if name == "up":
            points = [(cx, cy - h), (cx - h, cy + h), (cx + h, cy + h)]
        elif name == "down":
            points = [(cx, cy + h), (cx - h, cy - h), (cx + h, cy - h)]
        elif name == "left":
            points = [(cx - h, cy), (cx + h, cy - h), (cx + h, cy + h)]
        else:
            points = [(cx + h, cy), (cx - h, cy - h), (cx - h, cy + h)]
        pygame.draw.polygon(surface, color, points)

    def _draw_hud(self, surface):
        text = f"Score: {self.game.score}    Best: {self.game.best}"
        surface.blit(self.font.render(text, True, TEXT), (12, 10))

    def _draw_overlay(self, surface):
        state = self.game.state
        if state is GameState.PLAYING:
            return

        if state is GameState.READY:
            lines = ["ROOM-SCALE SNAKE", "Press SPACE to start"]
        elif state is GameState.PAUSED:
            lines = ["PAUSED", "Press P to resume"]
        else:
            title = "YOU WIN!" if self.game.won else "GAME OVER"
            lines = [title, f"Score: {self.game.score}", "Press SPACE to play again"]

        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill(OVERLAY)
        surface.blit(shade, (0, 0))

        cx, cy = surface.get_width() // 2, surface.get_height() // 2
        y = cy - 40 * (len(lines) - 1) // 2
        for i, line in enumerate(lines):
            font = self.big_font if i == 0 else self.font
            label = font.render(line, True, TEXT)
            surface.blit(label, label.get_rect(center=(cx, y)))
            y += 50 if i == 0 else 36
