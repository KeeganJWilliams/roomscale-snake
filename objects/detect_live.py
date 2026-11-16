"""Live ArUco marker detection from a camera, for checking markers and lighting.

    python -m objects.detect_live                 # camera index 0
    python -m objects.detect_live --camera 1      # another USB camera
    python -m objects.detect_live --camera rtsp://user:pass@host/stream

Esc or q quits. Prints the detected markers whenever the set changes.
"""

import argparse

import cv2

from .camera import frame_size, open_camera, read_frame
from .detector import MarkerDetector, draw_detections
from .markers import label


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", default="0",
                        help="camera index or video URL (default 0)")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080,
                        help="requested resolution; drop to 1280x720 if 1080p fails")
    parser.add_argument("--fps", type=int, default=30)
    return parser.parse_args()


def main():
    args = parse_args()
    cap = open_camera(args.camera, args.width, args.height, args.fps)
    print("Actual resolution: {} x {}".format(*frame_size(cap)))
    detector = MarkerDetector()

    last_ids = None
    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                print("No frames from the camera. Check permissions and the camera "
                      "index (python -m objects.list_cameras).")
                break

            detections = detector.detect(frame)
            ids = [d.id for d in detections]
            if ids != last_ids:   # only print when the set of markers changes
                print("Detected:", ", ".join(f"{d.id} ({label(d.id)})" for d in detections)
                      or "none")
                last_ids = ids

            draw_detections(frame, detections)
            h, w = frame.shape[:2]
            preview = cv2.resize(frame, (960, int(960 * h / w)))
            cv2.imshow("ArUco detection (Esc to quit)", preview)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
