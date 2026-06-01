"""
Webcam Preview — open laptop webcam + HUD in a window. No recording, no detection.
Good for visual testing before deployment.
"""
import sys
import os
import time
import argparse
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cam', type=int, default=0)
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int, default=480)
    parser.add_argument('--rotate', type=int, default=0, choices=[0, 90, 180, 270])
    parser.add_argument('--demo', action='store_true', help='Use demo frames')
    parser.add_argument('--duration', type=int, default=0)
    parser.add_argument('--save', metavar='DIR', help='Save snapshots to dir')
    parser.add_argument('--fullscreen', action='store_true')
    args = parser.parse_args()

    from camera.interface import CameraInterface
    from hud.engine import HUDEngine
    import config as C
    C.CAMERA_RESOLUTION = (args.width, args.height)
    C.HUD_WIDTH = args.width
    C.HUD_HEIGHT = args.height

    source = 'demo' if args.demo else 'webcam'
    cam = CameraInterface(resolution=(args.width, args.height),
                          rotation=args.rotate, source=source,
                          auto_gain=C.CAMERA_AUTO_GAIN,
                          min_mean=C.CAMERA_MIN_MEAN,
                          max_gain=C.CAMERA_GAIN_MAX,
                          warmup_frames=C.CAMERA_WARMUP_FRAMES,
                          dark_warn_threshold=C.CAMERA_DARK_WARN_THRESHOLD)
    if not args.demo and cam.source == 'demo':
        print("⚠ Webcam not found, falling back to demo mode")
    print(f"Camera: {cam.source} @ {cam.W}x{cam.H}")

    hud = HUDEngine(cam.W, cam.H, vars(C))

    win = "Webcam Preview"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    if args.fullscreen:
        cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.resizeWindow(win, cam.W, cam.H)

    if args.save:
        os.makedirs(args.save, exist_ok=True)

    end_time = (time.time() + args.duration) if args.duration > 0 else None
    print("Press 'q' to quit, 's' to save frame")

    frame_count = 0
    fps = 30
    try:
        while True:
            t0 = time.time()
            frame = cam.read()
            if frame is None:
                continue

            out = hud.render(frame, zoom_factor=1.0, fps=fps,
                             battery=80, temp_c=40, led_on=True)
            cv2.imshow(win, out)

            if end_time and time.time() >= end_time:
                break

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('s') and args.save:
                path = os.path.join(args.save, f"preview_{frame_count:06d}.jpg")
                cv2.imwrite(path, out)
                print(f"  → saved {path}")
            frame_count += 1
            dt = time.time() - t0
            fps = 0.9 * fps + 0.1 * (1 / max(dt, 0.001))  # EMA
    except KeyboardInterrupt:
        pass
    finally:
        cam.release()
        cv2.destroyAllWindows()
        print(f"\nCaptured {frame_count} frames, avg FPS: {fps:.1f}")


if __name__ == '__main__':
    main()