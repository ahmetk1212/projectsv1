"""
Camera Interface — abstracts the camera source.
Supports: PiCamera2, picamera (legacy), OpenCV webcam (demo mode).
"""
import logging
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraInterface:
    """
    Unified camera interface with fallback to demo mode.
    """

    def __init__(self, resolution: tuple = (1280, 720),
                 framerate: int = 30, rotation: int = 0,
                 source: str = 'auto'):
        """
        source: 'auto' | 'picamera2' | 'picamera' | 'webcam' | 'demo'
        """
        self.W, self.H = resolution
        self.framerate = framerate
        self.rotation = rotation
        self.source = source
        self._camera = None
        self._demo_frame = 0
        self._is_open = False

        if source == 'demo':
            self._open_demo()
        elif source == 'webcam':
            self._open_webcam(0)
        elif source == 'auto':
            self._auto_detect()
        else:
            self._open_demo()

    def _auto_detect(self):
        """Try picamera2 → picamera → webcam → demo."""
        try:
            self._open_picamera2()
            return
        except Exception as e1:
            logger.warning(f"picamera2 failed: {e1}")

        try:
            self._open_picamera()
            return
        except Exception as e2:
            logger.warning(f"picamera failed: {e2}")

        try:
            self._open_webcam(0)
            return
        except Exception as e3:
            logger.warning(f"webcam failed: {e3}")

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

    def _open_picamera(self):
        import picamera
        self._camera = picamera.PiCamera()
        self._camera.resolution = (self.W, self.H)
        self._camera.framerate = self.framerate
        self._camera.rotation = self.rotation
        time.sleep(2)
        self._stream = picamera.array.PiRGBArray(self._camera)
        self._stream.seek(0)
        self.source = 'picamera'
        self._is_open = True
        logger.info("Camera: picamera (legacy)")

    def _open_webcam(self, index: int = 0):
        self._camera = cv2.VideoCapture(index)
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.W)
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.H)
        self._camera.set(cv2.CAP_PROP_FPS, self.framerate)
        if not self._camera.isOpened():
            raise RuntimeError("Webcam not available")
        self.source = 'webcam'
        self._is_open = True
        logger.info("Camera: webcam")

    def _open_demo(self):
        """Generate a synthetic night-vision-style demo frame."""
        self.source = 'demo'
        self._is_open = True
        logger.info("Camera: DEMO mode (synthetic frames)")

    def read(self) -> Optional[np.ndarray]:
        """
        Read one frame. Returns None if no frame available.
        Frame is always BGR (OpenCV convention).
        """
        frame = None

        if self.source == 'picamera2':
            frame = self._camera.capture_array()

        elif self.source == 'picamera':
            self._stream.truncate(0)
            self._stream.seek(0)
            self._camera.capture(self._stream, format='rgb', use_video_port=True)
            frame = self._stream.array

        elif self.source == 'webcam':
            ret, frame = self._camera.read()
            if not ret:
                return None

        elif self.source == 'demo':
            frame = self._generate_demo_frame()

        if frame is None:
            return None

        # Apply rotation
        if self.rotation and self.source != 'demo':
            if self.rotation == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif self.rotation == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif self.rotation == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Ensure BGR for OpenCV
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        return frame

    def _generate_demo_frame(self) -> np.ndarray:
        """Generate a synthetic night-vision style frame."""
        self._demo_frame += 1
        t = self._demo_frame / 30.0

        # Base: very dark green-black
        frame = np.zeros((self.H, self.W, 3), dtype=np.uint8)
        frame[:, :] = (5, 12, 5)

        # Add grid lines for depth
        for y in range(0, self.H, 40):
            alpha = 0.1 + 0.05 * np.sin(y * 0.01 + t)
            frame[y, :] = (int(8 * alpha), int(20 * alpha), int(8 * alpha))

        for x in range(0, self.W, 60):
            alpha = 0.08 + 0.04 * np.sin(x * 0.015 + t * 0.7)
            frame[:, x] = (int(6 * alpha), int(15 * alpha), int(6 * alpha))

        # Simulated "objects" — glowing shapes
        import math
        objects = [
            (self.W // 4 + int(100 * math.sin(t * 0.8)), self.H // 3 + int(50 * math.cos(t))),
            (self.W // 2 + int(80 * math.sin(t * 0.5 + 1)), self.H // 2 + int(60 * math.cos(t * 0.6))),
            (int(self.W * 0.75 + 120 * math.sin(t * 0.3)), int(self.H * 0.65 + 40 * math.cos(t * 0.9))),
        ]

        for ox, oy in objects:
            # Glow around object
            for r in range(60, 0, -3):
                alpha = (1 - r / 60) * 0.15
                cv2.circle(frame, (ox, oy), r, (int(20 * alpha), int(80 * alpha), int(20 * alpha)), -1)
            cv2.circle(frame, (ox, oy), 15, (15, 80, 15), -1)
            cv2.circle(frame, (ox, oy), 8, (20, 120, 20), -1)
            cv2.circle(frame, (ox, oy), 3, (40, 180, 40), -1)

        # Noise / grain
        noise = np.random.randint(0, 20, (self.H, self.W), dtype=np.uint8)
        frame[:, :, 1] = cv2.add(frame[:, :, 1], noise // 4)

        # Vignette
        kernel = np.ones((self.H, self.W), dtype=np.float32)
        cx, cy = self.W // 2, self.H // 2
        for y in range(self.H):
            for x in range(0, self.W, 4):
                dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                max_dist = math.sqrt(cx ** 2 + cy ** 2)
                kernel[y, x:x+4] = max(0.0, 1.0 - (dist / max_dist) * 0.7)
        frame = (frame * kernel[:, :, None]).astype(np.uint8)

        return frame

    def is_open(self) -> bool:
        return self._is_open

    def release(self):
        if self._camera is not None:
            if self.source == 'picamera2':
                self._camera.close()
            elif self.source == 'webcam':
                self._camera.release()
            elif self.source == 'picamera':
                self._camera.close()
            self._is_open = False
            logger.info("Camera released")