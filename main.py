"""Room-Scale Snake: keyboard demo.

Controls: arrow keys / WASD steer, SPACE starts or restarts,
P pauses, F11 toggles fullscreen, ESC quits.
--demo-objects adds sample portals, keys, and gates for play-testing.
"""

import argparse
import logging

import pygame

from engine import Game, GameState, Layout, Ticker
from input.keyboard import KeyboardInput
from render.screen import ScreenRenderer

FPS = 60

# Hand-placed objects for play-testing before marker detection is wired in.
# Fits the default 20x15 grid; the snake starts at (10, 7) heading right.
DEMO_LAYOUT = Layout(
    portals=[((3, 3), (16, 11)), ((16, 3), (3, 11))],
    keys={(10, 2): 1, (6, 13): 2},
    gates={(18, 6): 1, (18, 7): 1, (18, 8): 1,
           (12, 12): 2, (12, 13): 2, (12, 14): 2},
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cols", type=int, default=20, help="grid width in cells")
    parser.add_argument("--rows", type=int, default=15, help="grid height in cells")
    parser.add_argument("--speed", type=float, default=3.0,
                        help="snake speed in cells per second (default 3)")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--demo-objects", action="store_true",
                        help="add sample portals, keys, and gates (needs at least 20x15)")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    pygame.init()
    pygame.display.set_caption("Room-Scale Snake")
    flags = pygame.FULLSCREEN if args.fullscreen else pygame.RESIZABLE
    screen = pygame.display.set_mode((960, 760), flags)
    clock = pygame.time.Clock()

    layout = DEMO_LAYOUT if args.demo_objects else None
    game = Game(width=args.cols, height=args.rows, layout=layout)
    ticker = Ticker(cells_per_second=args.speed)
    keyboard = KeyboardInput()
    renderer = ScreenRenderer(game)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE and game.state in (GameState.READY,
                                                                   GameState.GAME_OVER):
                    game.start()
                elif event.key == pygame.K_p:
                    if game.state is GameState.PLAYING:
                        game.pause(reason="player")
                    else:
                        game.resume()
                elif event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
            keyboard.handle_event(event)

        direction = keyboard.poll()
        if direction is not None:
            game.set_direction(direction)

        if game.state is GameState.PLAYING:
            for _ in range(ticker.update(dt)):
                game.step()
        else:
            # Don't bank time while paused or between rounds, or the snake
            # would lurch forward when play resumes.
            ticker.reset()

        renderer.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
