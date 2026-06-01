"""
NightVision Goggles — Main Entry Point
Ties camera + LED + zoom + detection + HUD all together.
Run on Raspberry Pi or desktop (demo mode).
"""
import os
import sys
import time
import logging
import argparse
from typing import Optional

import cv2
import numpy as np

# Project imports
from camera.interface import CameraInterface
from led.controller import LEDController
from zoom.controller import ZoomController
from detection.yolo import ObjectDetector
from hud.engine import HUDEngine

# ── Config ───────────────────────────────────────────────────────────────────
import config as C

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description='NightVision Goggles')
    parser.add_argument('--demo', action='store_true', help='Force demo mode')
    parser.add_argument('--no-led', action='store_true', help='Disable LED controller')
    parser.add_argument('--no-detect', action='store_true', help='Disable object detection')
    parser.add_argument('--debug', action='store_true', help='Show FPS and timing debug')
    parser.add_argument('--save', metavar='PATH', help='Save output frames to directory')
    parser.add_argument('--rotate', type=int, default=0, help='Camera rotation (0/90/180/270)')
    return parser.parse_args()


class NightVisionSystem:
    """Main system orchestrator."""

    def __init__(self, args):
        self.args = args
        self.running = True
        self._prev_frame = None

        # Init sub-systems
        logger.info("Initializing NightVision System...")

        # Camera
        cam_source = 'demo' if args.demo else 'auto'
        self.camera = CameraInterface(
            resolution=C.CAMERA_RESOLUTION,
            framerate=C.CAMERA_FRAMERATE,
            rotation=args.rotate or C.CAMERA_ROTATION,
            source=cam_source,
        )

        # LEDs
        if args.no_led:
            self.led = None
            logger.info("LED: disabled via flag")
        else:
            self.led = LEDController(
                pins=C.LED_PINS,
                default_brightness=C.LED_DEFAULT_BRIGHTNESS,
            )
            self.led.on()

        # Zoom
        self.zoom = ZoomController(
            frame_width=C.CAMERA_RESOLUTION[0],
            frame_height=C.CAMERA_RESOLUTION[1],
            min_zoom=C.ZOOM_MIN,
            max_zoom=C.ZOOM_MAX,
            default_zoom=C.ZOOM_DEFAULT,
        )
        self.zoom.smooth = C.ZOOM_SMOOTH

        # Detection
        detect_enabled = not args.no_detect and C.DETECTION_ENABLED
        self.detector = ObjectDetector({**vars(C), 'DETECTION_ENABLED': detect_enabled})

        # HUD
        self.hud = HUDEngine(C.HUD_WIDTH, C.HUD_HEIGHT, vars(C))

        # Output dir
        self.save_dir = args.save
        if self.save_dir:
            os.makedirs(self.save_dir, exist_ok=True)
            logger.info(f"Saving frames to {self.save_dir}")

        self.frame_count = 0
        self._start_time = time.time()
        self._last_fps_time = time.time()
        self._fps = 0.0
        self._frame_times = []

        logger.info(f"System ready — Camera: {self.camera.source} | LEDs: {'ON' if self.led else 'N/A'} | Detection: {'ON' if detect_enabled else 'OFF'}")

    # ── Controls ───────────────────────────────────────────────────────────

    def handle_key(self, key: int):
        """Handle keyboard input."""
        if key == -1:
            return

        k = chr(key & 0xFF) if 0 <= key <= 255 else ''

        if k == C.KEY_QUIT or key == 27:  # ESC
            self.running = False

        elif k in (C.KEY_ZOOM_IN, '+'):
            self.zoom.zoom_in(C.ZOOM_STEP)
            logger.info(f"Zoom IN → {self.zoom.target_zoom:.1f}x")

        elif k in (C.KEY_ZOOM_OUT, '-'):
            self.zoom.zoom_out(C.ZOOM_STEP)
            logger.info(f"Zoom OUT → {self.zoom.target_zoom:.1f}x")

        elif k == C.KEY_ZOOM_RESET:
            self.zoom.reset()
            logger.info("Zoom RESET")

        elif k == C.KEY_LED_TOGGLE and self.led:
            state = self.led.toggle()
            logger.info(f"LED {'ON' if state else 'OFF'}")

        elif k == C.KEY_LED_FLASH and self.led:
            self.led.flash(0.2, 3)
            logger.info("LED flash")

        elif k == C.KEY_DETECTION_TOGGLE:
            self.detector.toggle()

        elif k == C.KEY_SCREENSHOT:
            self._screenshot()

    def _screenshot(self):
        """Save current frame."""
        if self.save_dir:
            path = os.path.join(self.save_dir, f"snap_{self.frame_count:06d}.jpg")
            # Screenshot is the HUD frame — capture it externally
            logger.info(f"Screenshot saved (use display callback)")

    # ── Main Loop ─────────────────────────────────────────────────────────

    def run(self):
        """Main processing loop."""
        window_name = "NightVision Goggles"

        while self.running:
            loop_start = time.perf_counter()

            # ── 1. Read frame from camera ─────────────────────────────────
            frame = self.camera.read()
            if frame is None:
                logger.warning("No frame received — retrying")
                time.sleep(0.1)
                continue

            # ── 2. Apply zoom ─────────────────────────────────────────────
            self.zoom.update()
            zoomed_frame = self.zoom.apply(frame)

            # ── 3. Run object detection ────────────────────────────────────
            detections = self.detector.detect(zoomed_frame, self._prev_frame)
            self._prev_frame = zoomed_frame.copy()

            # ── 4. Flash LEDs on detection ─────────────────────────────────
            if C.LED_FLASH_ON_DETECT and self.led and detections:
                self.led.flash(0.1, 1)

            # ── 5. Render HUD ─────────────────────────────────────────────
            fps = self._fps
            battery = self._read_battery()
            temp = self._read_temp()
            led_on = self.led._gpio_available and (hasattr(self.led, '_state') and self.led._state) if self.led else True

            hud_frame = self.hud.render(
                zoomed_frame,
                detections=detections,
                zoom_factor=self.zoom.current_zoom,
                fps=fps,
                battery=battery,
                temp_c=temp,
                led_on=led_on,
            )

            # ── 6. Show / save ────────────────────────────────────────────
            # cv2.imshow NOT used here — we're headless/cloud. Frames saved to disk.
            # To use with a real display, uncomment the line below on your Pi:
            # cv2.imshow(window_name, hud_frame)

            if self.save_dir:
                out_path = os.path.join(self.save_dir, f"frame_{self.frame_count:06d}.jpg")
                cv2.imwrite(out_path, hud_frame)

            # ── 7. FPS tracking ───────────────────────────────────────────
            self.frame_count += 1
            now = time.perf_counter()
            self._frame_times.append(now - loop_start)
            if len(self._frame_times) > 30:
                self._frame_times.pop(0)
            avg_frame_time = sum(self._frame_times) / len(self._frame_times)
            self._fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0

            # ── 8. Keyboard input (headless mode: skip) ─────────────────
            # On your Pi with a display connected, uncomment:
            # key = cv2.waitKey(1) & 0xFF
            # self.handle_key(key)
            # For headless demo, run for a fixed number of frames then exit
            if self.frame_count >= 60:  # ~2 seconds at 30fps
                self.running = False

            # ── 9. Debug overlay ─────────────────────────────────────────
            if self.args.debug and self.frame_count % 30 == 0:
                elapsed = time.time() - self._start_time
                logger.info(
                    f"Loop #{self.frame_count} | FPS: {self._fps:.1f} | "
                    f"Zoom: {self.zoom.current_zoom:.1f}x | "
                    f"Detections: {len(detections)} | "
                    f"Cam: {self.camera.source}"
                )

        self._cleanup()

    def _read_battery(self) -> float:
        """Simulate battery reading (replace with real GPIO reading)."""
        # TODO: connect to a ADC (e.g. ADS1115) for real battery voltage
        return 87.5

    def _read_temp(self) -> float:
        """Simulate temperature reading."""
        # TODO: connect to a DS18B20 or GPIO-based sensor
        return 42.3

    def _cleanup(self):
        """Release all resources."""
        logger.info("Shutting down...")
        if self.led:
            self.led.off()
            self.led.cleanup()
        self.camera.release()
        # cv2.destroyAllWindows() — only needed with display connected on Pi
        elapsed = time.time() - self._start_time
        logger.info(f"Done — {self.frame_count} frames in {elapsed:.1f}s | Avg FPS: {self.frame_count / elapsed:.1f}")


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    print("""
╔═══════════════════════════════════════════════╗
║      NIGHT VISION GOGGLES  v1.0               ║
║  ─────────────────────────────────────────    ║
║  Controls:                                    ║
║   [i / +]  Zoom in                           ║
║   [o / -]  Zoom out                          ║
║   [r]      Reset zoom                        ║
║   [l]      Toggle LEDs                       ║
║   [f]      LED flash                         ║
║   [d]      Toggle detection                   ║
║   [s]      Screenshot                        ║
║   [q / ESC] Quit                             ║
╚═══════════════════════════════════════════════╝
    """)

    system = NightVisionSystem(args)
    system.run()


if __name__ == '__main__':
    main()