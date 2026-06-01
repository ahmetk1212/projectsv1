"""
Performance benchmark — measure FPS under different configurations.
"""
import sys
import os
import time
import argparse
import logging
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("bench")


def benchmark_resolution(W, H, frames=120, use_hud=True, use_detection=False, source='demo'):
    """Run benchmark at a given resolution and report FPS."""
    from camera.interface import CameraInterface
    from hud.engine import HUDEngine
    from detection.yolo import ObjectDetector
    import config as C

    C.HUD_WIDTH = W
    C.HUD_HEIGHT = H
    C.CAMERA_RESOLUTION = (W, H)

    cam = CameraInterface(resolution=(W, H), source=source)
    hud = HUDEngine(W, H, vars(C)) if use_hud else None
    det = ObjectDetector({**vars(C), 'DETECTION_ENABLED': use_detection,
                          'MODEL_DIR': '/nonexistent'}) if use_detection else None

    log.info(f"  Warming up... ({W}x{H}, hud={use_hud}, det={use_detection})")
    # Warm-up
    for _ in range(10):
        frame = cam.read()
        if hud:
            frame = hud.render(frame, zoom_factor=1.0, fps=30)
        if det:
            det.detect(frame)

    log.info(f"  Benchmarking {frames} frames...")
    t0 = time.time()
    for i in range(frames):
        frame = cam.read()
        if hud:
            frame = hud.render(frame, zoom_factor=1.0 + i * 0.01, fps=30)
        if det:
            det.detect(frame, None)
    elapsed = time.time() - t0
    fps = frames / elapsed
    cam.release()
    return fps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames', type=int, default=120)
    args = parser.parse_args()

    print("=" * 60)
    print("  NIGHT VISION GOGGLES — PERFORMANCE BENCHMARK")
    print("=" * 60)
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  NumPy:  {np.__version__}")
    print(f"  OpenCV: {__import__('cv2').__version__}")
    print("=" * 60)

    configs = [
        # (W, H, use_hud, use_detection, label)
        (320, 240, True, False, "320x240 + HUD"),
        (640, 480, True, False, "640x480 + HUD"),
        (640, 480, True, True,  "640x480 + HUD + Detection"),
        (1280, 720, True, False, "1280x720 + HUD"),
    ]

    print()
    print(f"  {'Configuration':<35} {'FPS':>8}  {'ms/frame':>10}")
    print("  " + "-" * 60)

    for W, H, hud, det, label in configs:
        try:
            fps = benchmark_resolution(W, H, args.frames, hud, det)
            ms = 1000 / fps
            print(f"  {label:<35} {fps:>8.1f}  {ms:>8.1f} ms")
        except Exception as e:
            print(f"  {label:<35}  ERROR: {e}")

    print()
    print("  Raspberry Pi 3A+ reference (typical):")
    print("    320x240 + HUD                  ~20-25 FPS")
    print("    640x480 + HUD                  ~12-15 FPS")
    print("    640x480 + HUD + YOLOv4-tiny    ~6-10 FPS")
    print("    1280x720 + HUD                 ~5-8 FPS")
    print("=" * 60)


if __name__ == '__main__':
    main()