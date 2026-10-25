class Grid:
    """The play-field: its size plus any blocked cells (registered furniture)."""

    def __init__(self, width, height, walls=()):
        if width < 1 or height < 1:
            raise ValueError("grid must be at least 1x1")
        self.width = width
        self.height = height
        self.walls = set(walls)
        for cell in self.walls:
            if not self.in_bounds(cell):
                raise ValueError(f"wall {cell} is outside the {width}x{height} grid")

    def in_bounds(self, cell):
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def is_blocked(self, cell):
        return not self.in_bounds(cell) or cell in self.walls

    def cells(self):
        for y in range(self.height):
            for x in range(self.width):
                yield (x, y)
