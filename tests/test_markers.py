import unittest

import cv2
import numpy as np

from objects import MarkerDetector, classify, label
from objects.camera import parse_source
from objects.generate_markers import render_marker
from objects.markers import (CALIBRATION, DICTIONARY_ID, GATE, KEY, PORTAL, PRINTABLE_IDS,
                             UNKNOWN, WALL)


class TestClassify(unittest.TestCase):
    def test_reserved_ranges(self):
        self.assertEqual(classify(2).kind, CALIBRATION)
        self.assertEqual(classify(15).kind, PORTAL)
        self.assertEqual(classify(20).kind, KEY)
        self.assertEqual(classify(39).kind, GATE)
        self.assertEqual(classify(44).kind, WALL)
        for unused in (4, 9):
            self.assertEqual(classify(unused).kind, UNKNOWN)

    def test_portal_pairs_share_a_group(self):
        self.assertEqual(classify(10).group, classify(11).group)
        self.assertNotEqual(classify(11).group, classify(12).group)

    def test_key_matches_gate(self):
        self.assertEqual(classify(21).group, classify(31).group)

    def test_labels(self):
        self.assertEqual(label(12), "portal 2A")
        self.assertEqual(label(13), "portal 2B")
        self.assertEqual(label(20), "key 1")
        self.assertEqual(label(0), "corner top left")

    def test_printable_ids_skip_calibration(self):
        self.assertNotIn(0, PRINTABLE_IDS)
        self.assertIn(10, PRINTABLE_IDS)
        self.assertIn(49, PRINTABLE_IDS)


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY_ID)
        self.detector = MarkerDetector()

    def test_detects_generated_markers_with_centers(self):
        # Two printable markers side by side on a white "wall".
        a = render_marker(self.dictionary, 10)
        b = render_marker(self.dictionary, 31)
        h, w = a.shape
        wall = np.full((h, 2 * w), 255, dtype=np.uint8)
        wall[:, :w] = a
        wall[:, w:] = b
        frame = cv2.cvtColor(wall, cv2.COLOR_GRAY2BGR)

        found = self.detector.detect(frame)
        self.assertEqual([d.id for d in found], [10, 31])
        # The black square is centered horizontally in each tile.
        self.assertAlmostEqual(found[0].center[0], w / 2, delta=3)
        self.assertAlmostEqual(found[1].center[0], w + w / 2, delta=3)
        self.assertEqual(found[1].kind.kind, GATE)

    def test_blank_frame_finds_nothing(self):
        self.assertEqual(self.detector.detect(np.full((200, 200), 255, np.uint8)), [])


class TestPrintablePdf(unittest.TestCase):
    def test_default_kit_pages_detect_every_marker(self):
        from collections import Counter

        from objects.generate_markers import DEFAULT_KIT, expand, render_pages

        ids = expand(DEFAULT_KIT)
        pages = render_pages(ids, size_in=3.1)
        detector = MarkerDetector()
        seen = Counter()
        for page in pages:
            frame = np.array(page.convert("L"))
            seen.update(d.id for d in detector.detect(frame))
        self.assertEqual(seen, Counter(ids))
        self.assertEqual(seen[30], 3)   # gates come 3 to an ID

    def test_pages_are_letter_size_with_six_pieces(self):
        from objects.generate_markers import DPI, page_grid, render_pages

        self.assertEqual(page_grid(3.1), (2, 3))
        pages = render_pages(list(range(10, 17)), size_in=3.1)
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0].size, (int(8.5 * DPI), int(11 * DPI)))

    def test_piece_is_the_requested_size(self):
        from objects.generate_markers import DPI, PIECE_BITS

        bit_px = round(3.1 * DPI / PIECE_BITS)
        self.assertAlmostEqual(bit_px * PIECE_BITS / DPI, 3.1, delta=0.01)

    def test_too_big_to_fit_is_rejected(self):
        from objects.generate_markers import page_grid

        with self.assertRaises(ValueError):
            page_grid(9.0)


class TestCameraSource(unittest.TestCase):
    def test_digits_become_index(self):
        self.assertEqual(parse_source("1"), 1)
        self.assertEqual(parse_source(0), 0)

    def test_urls_stay_strings(self):
        url = "rtsp://cam.local/stream"
        self.assertEqual(parse_source(url), url)


if __name__ == "__main__":
    unittest.main()
