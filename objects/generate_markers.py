"""Generate ArUco markers (DICT_4X4_50) to print and cut, or to show on a screen.

    python -m objects.generate_markers --pdf print/markers_3.1in.pdf
    python -m objects.generate_markers --pdf out.pdf --size 3.1 --ids 30 31 --copies 4
    python -m objects.generate_markers            # PNGs in ./markers/ (phone/screen tests)

PDF mode lays out real-size markers on US Letter pages with dashed cut lines
and each marker's ID and role printed outside the cut line. Print at
"Actual size" / 100%, NOT "Fit to page", then measure one piece to check.

--size is the cut piece of paper, in inches. The black square is 75% of it:
the rest is the white border ("quiet zone") the detector needs, so cut on
the dashed line and never into the white. Use matte paper.

Without --ids, the PDF holds the default kit (DEFAULT_KIT below). With --ids,
each listed ID is printed --copies times.
"""

import argparse
import os

import cv2
import numpy as np

from .markers import DICTIONARY_ID, MAX_ID, PRINTABLE_IDS, label

# A 4x4 marker is 6 bits across (4 data + a 1-bit black edge). One bit of white
# on each side is the minimum quiet zone, so a piece is 8 bits across.
MARKER_BITS = 6
PIECE_BITS = MARKER_BITS + 2

# Default print kit. It matches what the renderer can tell apart: 3 portal
# colors and 4 key/gate colors (render/screen.py). Gates come 3 to an ID so
# one ID can block a 3-cell opening; any wall ID means "wall", so one each.
DEFAULT_KIT = (
    [(i, 1) for i in range(10, 16)]      # portal pairs 1-3
    + [(i, 1) for i in range(20, 24)]    # keys 1-4
    + [(i, 3) for i in range(30, 34)]    # gates 1-4, 3 cells each
    + [(i, 1) for i in range(40, 50)]    # 10 wall pieces
)

# Page layout (inches).
PAGE_W, PAGE_H = 8.5, 11.0
MARGIN = 0.35          # most printers can't print the outer ~0.25"
GAP = 0.3              # between pieces; labels sit in the gap below each piece
DPI = 300


def marker_image(dictionary, marker_id, bit_px):
    """Marker plus one-bit white border, as a uint8 array (black 0, white 255)."""
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, MARKER_BITS * bit_px)
    return cv2.copyMakeBorder(marker, bit_px, bit_px, bit_px, bit_px,
                              cv2.BORDER_CONSTANT, value=255)


def page_grid(size_in):
    """(columns, rows) of pieces that fit on one page."""
    cols = int((PAGE_W - 2 * MARGIN + GAP) // (size_in + GAP))
    rows = int((PAGE_H - 2 * MARGIN + GAP) // (size_in + GAP))
    if cols < 1 or rows < 1:
        raise ValueError(f"a {size_in}\" piece doesn't fit on a {PAGE_W}x{PAGE_H}\" page")
    return cols, rows


def expand(kit):
    return [marker_id for marker_id, copies in kit for _ in range(copies)]


def render_pages(ids, size_in, dpi=DPI):
    """Lay out markers on Letter pages. Returns black-and-white PIL images."""
    from PIL import Image, ImageDraw, ImageFont

    dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY_ID)
    # Whole pixels per bit keep every bit the same size; the rounding error
    # is under 1/300" per bit.
    bit_px = max(1, round(size_in * dpi / PIECE_BITS))
    piece_px = bit_px * PIECE_BITS
    gap_px, margin_px = round(GAP * dpi), round(MARGIN * dpi)
    cols, rows = page_grid(size_in)
    per_page = cols * rows
    font = ImageFont.load_default(size=max(10, round(0.11 * dpi)))
    page_w, page_h = round(PAGE_W * dpi), round(PAGE_H * dpi)
    # Center the block of pieces on the page.
    left = (page_w - (cols * piece_px + (cols - 1) * gap_px)) // 2
    top = max(margin_px, (page_h - (rows * piece_px + (rows - 1) * gap_px)) // 2)

    pages = []
    for start in range(0, len(ids), per_page):
        page = Image.new("1", (page_w, page_h), 1)
        draw = ImageDraw.Draw(page)
        for slot, marker_id in enumerate(ids[start:start + per_page]):
            row, col = divmod(slot, cols)
            x = left + col * (piece_px + gap_px)
            y = top + row * (piece_px + gap_px)
            piece = Image.fromarray(marker_image(dictionary, marker_id, bit_px)).convert("1")
            page.paste(piece, (x, y))
            _dashed_box(draw, x - 1, y - 1, x + piece_px, y + piece_px, dash=round(0.06 * dpi))
            draw.text((x, y + piece_px + round(0.04 * dpi)),
                      f"ID {marker_id}  {label(marker_id)}", fill=0, font=font)
        pages.append(page)
    return pages


def _dashed_box(draw, x0, y0, x1, y1, dash):
    """Cut line just outside the piece, so cutting on it keeps the full border."""
    for a, b, horizontal, fixed in ((x0, x1, True, y0), (x0, x1, True, y1),
                                    (y0, y1, False, x0), (y0, y1, False, x1)):
        for s in range(a, b, 2 * dash):
            e = min(s + dash, b)
            if horizontal:
                draw.line([(s, fixed), (e, fixed)], fill=0)
            else:
                draw.line([(fixed, s), (fixed, e)], fill=0)


def write_pdf(path, ids, size_in, dpi=DPI):
    pages = render_pages(ids, size_in, dpi)
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=dpi)
    return len(pages)


# ---- PNG mode: one marker per file, for showing on a phone or monitor ----

PNG_BIT_PX = 100
PNG_LABEL_PX = 80


def render_marker(dictionary, marker_id):
    """One marker with a white border and its ID/role underneath (uint8 array)."""
    piece = marker_image(dictionary, marker_id, PNG_BIT_PX)
    h, w = piece.shape
    canvas = np.full((h + PNG_LABEL_PX, w), 255, dtype=np.uint8)
    canvas[:h] = piece
    cv2.putText(canvas, f"ID {marker_id}  {label(marker_id)}", (PNG_BIT_PX, h + 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 3, cv2.LINE_AA)
    return canvas


def write_pngs(folder, ids):
    dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY_ID)
    os.makedirs(folder, exist_ok=True)
    for marker_id in ids:
        cv2.imwrite(os.path.join(folder, f"marker_{marker_id:02d}.png"),
                    render_marker(dictionary, marker_id))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", metavar="PATH", help="write a printable PDF instead of PNGs")
    parser.add_argument("--size", type=float, default=3.1,
                        help="PDF: cut piece size in inches (default 3.1)")
    parser.add_argument("--ids", type=int, nargs="+", help=f"marker IDs (0-{MAX_ID})")
    parser.add_argument("--copies", type=int, default=1,
                        help="PDF: copies of each --ids marker (default 1)")
    parser.add_argument("--out", default="markers", help="PNG output folder")
    args = parser.parse_args()

    if args.ids:
        bad = [i for i in args.ids if not 0 <= i <= MAX_ID]
        if bad:
            parser.error(f"IDs must be 0-{MAX_ID}: {bad}")
    if args.copies < 1:
        parser.error("--copies must be at least 1")

    if args.pdf:
        ids = (expand([(i, args.copies) for i in args.ids]) if args.ids
               else expand(DEFAULT_KIT))
        try:
            n_pages = write_pdf(args.pdf, ids, args.size)
        except ValueError as e:
            parser.error(str(e))
        black = args.size * MARKER_BITS / PIECE_BITS
        print(f"Saved {len(ids)} markers on {n_pages} pages to '{args.pdf}'.")
        print(f"Pieces are {args.size:g}\" (black square {black:.2f}\"). "
              "Print at Actual size / 100%.")
    else:
        ids = args.ids or PRINTABLE_IDS
        write_pngs(args.out, ids)
        print(f"Saved {len(ids)} markers to '{args.out}'.")


if __name__ == "__main__":
    main()
