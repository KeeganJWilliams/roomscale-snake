"""Common input interface.

Every controller - keyboard, FP2, anything later - turns its raw device
events into the same small set of Commands. The Engine consumes Commands
and never learns which source produced them.
"""

import time
from dataclasses import dataclass
from typing import Protocol, Union

from engine import Direction


def now_ns():
    """Monotonic timestamp used across the whole input path.

    One clock everywhere so Telemetry can subtract two stamps and get a
    real latency. Engine events use time.perf_counter_ns(), which is a
    different epoch - only compare stamps from the same clock.
    """
    return time.monotonic_ns()


@dataclass(frozen=True)
class Turn:
    """Steer the snake.

    t_recv_ns is when the sensor event that caused this turn arrived, and
    zone_key the 'aid.iid' it came from (empty for keyboard). Render logs
    the frame that draws the turn against t_recv_ns to get the
    sensor-to-projection latency for objective O3.
    """

    direction: Direction
    t_recv_ns: int = 0
    zone_key: str = ""


@dataclass(frozen=True)
class PlayerLost:
    """Nobody on the d-pad (or the sensor went away): pause."""

    t_recv_ns: int = 0
    zone_key: str = ""


@dataclass(frozen=True)
class PlayerFound:
    """Somebody is back on the d-pad: resume."""

    t_recv_ns: int = 0
    zone_key: str = ""


Command = Union[Turn, PlayerLost, PlayerFound]


class InputSource(Protocol):
    """What main.py needs from any controller."""

    def poll(self) -> list:
        """Return the Commands produced since the last call. Never blocks."""
        ...

    def close(self) -> None:
        """Release threads, sockets and log files."""
        ...
