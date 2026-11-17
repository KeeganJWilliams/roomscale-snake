# roomscale-snake

Install (use opencv-python, NOT opencv-contrib-python; never install both,
and don't install regular pygame alongside pygame-ce):

    python3 -m pip install -r requirements.txt

Run the game:

    python3 main.py
    python3 main.py --demo-objects

ArUco marker tools (work on Windows, macOS, and Linux):

    python3 -m objects.list_cameras
    python3 -m objects.generate_markers
    python3 -m objects.detect_live --camera 1

Printable markers: `print/markers_3.1in.pdf` is ready to print (portals 10-15,
keys 20-23, gates 30-33 three each, walls 40-49). Print at **Actual size / 100%**,
not "Fit to page", on matte paper. Cut on the dashed lines and never into the
white border. Each piece is 3.1" to fit the 3.2" cells of the default 20x15 grid.
To make a different set or size:

    python3 -m objects.generate_markers --pdf print/markers_3.1in.pdf
    python3 -m objects.generate_markers --pdf out.pdf --size 3.1 --ids 30 31 --copies 4

Tests:

    python3 -m unittest
