"""Camera-to-grid calibration, the Layout builder, and the scan pipeline.

No camera needed: frames are synthetic images of a wall with markers,
seen through a known perspective tilt.
"""

import os
import unittest

import cv2
import numpy as np

from engine import Game
from objects.calibration import CORNER_CELLS, corner_targets
from objects.detector import MarkerDetector
from objects.layout_builder import build_layout
from objects.markers import DICTIONARY_ID
from objects.scanner import ScanError, analyze

W, H = 20, 15          # default grid
PX = 60                # pixels per cell in the flat "wall" image
DICTIONARY = cv2.aruco.getPredefinedDictionary(DICTIONARY_ID)


def paste_marker(img, marker_id, left, top, size):
    """Draw a marker's black square at grid-unit position (left, top)."""
    px = int(round(size * PX))
    marker = cv2.aruco.generateImageMarker(DICTIONARY, marker_id, px)
    x, y = int(round(left * PX)), int(round(top * PX))
    img[y:y + px, x:x + px] = marker


def wall_image(objects, corners=(0, 1, 2, 3)):
    """Flat white wall: projected corner markers plus paper markers.
    objects: {(x, y) cell: marker_id}, each drawn centered in its cell."""
    img = np.full((H * PX, W * PX), 255, dtype=np.uint8)
    for marker_id, (left, top, size) in corner_targets(W, H).items():
        if marker_id in corners:
            paste_marker(img, marker_id, left, top, size)
    for (x, y), marker_id in objects.items():
        paste_marker(img, marker_id, x + 0.15, y + 0.15, 0.7)
    return img


def camera_view(wall):
    """The wall as an angled camera sees it: keystoned, smaller, on a gray room."""
    h, w = wall.shape
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[180, 90], [1500, 40], [1560, 1010], [120, 960]])
    m = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(wall, m, (1700, 1080), borderValue=90)


class TestBuildLayout(unittest.TestCase):
    def build(self, placements, reserved=()):
        return build_layout(placements, W, H, reserved)

    def test_everything_in_its_place(self):
        layout, warnings = self.build([
            (10, (3, 3)), (11, (16, 11)),             # portal pair 1
            (20, (8, 2)),                              # key 1
            (30, (12, 5)), (30, (12, 6)), (30, (12, 7)),  # 3-cell gate 1
            (40, (1, 8)), (45, (1, 9)),                # walls
        ])
        self.assertEqual(warnings, [])
        self.assertEqual(layout.portals, (((3, 3), (16, 11)),))
        self.assertEqual(layout.keys, {(8, 2): 0})
        self.assertEqual(layout.gates, {(12, 5): 0, (12, 6): 0, (12, 7): 0})
        self.assertEqual(layout.walls, {(1, 8), (1, 9)})

    def test_portal_missing_partner_is_skipped(self):
        layout, warnings = self.build([(12, (3, 3))])
        self.assertEqual(layout.portals, ())
        self.assertIn("missing ID 13", warnings[0])

    def test_portal_with_extra_copy_is_skipped(self):
        layout, warnings = self.build([(10, (3, 3)), (10, (4, 4)), (11, (9, 9))])
        self.assertEqual(layout.portals, ())
        self.assertIn("extra copies", warnings[0])

    def test_two_markers_on_one_cell_are_both_skipped(self):
        layout, warnings = self.build([(40, (2, 2)), (41, (2, 2)), (42, (5, 5))])
        self.assertEqual(layout.walls, {(5, 5)})
        self.assertIn("more than one marker", warnings[0])

    def test_reserved_and_off_grid_cells_are_skipped(self):
        layout, warnings = self.build([(40, (10, 7)), (41, (25, 3))], reserved={(10, 7)})
        self.assertEqual(layout.walls, set())
        self.assertEqual(len(warnings), 2)

    def test_duplicate_key_keeps_one(self):
        layout, warnings = self.build([(21, (2, 2)), (21, (4, 4)), (31, (6, 6))])
        self.assertEqual(len(layout.keys), 1)
        self.assertIn("appears 2 times", warnings[0])

    def test_unmatched_keys_and_gates_load_with_a_warning(self):
        layout, warnings = self.build([(22, (2, 2)), (33, (4, 4))])
        self.assertEqual(layout.keys, {(2, 2): 2})
        self.assertEqual(layout.gates, {(4, 4): 3})
        self.assertEqual(len(warnings), 2)

    def test_calibration_ids_ignored_unknown_ids_warned(self):
        layout, warnings = self.build([(0, (0, 0)), (5, (3, 3))])
        self.assertEqual(layout.occupied_cells(), set())
        self.assertEqual(len(warnings), 1)
        self.assertIn("marker 5", warnings[0])

    def test_result_loads_into_the_game(self):
        game = Game(width=W, height=H)
        layout, _ = build_layout([(40, c) for c in game.start_cells()] + [(41, (2, 2))],
                                 W, H, reserved=game.start_cells())
        game.load_layout(layout)
        self.assertEqual(game.grid.walls, {(2, 2)})


class TestScanPipeline(unittest.TestCase):
    OBJECTS = {(4, 4): 10, (15, 10): 11, (7, 12): 20,
               (12, 3): 30, (12, 4): 30, (12, 5): 30, (6, 6): 44}

    def setUp(self):
        self.detector = MarkerDetector()

    def detections(self, wall, frames=5):
        found = self.detector.detect(camera_view(wall))
        return [found] * frames

    def test_markers_land_on_their_cells_through_a_tilted_camera(self):
        result = analyze(self.detections(wall_image(self.OBJECTS)), W, H)
        self.assertEqual(result.warnings, [])
        layout = result.layout
        self.assertEqual(layout.portals, (((4, 4), (15, 10)),))
        self.assertEqual(layout.keys, {(7, 12): 0})
        self.assertEqual(layout.gates, {(12, 3): 0, (12, 4): 0, (12, 5): 0})
        self.assertEqual(layout.walls, {(6, 6)})
        self.assertLess(result.calibration.rms_error_cells, 0.05)

    def test_marker_seen_in_one_frame_only_is_ignored(self):
        steady = self.detector.detect(camera_view(wall_image(self.OBJECTS)))
        glitch = self.detector.detect(camera_view(wall_image({**self.OBJECTS, (9, 9): 41})))
        result = analyze([glitch] + [steady] * 4, W, H)
        self.assertNotIn((9, 9), result.layout.walls)

    def test_missing_corner_is_a_clear_error(self):
        frames = self.detections(wall_image(self.OBJECTS, corners=(0, 1, 3)))
        with self.assertRaises(ScanError) as ctx:
            analyze(frames, W, H)
        self.assertIn("bottom right", str(ctx.exception))

    def test_marker_on_snake_start_is_skipped(self):
        game = Game(width=W, height=H)
        start = game.start_cells()[0]
        frames = self.detections(wall_image({start: 42}))
        result = analyze(frames, W, H, reserved=game.start_cells())
        self.assertEqual(result.layout.walls, set())
        self.assertIn("where the snake starts", result.warnings[0])

    def test_corner_blocks_are_reserved(self):
        # A paper marker inside a calibration corner block would be covered by
        # the projected corner marker; even if detected, it's rejected.
        result = analyze(self.detections(wall_image({})), W, H)
        placements_cell = (CORNER_CELLS - 1, CORNER_CELLS - 1)
        layout, warnings = build_layout([(40, placements_cell)], W, H,
                                        reserved={placements_cell})
        self.assertEqual(layout.walls, set())
        self.assertEqual(result.layout.occupied_cells(), set())


class TestCalibrationScreen(unittest.TestCase):
    """The pygame calibration screen and the calibration math agree on where
    the corner markers are: treat the screen itself as the camera image."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        cls.pygame = pygame

    @classmethod
    def tearDownClass(cls):
        cls.pygame.quit()

    def test_screen_pixels_map_back_to_the_right_cells(self):
        from render.screen import ScreenRenderer

        game = Game(width=W, height=H)
        renderer = ScreenRenderer(game)
        surface = self.pygame.Surface((1280, 800))
        renderer.draw_calibration(surface)
        frame = self.pygame.surfarray.array3d(surface).transpose(1, 0, 2)[:, :, ::-1].copy()

        result = analyze([MarkerDetector().detect(frame)], W, H)
        cell, left, top, _panel = renderer._layout(surface)
        for x, y in [(5, 5), (0, 7), (19, 14), (10, 0)]:
            center = (left + (x + 0.5) * cell, top + (y + 0.5) * cell)
            self.assertEqual(result.calibration.cell_at(center), (x, y))


class TestPlacementGrid(unittest.TestCase):
    """Cell lines and no-marker cells show between rounds when scanning is on."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        cls.pygame = pygame

    @classmethod
    def tearDownClass(cls):
        cls.pygame.quit()

    def render(self, placement_grid, playing=False):
        from render.screen import ScreenRenderer

        game = Game(width=W, height=H)
        if playing:
            game.start()
        renderer = ScreenRenderer(game)
        renderer.placement_grid = placement_grid
        surface = self.pygame.Surface((1280, 800))
        renderer.draw(surface)
        return surface, renderer._layout(surface)[:3]

    def test_lines_and_blocked_cells_shown_between_rounds(self):
        from render.screen import GRID_LINE

        surface, (cell, left, top) = self.render(True)
        line_px = (left + 5 * cell, top + 2 * cell + cell // 2)   # x=5 boundary, row 2
        self.assertEqual(tuple(surface.get_at(line_px))[:3], GRID_LINE)
        r, g, b, _ = surface.get_at((left + cell // 2, top + cell // 2))  # corner cell
        self.assertGreater(r, g + 20)

    def test_hidden_without_scanning_or_during_play(self):
        from render.screen import GRID_LINE

        for kwargs in ({"placement_grid": False}, {"placement_grid": True, "playing": True}):
            surface, (cell, left, top) = self.render(**kwargs)
            line_px = (left + 5 * cell, top + 2 * cell + cell // 2)
            self.assertNotEqual(tuple(surface.get_at(line_px))[:3], GRID_LINE, kwargs)


class TestStartCells(unittest.TestCase):
    def test_body_plus_one_ahead(self):
        game = Game(width=W, height=H)
        self.assertEqual(game.start_cells(), [(10, 7), (9, 7), (8, 7), (11, 7)])
        self.assertEqual(game.start_cells(lead=0), [(10, 7), (9, 7), (8, 7)])


if __name__ == "__main__":
    unittest.main()
