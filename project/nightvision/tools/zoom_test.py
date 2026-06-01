"""
Test a single zoom level — output a few zoomed frames as images.
Useful for visually inspecting zoom behavior on laptop.
"""
import sys
import os
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    out_dir = "output/zoom"
    os.makedirs(out_dir, exist_ok=True)

    from camera.interface import CameraInterface
    from zoom.controller import ZoomController

    cam = CameraInterface(resolution=(640, 480), source='demo')
    z = ZoomController(640, 480, min_zoom=1.0, max_zoom=8.0)
    levels = [1.0, 2.0, 3.0, 4.0, 6.0, 8.0]

    for level in levels:
        z.set_zoom(level)
        for _ in range(20):  # let it animate
            z.update()
        frame = cam.read()
        zoomed = z.apply(frame)
        out_path = os.path.join(out_dir, f"zoom_{int(level*10):02d}.jpg")
        cv2.imwrite(out_path, zoomed)
        print(f"  → {out_path} (zoom={z.current_zoom:.2f}x)")

    cam.release()
    print(f"\nDone. Images in {out_dir}/")


if __name__ == '__main__':
    main()