"""
Zoom Controller — Region-of-Interest cropping zoom
Zooms by cropping the frame and upscaling with interpolation.
Supports smooth animated transitions.
"""
import logging
from typing import Tuple, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ZoomController:
    """
    Digital zoom via region-of-interest (ROI) cropping.
    Supports smooth zoom transitions and pan across the zoomed region.
    """

    def __init__(self, frame_width: int, frame_height: int,
                 min_zoom: float = 1.0, max_zoom: float = 8.0,
                 default_zoom: float = 1.0):
        self.W = frame_width
        self.H = frame_height
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.current_zoom = default_zoom
        self.target_zoom = default_zoom

        # Pan position (normalized 0–1, center of zoom window)
        self.pan_x = 0.5
        self.pan_y = 0.5

        # Smooth animation
        self.smooth = True
        self._zoom_vel = 0.0
        self._pan_vel_x = 0.0
        self._pan_vel_y = 0.0

    @property
    def zoom_factor(self) -> float:
        return self.current_zoom

    def zoom_in(self, step: float = 0.5):
        self.target_zoom = min(self.max_zoom, self.target_zoom + step)

    def zoom_out(self, step: float = 0.5):
        self.target_zoom = max(self.min_zoom, self.target_zoom - step)

    def reset(self):
        self.target_zoom = 1.0
        self.pan_x = 0.5
        self.pan_y = 0.5

    def set_zoom(self, value: float):
        self.target_zoom = max(self.min_zoom, min(self.max_zoom, value))

    def pan(self, dx: float, dy: float):
        """Pan the zoom window by a normalized delta."""
        self.pan_x = max(0.0, min(1.0, self.pan_x + dx))
        self.pan_y = max(0.0, min(1.0, self.pan_y + dy))

    def update(self):
        """Call every frame to animate zoom/pan transitions."""
        if self.smooth:
            # Smooth interpolation
            self.current_zoom += (self.target_zoom - self.current_zoom) * 0.15
        else:
            self.current_zoom = self.target_zoom

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply current zoom/pan to a frame and return the cropped+resized frame.
        Returns the same shape as input (WxH).
        """
        if self.current_zoom <= 1.01:
            return frame

        z = self.current_zoom
        h, w = frame.shape[:2]

        # ROI size (how much of the original to keep after crop)
        roi_w = int(w / z)
        roi_h = int(h / z)

        # Center of ROI from pan position
        cx = int(self.pan_x * w)
        cy = int(self.pan_y * h)

        # Clamp ROI to frame bounds
        x1 = max(0, cx - roi_w // 2)
        y1 = max(0, cy - roi_h // 2)
        x2 = min(w, x1 + roi_w)
        y2 = min(h, y1 + roi_h)

        # Re-center if out of bounds
        if x2 - x1 < roi_w:
            x1 = max(0, x2 - roi_w)
        if y2 - y1 < roi_h:
            y1 = max(0, y2 - roi_h)

        # Crop
        cropped = frame[y1:y2, x1:x2]

        # Resize back to full frame size
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        return zoomed

    def get_roi_info(self) -> dict:
        """Return current ROI info for HUD overlay."""
        return {
            'zoom': round(self.current_zoom, 2),
            'pan_x': round(self.pan_x, 3),
            'pan_y': round(self.pan_y, 3),
            'roi_pct': round(100.0 / self.current_zoom, 1)
        }