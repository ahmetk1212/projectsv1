"""
NightVision Goggles — Main Entry Point
Default: laptop webcam + on-screen HUD (cv2.imshow)
Modes: --demo, --webcam, --pi (Raspberry Pi full), --headless
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

import config as C

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description='NightVision Goggles (laptop mode)')
    p.add_argument('--demo', action='store_true',
                   help='Force synthetic demo frames (no hardware needed)')
    p.add_argument('--webcam', type=int, default=None, metavar='IDX',
                   help='Use laptop webcam (default index 0)')
    p.add_argument('--pi', action='store_true',
                   help='Force Raspberry Pi + IR LED mode')
    p.add_argument('--no-led', action='store_true', help='Disable LED controller')
    p.add_argument('--no-detect', action='store_true', help='Disable object detection')
    p.add_argument('--headless', action='store_true',
                   help='No display — just save frames to ./output/')
    p.add_argument('--save', metavar='DIR', help='Save output frames to directory')
    p.add_argument('--rotate', type=int, default=0, choices=[0, 90, 180, 270])
    p.add_argument('--record', metavar='PATH',
                   help='Record output to a video file (.mp4/.avi)')
    p.add_argument('--duration', type=int, default=0,
                   help='Run for N seconds then quit (0 = forever)')
    p.add_argument('--fullscreen', action='store_true', help='Fullscreen window')
    p.add_argument('--debug', action='store_true', help='Verbose FPS logging')
    return p.parse_args()


class NightVisionSystem:
    def __init__(self, args):
        self.args = args
        self.running = True
        self.paused = False
        self.show_help = False
        self._prev_frame = None
        self._frame_count = 0
        self._start_time = time.time()
        self._last_fps = 0.0
        self._loop_times = []
        self._detection_history = []

        # ── Determine source ─────────────────────────────────────
        if args.demo:
            source = 'demo'
        elif args.webcam is not None:
            source = 'webcam'
        elif args.pi:
            source = 'auto'  # picamera2 first
        else:
            source = 'auto'  # webcam first on laptop

        # ── Camera ───────────────────────────────────────────────
        self.camera = CameraInterface(
            resolution=C.CAMERA_RESOLUTION,
            framerate=C.CAMERA_FRAMERATE,
            rotation=args.rotate,
            source=source,
        )
        # Update HUD to match actual resolution
        C.HUD_WIDTH = self.camera.W
        C.HUD_HEIGHT = self.camera.H

        # ── LEDs (only if --pi or explicitly enabled) ────────────
        self.led = None
        if not args.no_led and (args.pi or self.camera.source == 'picamera2'):
            self.led = LEDController(pins=C.LED_PINS,
                                      default_brightness=C.LED_DEFAULT_BRIGHTNESS)
            self.led.on()

        # ── Zoom ─────────────────────────────────────────────────
        self.zoom = ZoomController(
            self.camera.W, self.camera.H,
            min_zoom=C.ZOOM_MIN, max_zoom=C.ZOOM_MAX,
            default_zoom=C.ZOOM_DEFAULT,
        )
        self.zoom.smooth = C.ZOOM_SMOOTH

        # ── Detection ────────────────────────────────────────────
        detect_enabled = (not args.no_detect) and C.DETECTION_ENABLED
        self.detector = ObjectDetector({
            **vars(C),
            'DETECTION_ENABLED': detect_enabled,
            'MODEL_DIR': os.path.join(os.path.dirname(__file__), C.MODEL_DIR),
        })

        # ── HUD ──────────────────────────────────────────────────
        self.hud = HUDEngine(self.camera.W, self.camera.H, vars(C))

        # ── Save dir ─────────────────────────────────────────────
        self.save_dir = args.save
        if self.save_dir:
            os.makedirs(self.save_dir, exist_ok=True)

        # ── Video writer ─────────────────────────────────────────
        self.video_writer = None
        if args.record:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(
                args.record, fourcc, C.CAMERA_FRAMERATE,
                (self.camera.W, self.camera.H)
            )
            if self.video_writer.isOpened():
                logger.info(f"Recording to {args.record}")
            else:
                logger.warning(f"Could not open video writer: {args.record}")
                self.video_writer = None

        # ── Display window ───────────────────────────────────────
        self.window_name = "NightVision Goggles"
        if not args.headless:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            if args.fullscreen:
                cv2.setWindowProperty(self.window_name,
                                      cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN)
            cv2.resizeWindow(self.window_name, self.camera.W, self.camera.H)

        # ── Duration timer ───────────────────────────────────────
        self._end_time = (time.time() + args.duration) if args.duration > 0 else None

        logger.info(
            f"Ready | cam={self.camera.source} "
            f"| {self.camera.W}x{self.camera.H}@{C.CAMERA_FRAMERATE} "
            f"| led={'ON' if self.led else 'OFF'} "
            f"| detect={'ON' if detect_enabled else 'OFF'}"
        )

    # ── Controls ─────────────────────────────────────────────────────────

    def handle_key(self, key: int):
        if key == -1:
            return

        if key == C.KEY_QUIT or key == 27:  # ESC
            self.running = False

        elif key == C.KEY_ZOOM_IN:
            self.zoom.zoom_in(C.ZOOM_STEP)

        elif key == C.KEY_ZOOM_OUT:
            self.zoom.zoom_out(C.ZOOM_STEP)

        elif key == C.KEY_ZOOM_RESET:
            self.zoom.reset()

        elif key == C.KEY_LED_TOGGLE and self.led:
            self.led.toggle()

        elif key == C.KEY_LED_FLASH and self.led:
            self.led.flash(0.2, 3)

        elif key == C.KEY_DETECTION_TOGGLE:
            self.detector.toggle()

        elif key == C.KEY_SCREENSHOT:
            self._screenshot()

        elif key == C.KEY_PAUSE:
            self.paused = not self.paused
            logger.info(f"{'PAUSED' if self.paused else 'RESUMED'}")

        elif key == C.KEY_HELP:
            self.show_help = not self.show_help

    def _screenshot(self):
        if not hasattr(self, '_last_hud_frame') or self._last_hud_frame is None:
            return
        if self.save_dir:
            path = os.path.join(self.save_dir, f"snap_{self._frame_count:06d}.jpg")
        else:
            os.makedirs("screenshots", exist_ok=True)
            path = os.path.join("screenshots", f"snap_{int(time.time())}.jpg")
        cv2.imwrite(path, self._last_hud_frame)
        logger.info(f"📸 Screenshot → {path}")

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        self._print_welcome()

        while self.running:
            loop_start = time.perf_counter()

            # Duration check
            if self._end_time and time.time() >= self._end_time:
                logger.info("Duration reached, exiting")
                self.running = False
                break

            if self.paused:
                cv2.waitKey(100)
                continue

            # ── 1. Read frame ─────────────────────────────────────
            frame = self.camera.read()
            if frame is None:
                logger.warning("No frame — retrying")
                time.sleep(0.05)
                continue

            # ── 2. Apply zoom ─────────────────────────────────────
            self.zoom.update()
            zoomed = self.zoom.apply(frame)

            # ── 3. Detect (skip every N frames for perf) ────────
            detections = []
            if self.detector.enabled and self._frame_count % 2 == 0:
                detections = self.detector.detect(zoomed, self._prev_frame)
            self._prev_frame = zoomed.copy()

            # ── 4. LED flash on detection ─────────────────────────
            if C.LED_FLASH_ON_DETECT and self.led and detections:
                self.led.flash(0.1, 1)

            # ── 5. HUD ────────────────────────────────────────────
            led_state = bool(self.led and getattr(self.led, '_state', True))
            hud_frame = self.hud.render(
                zoomed,
                detections=detections,
                zoom_factor=self.zoom.current_zoom,
                fps=self._last_fps,
                battery=self._read_battery(),
                temp_c=self._read_temp(),
                led_on=led_state,
            )

            # Help overlay
            if self.show_help:
                hud_frame = self._draw_help(hud_frame)

            self._last_hud_frame = hud_frame

            # ── 6. Display / record / save ───────────────────────
            if not self.args.headless:
                cv2.imshow(self.window_name, hud_frame)
            if self.video_writer:
                self.video_writer.write(hud_frame)
            if self.save_dir:
                out_path = os.path.join(self.save_dir, f"frame_{self._frame_count:06d}.jpg")
                cv2.imwrite(out_path, hud_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            # ── 7. FPS tracking ──────────────────────────────────
            self._frame_count += 1
            now = time.perf_counter()
            self._loop_times.append(now - loop_start)
            if len(self._loop_times) > 30:
                self._loop_times.pop(0)
            avg_loop = sum(self._loop_times) / len(self._loop_times)
            self._last_fps = 1.0 / avg_loop if avg_loop > 0 else 0

            if self.args.debug and self._frame_count % 30 == 0:
                logger.info(f"FPS: {self._last_fps:.1f} | frame {self._frame_count}")

            # ── 8. Keyboard ───────────────────────────────────────
            if not self.args.headless:
                # waitKey(1) = ~30fps; use higher for slow CPU
                wait_ms = max(1, int(1000 / C.CAMERA_FRAMERATE) - int(avg_loop * 1000))
                key = cv2.waitKey(wait_ms) & 0xFF
                self.handle_key(key)

        self._cleanup()

    def _draw_help(self, frame):
        """Help overlay."""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (40, 40), (w - 40, h - 40), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        help_text = [
            "NIGHT VISION GOGGLES — KEYS",
            "",
            "  i / +    Zoom in",
            "  o / -    Zoom out",
            "  r        Reset zoom",
            "  l        Toggle IR LEDs",
            "  f        LED flash",
            "  d        Toggle detection",
            "  s        Screenshot",
            "  SPACE    Pause/resume",
            "  h        Toggle this help",
            "  q / ESC  Quit",
            "",
            f"  Camera:  {self.camera.source}  {self.camera.W}x{self.camera.H}",
            f"  FPS:     {self._last_fps:.1f}",
            f"  Zoom:    {self.zoom.current_zoom:.1f}x",
            f"  Detect:  {'ON' if self.detector.enabled else 'OFF'}",
        ]
        y = 80
        for line in help_text:
            color = (0, 255, 255) if y == 80 else (200, 200, 200)
            cv2.putText(frame, line, (60, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, color, 1)
            y += 22
        return frame

    def _read_battery(self) -> float:
        """Simulated. On Pi, read from ADC (e.g. ADS1115)."""
        return 87.5

    def _read_temp(self) -> float:
        """Simulated. On Pi, read from DS18B20."""
        return 42.3

    def _print_welcome(self):
        if not self.args.headless:
            print("""
╔═══════════════════════════════════════════════╗
║      NIGHT VISION GOGGLES  v1.0               ║
║  ─────────────────────────────────────────    ║
║  Keys:                                        ║
║   [i / +]  Zoom in                           ║
║   [o / -]  Zoom out                          ║
║   [r]      Reset zoom                        ║
║   [l]      Toggle LEDs                       ║
║   [f]      LED flash                         ║
║   [d]      Toggle detection                   ║
║   [s]      Screenshot                        ║
║   [SPACE]  Pause                             ║
║   [h]      Help                              ║
║   [q]      Quit                              ║
╚═══════════════════════════════════════════════╝
            """)

    def _cleanup(self):
        logger.info("Shutting down...")
        if self.led:
            self.led.off()
            self.led.cleanup()
        self.camera.release()
        if self.video_writer:
            self.video_writer.release()
        if not self.args.headless:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass
        elapsed = time.time() - self._start_time
        logger.info(f"Done — {self._frame_count} frames in {elapsed:.1f}s "
                   f"| Avg FPS: {self._frame_count / elapsed:.1f}")


def main():
    args = parse_args()
    system = NightVisionSystem(args)
    try:
        system.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        system._cleanup()


if __name__ == '__main__':
    main()