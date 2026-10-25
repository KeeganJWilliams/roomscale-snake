import pygame

from engine import GameState

BACKGROUND = (12, 14, 20)
BORDER = (70, 78, 96)
WALL = (110, 116, 130)
FOOD = (235, 70, 80)
SNAKE_HEAD = (120, 230, 120)
SNAKE_BODY = (60, 170, 80)
TEXT = (235, 235, 235)
OVERLAY = (0, 0, 0, 160)

HUD_HEIGHT = 40


class ScreenRenderer:
    """Draws the game to a pygame surface. Reads game state, never changes it.

    The grid is scaled to fit the window and centered, so resizing or
    switching to the projector's resolution just works. Homography
    warping for the projector will be added here later.
    """

    def __init__(self, game):
        self.game = game
        self.font = pygame.font.Font(None, 32)
        self.big_font = pygame.font.Font(None, 64)

    def _layout(self, surface):
        grid = self.game.grid
        width, height = surface.get_size()
        cell = max(1, min(width // grid.width, (height - HUD_HEIGHT) // grid.height))
        left = (width - cell * grid.width) // 2
        top = HUD_HEIGHT + (height - HUD_HEIGHT - cell * grid.height) // 2
        return cell, left, top

    def draw(self, surface):
        surface.fill(BACKGROUND)
        cell, left, top = self._layout(surface)

        def rect(x, y, inset=0):
            return pygame.Rect(left + x * cell + inset, top + y * cell + inset,
                               cell - 2 * inset, cell - 2 * inset)

        grid = self.game.grid
        pygame.draw.rect(surface, BORDER,
                         (left, top, cell * grid.width, cell * grid.height), 2)
        for x, y in grid.walls:
            pygame.draw.rect(surface, WALL, rect(x, y))

        if self.game.food is not None:
            pygame.draw.rect(surface, FOOD, rect(*self.game.food, inset=cell // 6),
                             border_radius=cell // 3)

        for i, (x, y) in enumerate(self.game.snake.body):
            color = SNAKE_HEAD if i == 0 else SNAKE_BODY
            pygame.draw.rect(surface, color, rect(x, y, inset=1), border_radius=cell // 5)

        self._draw_hud(surface)
        self._draw_overlay(surface)

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
