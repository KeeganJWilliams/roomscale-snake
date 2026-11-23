"""Turn detected markers (ID + grid cell) into an engine Layout.

One marker = one cell: the cell under the marker's center. Problems never
raise; the offending marker is skipped and a warning explains why, so the
facilitator can fix the wall and rescan while everything else still loads.
"""

from collections import defaultdict

from engine import Layout

from .markers import CALIBRATION, GATE, KEY, PORTAL, UNKNOWN, WALL, classify, label


def build_layout(placements, width, height, reserved=()):
    """Build a Layout from markers.

    placements: iterable of (marker_id, (x, y)) — duplicates are fine.
    reserved:   cells nothing may occupy (the snake's starting cells).
    Returns (Layout, warnings) where warnings is a list of strings.
    """
    warnings = []
    reserved = set(reserved)

    # 1. Drop markers that can't be placed at all.
    by_cell = defaultdict(set)
    for marker_id, cell in set((int(i), tuple(c)) for i, c in placements):
        kind = classify(marker_id).kind
        if kind == CALIBRATION:
            continue   # projected by the game, not a game object
        if kind == UNKNOWN:
            warnings.append(f"marker {marker_id} isn't a game object ID; ignored")
            continue
        x, y = cell
        if not (0 <= x < width and 0 <= y < height):
            warnings.append(f"{label(marker_id)} (ID {marker_id}) is off the grid; ignored")
            continue
        if cell in reserved:
            warnings.append(f"{label(marker_id)} (ID {marker_id}) at {cell} is where "
                            "the snake starts; move it")
            continue
        by_cell[cell].add(marker_id)

    # 2. One object per cell.
    placed = []   # (marker_id, cell)
    for cell, ids in sorted(by_cell.items()):
        if len(ids) > 1:
            names = ", ".join(f"ID {i}" for i in sorted(ids))
            warnings.append(f"cell {cell} has more than one marker ({names}); ignored")
            continue
        placed.append((ids.pop(), cell))

    cells_of = defaultdict(list)
    for marker_id, cell in placed:
        cells_of[marker_id].append(cell)

    walls, portals, keys, gates = set(), [], {}, {}

    # 3. Walls: any number of any wall ID.
    for marker_id, cells in cells_of.items():
        if classify(marker_id).kind == WALL:
            walls.update(cells)

    # 4. Portals: exactly one of each ID in a pair.
    pairs = defaultdict(dict)
    for marker_id, cells in cells_of.items():
        kind = classify(marker_id)
        if kind.kind == PORTAL:
            pairs[kind.group][marker_id] = cells
    for group, members in sorted(pairs.items()):
        a, b = 10 + 2 * group, 11 + 2 * group
        name = f"portal pair {group + 1} (IDs {a}/{b})"
        if any(len(cells) > 1 for cells in members.values()):
            warnings.append(f"{name} has extra copies; each ID may appear once. Pair ignored")
        elif len(members) < 2:
            have = next(iter(members))
            warnings.append(f"{name} is missing ID {b if have == a else a}; pair ignored")
        else:
            portals.append((members[a][0], members[b][0]))

    # 5. Keys: one per ID. Gates: any number per ID.
    for marker_id, cells in sorted(cells_of.items()):
        kind = classify(marker_id)
        if kind.kind == KEY:
            if len(cells) > 1:
                warnings.append(f"{label(marker_id)} (ID {marker_id}) appears "
                                f"{len(cells)} times; using one at {cells[0]}")
            keys[cells[0]] = kind.group
        elif kind.kind == GATE:
            for cell in cells:
                gates[cell] = kind.group

    key_ids, gate_ids = set(keys.values()), set(gates.values())
    for gid in sorted(gate_ids - key_ids):
        warnings.append(f"gate {gid + 1} has no key (ID {20 + gid}), so it never opens")
    for kid in sorted(key_ids - gate_ids):
        warnings.append(f"key {kid + 1} has no gate (ID {30 + kid}) to open")

    return Layout(walls=walls, portals=portals, keys=keys, gates=gates), warnings


def summarize(layout):
    """One-line description, e.g. '2 portal pairs, 1 key, 3 gate cells, 4 walls'."""
    def n(count, word):
        return f"{count} {word}{'' if count == 1 else 's'}"
    return ", ".join([n(len(layout.portals), "portal pair"), n(len(layout.keys), "key"),
                      n(len(layout.gates), "gate cell"), n(len(layout.walls), "wall")])
