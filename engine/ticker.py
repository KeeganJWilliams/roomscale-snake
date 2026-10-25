class Ticker:
    """Converts frame time into game ticks at a fixed snake speed.

    The render loop can run at any frame rate; the snake still moves at
    cells_per_second. Stepping is slower than key presses, so start slow.
    """

    def __init__(self, cells_per_second=3.0, max_ticks_per_update=5):
        self.cells_per_second = cells_per_second
        self.max_ticks_per_update = max_ticks_per_update
        self._accumulator = 0.0

    @property
    def cells_per_second(self):
        return self._cells_per_second

    @cells_per_second.setter
    def cells_per_second(self, value):
        if value <= 0:
            raise ValueError("cells_per_second must be positive")
        self._cells_per_second = value
        self.interval = 1.0 / value

    def update(self, dt):
        """Add dt seconds of elapsed time and return how many ticks are due.

        Capped so a long stall (window drag, slow device call) doesn't make
        the snake jump several cells at once.
        """
        self._accumulator += dt
        ticks = int(self._accumulator // self.interval)
        self._accumulator -= ticks * self.interval
        if ticks > self.max_ticks_per_update:
            ticks = self.max_ticks_per_update
            self._accumulator = 0.0
        return ticks

    def reset(self):
        self._accumulator = 0.0
