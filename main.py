"""Room-Scale Snake.

Controls: arrow keys / WASD steer, SPACE starts or restarts,
P pauses, F11 toggles fullscreen, ESC quits.

Steering can come from the keyboard, from the Aqara FP2 floor d-pad, or
both at once:

    python main.py --input keyboard
    python main.py --input fp2
    python main.py --input fp2 --fake config/fp2_fake_script.json
    python main.py --input both

With --input fp2 the sensor runs on a background thread; if it is
unreachable the game pauses and keeps retrying rather than crashing.
"""

import argparse
import logging
import sys

import pygame

from engine import Game, GameState, Ticker
from input import PlayerFound, PlayerLost, Turn
from input.keyboard import KeyboardInput
from render.screen import ScreenRenderer

FPS = 60

log = logging.getLogger("main")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cols", type=int, default=20, help="grid width in cells")
    parser.add_argument("--rows", type=int, default=15, help="grid height in cells")
    parser.add_argument("--speed", type=float, default=3.0,
                        help="snake speed in cells per second (default 3)")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--input", choices=("keyboard", "fp2", "both"),
                        default="keyboard",
                        help="steering source (default keyboard, so the game "
                             "runs with no sensor present)")
    parser.add_argument("--fp2-config", default=None,
                        help="FP2 zone config (default config/fp2_zones.json)")
    parser.add_argument("--fake", metavar="SCRIPT",
                        help="replay a scripted FP2 event file instead of the sensor")
    parser.add_argument("--no-telemetry", action="store_true",
                        help="skip the FP2 zone-event CSV in telemetry/logs/")
    return parser.parse_args()


def build_fp2_source(args):
    """Create the FP2 input source. Raises ConfigError on a bad config."""
    from input.fp2 import Fp2Input
    from input.fp2.config import DEFAULT_PATH, load
    from input.fp2.__main__ import make_client_factory

    config = load(args.fp2_config or DEFAULT_PATH)
    telemetry = None
    if not args.no_telemetry:
        from telemetry import ZoneEventLog

        telemetry = ZoneEventLog(config.zones)
    return Fp2Input(config, client_factory=make_client_factory(args.fake),
                    telemetry=telemetry).start()


def build_sources(args):
    """Return (sources, keyboard). keyboard is None unless it is enabled."""
    sources, keyboard = [], None
    if args.input in ("keyboard", "both"):
        keyboard = KeyboardInput()
        sources.append(keyboard)
    if args.input in ("fp2", "both"):
        sources.append(build_fp2_source(args))
    return sources, keyboard


def apply_command(game, command):
    """Feed one input Command to the Engine."""
    if isinstance(command, Turn):
        # Reversing into itself is the Engine's rule to enforce, not the
        # adapter's, so just hand the direction over.
        game.set_direction(command.direction)
    elif isinstance(command, PlayerLost):
        log.info("player left the pad: pausing")
        game.pause(reason="player_lost")
    elif isinstance(command, PlayerFound):
        log.info("player back on the pad: resuming")
        game.resume()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        sources, keyboard = build_sources(args)
    except Exception as exc:
        # A bad zone config is a setup mistake worth failing fast on; a
        # sensor that merely cannot be reached is handled at runtime.
        print(f"input setup failed: {exc}", file=sys.stderr)
        return 2

    pygame.init()
    pygame.display.set_caption("Room-Scale Snake")
    flags = pygame.FULLSCREEN if args.fullscreen else pygame.RESIZABLE
    screen = pygame.display.set_mode((960, 760), flags)
    clock = pygame.time.Clock()

    game = Game(width=args.cols, height=args.rows)
    ticker = Ticker(cells_per_second=args.speed)
    renderer = ScreenRenderer(game)

    running = True
    try:
        while running:
            dt = clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE and game.state in (
                            GameState.READY, GameState.GAME_OVER):
                        game.start()
                    elif event.key == pygame.K_p:
                        if game.state is GameState.PLAYING:
                            game.pause(reason="player")
                        else:
                            game.resume()
                    elif event.key == pygame.K_F11:
                        pygame.display.toggle_fullscreen()
                if keyboard is not None:
                    keyboard.handle_event(event)

            for source in sources:
                for command in source.poll():
                    apply_command(game, command)

            if game.state is GameState.PLAYING:
                for _ in range(ticker.update(dt)):
                    game.step()
            else:
                # Don't bank time while paused or between rounds, or the snake
                # would lurch forward when play resumes.
                ticker.reset()

            renderer.draw(screen)
            pygame.display.flip()
    finally:
        for source in sources:
            source.close()
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
