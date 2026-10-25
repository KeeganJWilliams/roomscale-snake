from enum import Enum


class Direction(Enum):
    """The four steering commands every input adapter produces.

    Grid coordinates are (x, y) with (0, 0) in the top-left corner,
    so UP decreases y.
    """

    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def dx(self):
        return self.value[0]

    @property
    def dy(self):
        return self.value[1]

    @property
    def opposite(self):
        return Direction((-self.dx, -self.dy))
