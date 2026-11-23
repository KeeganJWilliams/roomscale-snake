"""Guided tutorial: teaches the floor d-pad and the room's objects.

Snake itself needs no explaining; the controls do. Each step shows a prompt
and waits for the player to actually do it, so finishing the tutorial means
the player can steer. The snake only moves when a step lets it, and the
practice steps restart quietly on a crash, so there's no game over here.

Pure logic: no pygame, no sensor code. main.py feeds it input Commands and
frame time; the renderer draws `game` plus the current step's prompt. It
records how long each step took, wrong turns, retries, and steps a
facilitator skipped, for the user study's "unassisted within 2 minutes".
"""

import logging
import random
from dataclasses import dataclass, field

from engine import Direction, EventType, Game, GameState, Layout, Ticker
from input.base import PlayerFound, PlayerLost, Turn

log = logging.getLogger(__name__)

# The snake moves at the real game's speed throughout (main.py passes
# --speed), so the practice matches what players will actually play.
DEFAULT_SPEED = 0.85    # cells per second, when none is given (same as main.py)
MOVE_CELLS = 2          # cells the snake travels after each taught turn
CRUISE_CELLS = 4        # "keep going" step: this many cells...
CRUISE_LINGER = 1.5     # ...then the prompt stays up this long after the snake stops
READY_SECONDS = 2.0     # practice level shown frozen before it starts (and after a crash)
PRAISE_SECONDS = 2.0    # "Nice!" pause after a practice goal, to see where the snake ended up
DONE_SECONDS = 4.0      # how long the finish screen stays up

MIN_PRACTICE_SIZE = (16, 11)   # smallest grid the practice levels fit on

TURN_PROMPTS = {
    Direction.UP: ("Step FORWARD, toward the wall", "That turns the snake UP"),
    Direction.DOWN: ("Step BACK, away from the wall", "That turns the snake DOWN"),
    Direction.LEFT: ("Step LEFT", "That turns the snake LEFT"),
    Direction.RIGHT: ("Step RIGHT", "That turns the snake RIGHT"),
}
KEY_HINTS = {Direction.UP: "UP arrow", Direction.DOWN: "DOWN arrow",
             Direction.LEFT: "LEFT arrow", Direction.RIGHT: "RIGHT arrow"}


@dataclass(frozen=True)
class Step:
    name: str
    kind: str      # stand | turn | center | cruise | leave | return | portal | gate | done
    title: str
    subtitle: str = ""
    direction: Direction = None

    @property
    def target_zone(self):
        """The d-pad zone this step wants the player in, for the pad diagram."""
        if self.kind == "turn":
            return self.direction.name.lower()
        if self.kind in ("stand", "center", "cruise", "return"):
            return "center"
        return None


@dataclass
class StepRecord:
    name: str
    seconds: float = 0.0
    wrong_turns: int = 0
    retries: int = 0
    skipped: bool = False


def build_steps(has_pad, practice=True):
    """The step list. Pad-only steps (center, leave/return) are left out when
    steering with the keyboard alone, since a keyboard has no 'center'."""
    steps = []
    if has_pad:
        steps.append(Step("stand", "stand", "Stand on the CENTER square of the pad",
                          "Face the wall"))
    order = [Direction.UP, Direction.LEFT, Direction.DOWN, Direction.RIGHT]
    for i, direction in enumerate(order):
        title, subtitle = TURN_PROMPTS[direction]
        if not has_pad:
            title = f"Press the {KEY_HINTS[direction]}"
        steps.append(Step(f"turn_{direction.name.lower()}", "turn", title, subtitle,
                          direction))
        if has_pad and i < len(order) - 1:
            steps.append(Step(f"center_{i + 1}", "center", "Step back to the CENTER square",
                              "Do this after every turn"))
    if has_pad:
        steps.append(Step("cruise", "cruise", "Step back to the CENTER and stay there",
                          "The snake keeps going the same way"))
        steps.append(Step("leave", "leave", "Now step OFF the pad",
                          "The game pauses when nobody is on it"))
        steps.append(Step("return", "return", "Step back onto the CENTER square",
                          "The game picks up where it left off"))
    else:
        steps.append(Step("cruise", "cruise", "Let go: the snake keeps going",
                          "It only turns when you tell it to"))
    if practice:
        steps.append(Step("portal", "portal", "Steer into the PORTAL (the ring)",
                          "You come out of the other one"))
        steps.append(Step("gate", "gate", "Grab the KEY, then go through its GATE",
                          "A locked gate is a wall. Its key opens it"))
    steps.append(Step("done", "done", "You're ready!"))
    return steps


class Tutorial:
    """Runs the tutorial. Call handle() with each input Command and
    update(dt) once per frame; draw `game` and `step`."""

    def __init__(self, width=20, height=15, has_pad=False, pad_zones=None,
                 speed=DEFAULT_SPEED):
        self.width, self.height = width, height
        self.speed = speed
        self.has_pad = has_pad
        self.pad_zones = pad_zones or (lambda: None)
        min_w, min_h = MIN_PRACTICE_SIZE
        practice = width >= min_w and height >= min_h
        if not practice:
            log.warning("grid %dx%d is too small for the practice levels; skipping them",
                        width, height)
        self.steps = build_steps(has_pad, practice)
        self.records = []
        self.index = -1
        self.elapsed = 0.0
        self.completion_seconds = None   # time to reach the finish screen
        self.finished = False
        self.aborted = False
        self.hint = ""
        self.lost = False

        self.game = self._new_game()
        self._ticker = Ticker(speed)
        self._moves_left = 0
        self._hold = 0.0        # practice frozen for a moment (get ready, or praise)
        self._done_timer = 0.0
        self._goal = False
        self._advance()

    # --- public state --------------------------------------------------------

    @property
    def step(self):
        return self.steps[self.index]

    @property
    def progress(self):
        """(current step number, number of steps), not counting the finish."""
        return min(self.index + 1, len(self.steps) - 1), len(self.steps) - 1

    @property
    def assisted(self):
        return any(r.skipped for r in self.records)

    # --- input ---------------------------------------------------------------

    def handle(self, command):
        if self.finished:
            return
        step = self.step
        if isinstance(command, PlayerLost):
            self.lost = True
            if step.kind == "leave":
                self._complete()
            else:
                self.hint = "Step back onto the pad to continue"
        elif isinstance(command, PlayerFound):
            self.lost = False
            self.hint = ""
            if step.kind == "return":
                self._complete()
        elif isinstance(command, Turn):
            self._handle_turn(command.direction)

    def _handle_turn(self, direction):
        step = self.step
        if step.kind == "turn":
            if self._moves_left or self.lost:
                return   # already showing this turn
            if direction is step.direction:
                self._start_turn(direction)
            else:
                self._record.wrong_turns += 1
                self.hint = f"That was {direction.name}. {step.title}"
        elif step.kind in ("portal", "gate") and not self._goal:
            self.game.set_direction(direction)

    def skip(self):
        """Facilitator skips the current step. Logged as assisted."""
        if self.finished:
            return
        step = self.step
        if step.kind == "done":
            self._finish()
            return
        self._record.skipped = True
        if step.kind == "turn" and not self._moves_left:
            self._start_turn(step.direction)   # still show the move, keep the snake in sync
        elif step.kind != "turn":
            if step.kind in ("leave", "return"):
                self.lost = False
            self._complete()

    def abort(self):
        """Player or facilitator quit the tutorial early."""
        if not self.finished:
            self.aborted = True
            self._finish()

    # --- time ----------------------------------------------------------------

    def update(self, dt):
        if self.finished:
            return
        self.elapsed += dt
        self._record.seconds += dt
        step = self.step

        if step.kind == "done":
            self._done_timer += dt
            if self._done_timer >= DONE_SECONDS:
                self._finish()
            return
        if self.lost:
            self._ticker.reset()
            return

        zones = self.pad_zones() if self.has_pad else None
        on_center = zones is None or set(zones) == {"center"}

        if step.kind in ("stand", "center"):
            if on_center:
                self._complete()
        elif step.kind == "turn":
            self._run_moves(dt)
        elif step.kind == "cruise":
            if self._hold:
                self._hold = max(0.0, self._hold - dt)
                if not self._hold:
                    self._complete()
            elif on_center:
                self.hint = ""
                self._run_moves(dt)
            else:
                self.hint = "Stay on the CENTER square"
                self._ticker.reset()
        elif step.kind in ("portal", "gate"):
            self._run_practice(dt)

    def _run_moves(self, dt):
        if not self._moves_left:
            return
        for _ in range(self._ticker.update(dt)):
            self.game.step()
            self._moves_left -= 1
            if not self._moves_left:
                if self.step.kind == "cruise":
                    self._hold = CRUISE_LINGER   # leave time to read the prompt
                else:
                    self._complete()
                return

    def _run_practice(self, dt):
        if self._hold:
            self._hold = max(0.0, self._hold - dt)
            if not self._hold:
                if self._goal:
                    self._complete()
                else:
                    self.hint = ""   # "Get ready..." / crash hint has been read
            return
        for _ in range(self._ticker.update(dt)):
            self.game.step()
            if self.step.kind == "gate" and self.game.snake.head[0] > self._gate_x:
                self._goal = True
            if self._goal:
                self.hint = "Nice!"
                self._hold = PRAISE_SECONDS
                return
            if self.game.state is GameState.GAME_OVER:
                self._record.retries += 1
                self.hint = ("That gate is locked. Grab the KEY first!"
                             if self._crash == "gate" else "Ouch! Try again.")
                self._setup_practice(self.step.kind)
                return

    # --- steps ---------------------------------------------------------------

    def _start_turn(self, direction):
        self.hint = ""
        self.game.set_direction(direction)
        self._moves_left = MOVE_CELLS

    def _complete(self):
        record = self._record
        log.info("tutorial step %s done in %.1fs%s", record.name, record.seconds,
                 " (skipped)" if record.skipped else "")
        self._advance()

    def _advance(self):
        self.index += 1
        step = self.step
        self._record = StepRecord(step.name)
        self.records.append(self._record)
        self.hint = ""
        self._moves_left = 0
        self._hold = 0.0
        self._ticker.reset()
        if step.kind == "cruise":
            head_x = self.game.snake.head[0]
            self._moves_left = max(1, min(CRUISE_CELLS, self.width - head_x - 2))
        elif step.kind in ("portal", "gate"):
            self._setup_practice(step.kind)
            self.hint = "Get ready..."
        elif step.kind == "done":
            self.completion_seconds = self.elapsed
            minutes, seconds = divmod(int(round(self.elapsed)), 60)
            self.steps[self.index] = Step("done", "done", "You're ready!",
                                          f"Tutorial finished in {minutes}:{seconds:02d}")

    def _finish(self):
        self.finished = True
        if self.completion_seconds is None:
            self.completion_seconds = self.elapsed
        log.info("tutorial %s after %.1fs%s",
                 "aborted" if self.aborted else "finished", self.elapsed,
                 " (assisted)" if self.assisted else "")

    # --- levels --------------------------------------------------------------

    def _new_game(self, layout=None, direction=Direction.RIGHT):
        game = Game(width=self.width, height=self.height, layout=layout,
                    start_direction=direction, rng=random.Random(0))
        game.start()
        game.food = None   # nothing to chase: keep the focus on the lesson
        return game

    def _setup_practice(self, kind):
        """(Re)build a practice level. The snake always starts in the middle."""
        w, h = self.width, self.height
        cx, cy = w // 2, h // 2
        self._goal = False
        self._crash = None
        self._hold = READY_SECONDS   # show the level frozen before it starts
        self._ticker.reset()
        if kind == "portal":
            # Entrance up and to the right, so reaching it takes a turn (on
            # 20x15: 3 right, 3 up). Exit lower left, far from the entrance,
            # with room ahead whichever way the snake comes out.
            entry = (min(cx + 3, w - 3), max(1, cy - 3))
            exit_ = (max(1, cx - 6), min(h - 2, cy + 3))
            self.game = self._new_game(Layout(portals=[(entry, exit_)]))
            self.game.events.subscribe(self._on_portal, EventType.PORTAL_USED)
        else:
            # A wall splits the board; its only opening is a 3-cell gate. The
            # snake starts heading UP; the key is up and one cell right, so
            # grabbing it takes a turn (on 20x15: up 3, right 1), then the
            # player steers down and right through the gate.
            self._gate_x = min(cx + 4, w - 3)
            gate_rows = range(cy - 1, cy + 2)
            walls = {(self._gate_x, y) for y in range(h) if y not in gate_rows}
            gates = {(self._gate_x, y): 0 for y in gate_rows}
            layout = Layout(walls=walls, keys={(cx + 1, max(1, cy - 3)): 0}, gates=gates)
            self.game = self._new_game(layout, direction=Direction.UP)
        self.game.events.subscribe(self._on_collision, EventType.COLLISION)

    def _on_portal(self, event):
        self._goal = True

    def _on_collision(self, event):
        self._crash = event.data.get("kind")
