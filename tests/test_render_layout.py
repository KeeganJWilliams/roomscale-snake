"""Play-area and d-pad placement.

Pure geometry, so these run without a display or a font.
"""

import unittest

import pygame

from render.screen import DPAD_MIN_PX, HUD_HEIGHT, compute_layout

COLS, ROWS = 20, 15


def play_rect(width, height, cols=COLS, rows=ROWS):
    cell, left, top, _ = compute_layout(width, height, cols, rows)
    return pygame.Rect(left, top, cell * cols, cell * rows)


class TestPlayAreaIsUnchanged(unittest.TestCase):
    """The d-pad goes in dead space; it never costs the play area a pixel."""

    def test_cell_size_matches_the_no_dpad_calculation(self):
        for width, height in [(1280, 760), (960, 760), (1920, 1080),
                              (1024, 768), (800, 900), (1600, 900)]:
            with self.subTest(size=(width, height)):
                cell, _, _, _ = compute_layout(width, height, COLS, ROWS)
                expected = min(width // COLS, (height - HUD_HEIGHT) // ROWS)
                self.assertEqual(cell, expected)

    def test_widening_the_window_does_not_shrink_the_play_area(self):
        # 960x760 had no dead space; 1280x760 adds the d-pad panel and the
        # play area must come out exactly the same size.
        before = play_rect(960, 760)
        after = play_rect(1280, 760)
        self.assertEqual((before.width, before.height), (960, 720))
        self.assertEqual(after.size, before.size)


class TestPanelPlacement(unittest.TestCase):
    def test_wide_window_puts_the_pad_beside_the_grid(self):
        cell, left, top, panel = compute_layout(1280, 760, COLS, ROWS)
        self.assertIsNotNone(panel)
        self.assertEqual(left, 0, "grid shifts off the panel")
        self.assertEqual(panel.left, cell * COLS)
        self.assertEqual(panel.width, 1280 - cell * COLS)

    def test_tall_window_puts_the_pad_below_the_grid(self):
        cell, left, top, panel = compute_layout(800, 900, COLS, ROWS)
        self.assertIsNotNone(panel)
        self.assertEqual(top, HUD_HEIGHT, "grid pushed up")
        self.assertEqual(panel.top, HUD_HEIGHT + cell * ROWS)

    def test_no_dead_space_means_no_panel_and_the_old_centred_layout(self):
        cell, left, top, panel = compute_layout(960, 760, COLS, ROWS)
        self.assertIsNone(panel)
        self.assertEqual(left, (960 - cell * COLS) // 2)
        self.assertEqual(top, HUD_HEIGHT + (760 - HUD_HEIGHT - cell * ROWS) // 2)

    def test_a_sliver_of_dead_space_is_refused_rather_than_drawn_tiny(self):
        # 1024x768 leaves 64px beside the grid: too narrow to be legible.
        _, _, _, panel = compute_layout(1024, 768, COLS, ROWS)
        self.assertIsNone(panel)

    def test_panel_never_overlaps_the_play_area_or_the_hud(self):
        for width, height in [(1280, 760), (1920, 1080), (800, 900),
                              (1440, 760), (700, 1200)]:
            with self.subTest(size=(width, height)):
                cell, left, top, panel = compute_layout(width, height, COLS, ROWS)
                if panel is None:
                    continue
                grid = pygame.Rect(left, top, cell * COLS, cell * ROWS)
                self.assertFalse(panel.colliderect(grid), "panel overlaps play area")
                self.assertGreaterEqual(panel.top, HUD_HEIGHT, "panel covers the HUD")
                self.assertGreaterEqual(min(panel.width, panel.height), 1)

    def test_panel_is_big_enough_to_draw_when_present(self):
        for width, height in [(1280, 760), (1920, 1080), (800, 900)]:
            with self.subTest(size=(width, height)):
                _, _, _, panel = compute_layout(width, height, COLS, ROWS)
                self.assertGreaterEqual(max(panel.width, panel.height), DPAD_MIN_PX)

    def test_tiny_window_still_produces_a_usable_layout(self):
        cell, left, top, panel = compute_layout(120, 100, COLS, ROWS)
        self.assertGreaterEqual(cell, 1)
        self.assertGreaterEqual(left, 0)
        self.assertGreaterEqual(top, HUD_HEIGHT)
        self.assertIsNone(panel)


if __name__ == "__main__":
    unittest.main()
