from dataclasses import dataclass, field


@dataclass(frozen=True)
class Layout:
    """Everything placed on the grid for a round, besides the snake and food.

    This is the hand-off point from the Objects module: marker detection
    builds a Layout, and the game loads it between rounds so the map stays
    frozen while a round is being played.

    walls:   cells that end the game on contact (furniture, wall markers).
    portals: pairs of cells. Entering one puts the snake's head on the other.
    keys:    {cell: id}. Driving over a key collects it and unlocks every
             gate with the same id.
    gates:   {cell: id}. A locked gate ends the game on contact; once its
             key is collected it becomes open floor.
    """

    walls: frozenset = frozenset()
    portals: tuple = ()
    keys: dict = field(default_factory=dict)
    gates: dict = field(default_factory=dict)

    def __post_init__(self):
        # Normalize so callers can pass lists/sets and the Layout stays hashable-ish.
        object.__setattr__(self, "walls", frozenset(self.walls))
        object.__setattr__(self, "portals", tuple(tuple(p) for p in self.portals))
        object.__setattr__(self, "keys", dict(self.keys))
        object.__setattr__(self, "gates", dict(self.gates))

    def portal_links(self):
        """{entry_cell: exit_cell} for both directions of every pair."""
        links = {}
        for a, b in self.portals:
            links[a] = b
            links[b] = a
        return links

    def occupied_cells(self):
        cells = set(self.walls) | set(self.keys) | set(self.gates)
        for pair in self.portals:
            cells.update(pair)
        return cells

    def validate(self, width, height):
        """Raise ValueError if the layout doesn't fit a width x height grid."""
        seen = {}

        def claim(cell, what):
            x, y = cell
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(f"{what} {cell} is outside the {width}x{height} grid")
            if cell in seen:
                raise ValueError(f"{what} {cell} overlaps {seen[cell]}")
            seen[cell] = what

        for cell in self.walls:
            claim(cell, "wall")
        for pair in self.portals:
            if len(pair) != 2:
                raise ValueError(f"portal {pair} must be a pair of two cells")
            for cell in pair:
                claim(cell, "portal")
        for cell in self.keys:
            claim(cell, "key")
        for cell in self.gates:
            claim(cell, "gate")
