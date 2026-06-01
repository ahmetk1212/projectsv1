"""
Camera Interface — abstracts the camera source.
Supports: PiCamera2, OpenCV webcam (laptop), demo (synthetic).
Demo frame is fully vectorized (numpy) for fast laptop testing.
"""
import logging
import time
import math
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraInterface:
    """
    Unified camera interface. Order: PiCamera2 → webcam → demo.
    Use --webcam to force laptop webcam. Use --demo to force synthetic.
    """

    def __init__(self, resolution: tuple = (640, 480),
                 framerate: int = 30, rotation: int = 0,
                 source: str = 'auto'):
        self.W, self.H = resolution
        self.framerate = framerate
        self.rotation = rotation
        self.source = source
        self._camera = None
        self._demo_frame = 0
        self._is_open = False
        self._frame_count = 0
        self._last_frame = None

        # Precompute vignette once
        self._vignette = self._make_vignette(self.W, self.H)

        if source == 'demo':
            self._open_demo()
        elif source == 'webcam':
            self._open_webcam(0)
        else:
            self._auto_detect()

    def _auto_detect(self):
        """Try PiCamera2 → webcam → demo."""
        try:
            self._open_picamera2()
            return
        except Exception as e1:
            logger.debug(f"picamera2 not available: {e1}")

        try:
            self._open_webcam(0)
            return
        except Exception as e2:
            logger.debug(f"webcam not available: {e2}")

        logger.info("No camera found — using DEMO mode")
        self._open_demo()

    def _open_picamera2(self):
        from picamera2 import Picamera2
        self._camera = Picamera2()
        self._camera.configure(self._camera.create_preview_configuration(
            main={"size": (self.W, self.H), "format": "RGB888"}))
        self._camera.start()
        self.source = 'picamera2'
        self._is_open = True
        logger.info("Camera: picamera2 (NoIR)")

    def _open_webcam(self, index: int = 0):
        """Open laptop webcam via OpenCV."""
        cap = cv2.VideoCapture(index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.H)
        cap.set(cv2.CAP_PROP_FPS, self.framerate)
        if not cap.isOpened():
            raise RuntimeError(f"Webcam index {index} not available")
        # Test read
        ok, test_frame = cap.read()
        if not ok or test_frame is None:
            cap.release()
            raise RuntimeError(f"Webcam index {index} returned no frames")
        # Use actual returned size if different
        actual_h, actual_w = test_frame.shape[:2]
        if (actual_w, actual_h) != (self.W, self.H):
            logger.info(f"Webcam actual resolution: {actual_w}x{actual_h}")
            self.W, self.H = actual_w, actual_h
            self._vignette = self._make_vignette(self.W, self.H)

        self._camera = cap
        self.source = 'webcam'
        self._is_open = True
        logger.info(f"Camera: webcam (index={index}, {self.W}x{self.H})")

    def _open_demo(self):
        """Use synthetic night-vision-style frames."""
        self.source = 'demo'
        self._is_open = True
        logger.info(f"Camera: DEMO mode (synthetic {self.W}x{self.H})")

    def read(self) -> Optional[np.ndarray]:
        """Read one frame (BGR). Returns None on failure."""
        frame = None

        if self.source == 'picamera2':
            frame = self._camera.capture_array()
            if frame is not None and len(frame.shape) == 3 and frame.shape[2] == 3:
                # picamera2 returns RGB; convert to BGR for OpenCV consistency
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        elif self.source == 'webcam':
            ok, frame = self._camera.read()
            if not ok or frame is None:
                return None

        elif self.source == 'demo':
            frame = self._generate_demo_frame()

        if frame is None:
            return None

        # Resize if needed
        if frame.shape[1] != self.W or frame.shape[0] != self.H:
            frame = cv2.resize(frame, (self.W, self.H), interpolation=cv2.INTER_AREA)

        # Apply rotation
        if self.rotation:
            if self.rotation == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif self.rotation == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif self.rotation == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        self._frame_count += 1
        self._last_frame = frame
        return frame

    def _make_vignette(self, w: int, h: int) -> np.ndarray:
        """Pre-compute a vignette mask (1.0 center → 0.0 corners). Vectorized."""
        y = np.linspace(-1, 1, h, dtype=np.float32)
        x = np.linspace(-1, 1, w, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        dist = np.sqrt(xx * xx + yy * yy)
        # corners at sqrt(2) ≈ 1.414, clamp at 1.0
        vignette = np.clip(1.0 - dist * 0.7, 0.0, 1.0)
        return vignette.astype(np.float32)

    def _generate_demo_frame(self) -> np.ndarray:
        """
        Vectorized synthetic night-vision frame. Fast enough for 60fps on a laptop.
        Simulates dark scene with moving glowing objects (people, animals, vehicles).
        """
        t = self._frame_count / max(1, self.framerate)
        h, w = self.H, self.W

        # ── Base: very dark green-black ──────────────────────────────
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (5, 14, 5)

        # ── Grid pattern for depth ───────────────────────────────────
        grid_y = np.arange(0, h, 40, dtype=np.float32)
        grid_x = np.arange(0, w, 60, dtype=np.float32)
        for gy in grid_y:
            alpha = 0.10 + 0.05 * np.sin(gy * 0.01 + t).item()
            color = (int(8 * alpha), int(20 * alpha), int(8 * alpha))
            iy = int(gy) % h
            frame[iy, :] = color

        # ── Moving "objects" — sinusoidal paths ──────────────────────
        objects = [
            (w // 4 + int(120 * np.sin(t * 0.8)),
             h // 3 + int(50 * np.cos(t))),
            (w // 2 + int(90 * np.sin(t * 0.5 + 1)),
             h // 2 + int(60 * np.cos(t * 0.6))),
            (int(w * 0.75 + 130 * np.sin(t * 0.3)),
             int(h * 0.65 + 40 * np.cos(t * 0.9))),
            (int(w * 0.3 + 60 * np.sin(t * 1.2 + 2)),
             int(h * 0.8 + 30 * np.cos(t * 1.4))),
        ]
        for ox, oy in objects:
            ox = int(np.clip(ox, 30, w - 30))
            oy = int(np.clip(oy, 30, h - 30))
            # Glow
            for r in range(60, 0, -3):
                alpha = (1 - r / 60) * 0.15
                color = (int(20 * alpha), int(80 * alpha), int(20 * alpha))
                cv2.circle(frame, (ox, oy), r, color, -1)
            # Body
            cv2.circle(frame, (ox, oy), 18, (15, 80, 15), -1)
            cv2.circle(frame, (ox, oy), 10, (25, 130, 25), -1)
            cv2.circle(frame, (ox, oy), 4, (50, 200, 50), -1)

        # ── Camera grain / noise ─────────────────────────────────────
        noise = np.random.randint(0, 25, (h, w, 3), dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise - 12, 0, 255).astype(np.uint8)

        # ── Vignette ────────────────────────────────────────────────
        vign = self._vignette
        frame_f = frame.astype(np.float32) * vign[..., None]
        frame = np.clip(frame_f, 0, 255).astype(np.uint8)

        return frame

    def is_open(self) -> bool:
        return self._is_open

    def release(self):
        if self._camera is not None:
            if self.source == 'picamera2':
                self._camera.close()
            elif self.source == 'webcam':
                self._camera.release()
            self._camera = None
            self._is_open = False
            logger.info("Camera released")