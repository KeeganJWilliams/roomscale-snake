from collections import deque


class Snake:
    """Snake body as a deque of cells, head first."""

    def __init__(self, head, direction, length=3):
        if length < 1:
            raise ValueError("snake length must be at least 1")
        self.direction = direction
        self._pending = None
        # Lay the body out behind the head, opposite to the heading.
        hx, hy = head
        self.body = deque(
            (hx - direction.dx * i, hy - direction.dy * i) for i in range(length)
        )

    @property
    def head(self):
        return self.body[0]

    @property
    def tail(self):
        return self.body[-1]

    def __len__(self):
        return len(self.body)

    def __contains__(self, cell):
        return cell in self.body

    def queue_turn(self, direction):
        """Request a turn for the next tick. Returns False if ignored.

        Checked against the direction the snake is actually moving, not an
        earlier queued turn, so two quick inputs in one tick can't reverse
        it into itself. The latest valid request in a tick wins.
        """
        if direction == self.direction or direction == self.direction.opposite:
            return False
        self._pending = direction
        return True

    def apply_turn(self):
        """Commit the queued turn. Returns True if the direction changed."""
        if self._pending is None:
            return False
        self.direction = self._pending
        self._pending = None
        return True

    def next_head(self):
        hx, hy = self.head
        return (hx + self.direction.dx, hy + self.direction.dy)

    def move(self, grow=False):
        self.body.appendleft(self.next_head())
        if not grow:
            self.body.pop()
