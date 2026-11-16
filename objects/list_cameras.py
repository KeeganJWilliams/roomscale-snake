"""Find which camera index is which.

    python -m objects.list_cameras

Saves a test photo from each working camera (camera_0.jpg, camera_1.jpg, ...)
so you can open them and see which one is the ELP/USB camera.
"""

import cv2

from .camera import read_frame


def main(max_index=4):
    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            print(f"Index {index}: cannot open")
            continue
        frame = read_frame(cap)
        if frame is None:
            print(f"Index {index}: opened but no frames (permission problem or wrong device)")
        else:
            h, w = frame.shape[:2]
            cv2.imwrite(f"camera_{index}.jpg", frame)
            print(f"Index {index}: OK, {w}x{h}, saved camera_{index}.jpg")
        cap.release()


if __name__ == "__main__":
    main()
