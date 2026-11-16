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

Tests:

    python3 -m unittest
