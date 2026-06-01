"""
Quick test runner — run all module tests on laptop without hardware.
"""
import sys
import os
import time
import logging
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(message)s',
                    datefmt='%H:%M:%S')
log = logging.getLogger("tests")


def test_zoom():
    """Test zoom controller: in/out/reset/pan."""
    log.info("Test: ZoomController")
    from zoom.controller import ZoomController
    z = ZoomController(640, 480, min_zoom=1.0, max_zoom=4.0)
    assert z.zoom_factor == 1.0
    z.zoom_in(0.5)
    z.zoom_in(0.5)
    z.zoom_in(0.5)
    for _ in range(50):  # let it animate
        z.update()
    assert z.current_zoom > 1.5, f"expected >1.5, got {z.current_zoom}"
    z.zoom_out(2.0)
    for _ in range(50):
        z.update()
    assert z.current_zoom < z.target_zoom + 0.1

    # Apply to a real frame
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    out = z.apply(frame)
    assert out.shape == frame.shape
    log.info(f"  ✓ zoom levels: min=1.0, current={z.current_zoom:.2f}, max=4.0")
    log.info(f"  ✓ apply() preserves shape {out.shape}")


def test_hud():
    """Test HUD engine renders without errors."""
    log.info("Test: HUDEngine")
    from hud.engine import HUDEngine
    import config as C
    hud = HUDEngine(640, 480, vars(C))
    frame = np.zeros((480, 640, 3), dtype=np.uint8) + 30
    out = hud.render(frame,
                     detections=[{'label': 'person', 'confidence': 0.85,
                                  'bbox': (200, 200, 100, 150)}],
                     zoom_factor=2.0, fps=28.5, battery=75, temp_c=42, led_on=True)
    assert out.shape == (480, 640, 3)
    log.info(f"  ✓ HUD render shape={out.shape}")
    # Save sample
    os.makedirs("output/tests", exist_ok=True)
    cv2.imwrite("output/tests/hud_sample.jpg", out)
    log.info("  → output/tests/hud_sample.jpg")


def test_camera_demo():
    """Test synthetic frame generation speed."""
    log.info("Test: CameraInterface (demo mode)")
    from camera.interface import CameraInterface
    cam = CameraInterface(resolution=(640, 480), source='demo')
    t0 = time.time()
    for _ in range(60):
        frame = cam.read()
        assert frame is not None and frame.shape == (480, 640, 3)
    elapsed = time.time() - t0
    fps = 60 / elapsed
    log.info(f"  ✓ 60 frames in {elapsed:.2f}s = {fps:.1f} FPS")
    cam.release()


def test_detection_fallback():
    """Test motion-based fallback detection."""
    log.info("Test: ObjectDetector (fallback motion detection)")
    from detection.yolo import ObjectDetector
    import config as C
    det = ObjectDetector({**vars(C), 'MODEL_DIR': '/nonexistent'})

    # Two frames with motion
    f1 = np.zeros((480, 640, 3), dtype=np.uint8)
    f2 = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(f2, (320, 240), 60, (200, 200, 200), -1)
    out = det.detect(f2, f1)
    log.info(f"  ✓ detected {len(out)} motion regions (expecting >=1)")
    assert len(out) >= 1


def test_led_controller_simulation():
    """Test LED controller logic without GPIO."""
    log.info("Test: LEDController (simulation)")
    from led.controller import LEDController
    led = LEDController(pins=[17, 27, 22])
    assert led._gpio_available is False  # No RPi here
    led.on()  # should not raise
    led.off()
    led.set_brightness(50)
    state = led.toggle()
    log.info(f"  ✓ simulated on/off/toggle (state={state})")


def test_config_values():
    """Test that all config values are sane."""
    log.info("Test: config sanity")
    import config as C
    assert C.CAMERA_RESOLUTION[0] > 0 and C.CAMERA_RESOLUTION[1] > 0
    assert C.ZOOM_MIN >= 1.0
    assert C.ZOOM_MAX > C.ZOOM_MIN
    assert 0 <= C.LED_DEFAULT_BRIGHTNESS <= 100
    log.info(f"  ✓ cam={C.CAMERA_RESOLUTION}, zoom={C.ZOOM_MIN}-{C.ZOOM_MAX}, "
             f"led_brightness={C.LED_DEFAULT_BRIGHTNESS}%")


def main():
    print("=" * 50)
    print("  NIGHT VISION GOGGLES — LAPTOP TEST SUITE")
    print("=" * 50)

    tests = [
        test_config_values,
        test_zoom,
        test_hud,
        test_camera_demo,
        test_detection_fallback,
        test_led_controller_simulation,
    ]

    passed = 0
    failed = 0
    t0 = time.time()
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            log.error(f"  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()

    elapsed = time.time() - t0
    print()
    print("=" * 50)
    print(f"  Result: {passed} passed, {failed} failed ({elapsed:.1f}s)")
    print("=" * 50)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())