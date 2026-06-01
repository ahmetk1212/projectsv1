"""
HUD Engine — JARVIS-style overlay renderer
Draws all sci-fi HUD elements on top of the camera feed.
"""
import math
import time
import logging
from datetime import datetime
from typing import Optional, List, Tuple

import numpy as np
import cv2

logger = logging.getLogger(__name__)


class HUDEngine:
    """
    Renders a sci-fi HUD overlay (JARVIS / Iron Man style) on a camera feed.
    All elements are drawn with glowing effects and animated where appropriate.
    """

    def __init__(self, width: int, height: int, config: dict):
        self.W = width
        self.H = height
        self.cfg = config
        self.start_time = time.time()
        self.frame_count = 0
        self._font_main = cv2.FONT_HERSHEY_DUPLEX
        self._font_thin = cv2.FONT_HERSHEY_SIMPLEX
        self._scan_y = 0
        self._scan_dir = 1

        # Pre-compute corners for drawing
        self._cx = self.W // 2
        self._cy = self.H // 2
        self._frame_start = time.time()

    # ── Drawing helpers ────────────────────────────────────────────────────

    def _glow_text(self, canvas, text, pos, font, scale, color, thickness=1, glow=3):
        """Draw text with a glowing effect."""
        x, y = pos
        for g in range(glow, 0, -1):
            alpha = int(255 * (g / glow) * 0.15)
            cv2.putText(canvas, text, (x, y), font, scale,
                       (color[0], color[1], color[2], alpha), thickness + 1)
        cv2.putText(canvas, text, (x, y), font, scale, color, thickness)
        return cv2.getTextSize(text, font, scale, thickness)[0]

    def _glow_rect(self, canvas, pt1, pt2, color, thickness=1, glow=2, corner_radius=0):
        """Draw a rectangle with glowing edges."""
        if glow > 0:
            for g in range(glow, 0, -1):
                c = tuple(max(0, v - 20 * g) for v in color)
                if corner_radius > 0:
                    self._rounded_rect(canvas, pt1, pt2, corner_radius, c, -1)
                else:
                    cv2.rectangle(canvas, pt1, pt2, c, -1)
        if corner_radius > 0:
            self._rounded_rect(canvas, pt1, pt2, corner_radius, color, thickness)
        else:
            cv2.rectangle(canvas, pt1, pt2, color, thickness)

    def _rounded_rect(self, canvas, pt1, pt2, radius, color, thickness=1):
        """Draw a rounded rectangle."""
        x1, y1 = pt1
        x2, y2 = pt2
        cv2.line(canvas, (x1 + radius, y1), (x2 - radius, y1), color, thickness)
        cv2.line(canvas, (x2, y1 + radius), (x2, y2 - radius), color, thickness)
        cv2.line(canvas, (x2 - radius, y2), (x1 + radius, y2), color, thickness)
        cv2.line(canvas, (x1, y2 - radius), (x1, y1 + radius), color, thickness)
        cv2.ellipse(canvas, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness)
        cv2.ellipse(canvas, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness)
        cv2.ellipse(canvas, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness)
        cv2.ellipse(canvas, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness)

    def _hexagon(self, canvas, center, size, color, thickness=1, filled=False):
        """Draw a hexagon around a point."""
        cx, cy = center
        points = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            x = int(cx + size * math.cos(angle))
            y = int(cy + size * math.sin(angle))
            points.append((x, y))
        pts = np.array(points, np.int32).reshape((-1, 1, 2))
        if filled:
            cv2.fillPoly(canvas, [pts], color)
        else:
            cv2.polylines(canvas, [pts], True, color, thickness)
        return points

    def _loading_bar(self, canvas, x, y, w, h, progress, color, glow=3):
        """Draw a segmented loading bar."""
        segments = 20
        seg_w = w // segments
        for i in range(segments):
            filled = (i / segments) <= progress
            sx = x + i * seg_w
            c = color if filled else (color[0] // 4, color[1] // 4, color[2] // 4)
            cv2.rectangle(canvas, (sx, y), (sx + seg_w - 1, y + h), c, -1)
            if glow > 0 and filled:
                for g in range(glow, 0, -1):
                    cv2.rectangle(canvas, (sx, y), (sx + seg_w - 1, y + h),
                                  tuple(max(0, v - 30 * g) for v in color), 1)

    def _draw_bracket(self, canvas, x, y, w, h, color, thickness=2):
        """Draw corner brackets (like target locks)."""
        b_len = min(w, h) // 5
        # top-left
        cv2.line(canvas, (x, y + b_len), (x, y), color, thickness)
        cv2.line(canvas, (x, y), (x + b_len, y), color, thickness)
        # top-right
        cv2.line(canvas, (x + w - b_len, y), (x + w, y), color, thickness)
        cv2.line(canvas, (x + w, y), (x + w, y + b_len), color, thickness)
        # bottom-left
        cv2.line(canvas, (x, y + h - b_len), (x, y + h), color, thickness)
        cv2.line(canvas, (x, y + h), (x + b_len, y + h), color, thickness)
        # bottom-right
        cv2.line(canvas, (x + w - b_len, y + h), (x + w, y + h), color, thickness)
        cv2.line(canvas, (x + w, y + h - b_len), (x + w, y + h), color, thickness)

    def _draw_arc(self, canvas, center, radius, start_angle, end_angle, color, thickness=2):
        """Draw an arc segment."""
        cx, cy = center
        axes = (radius, radius)
        cv2.ellipse(canvas, (cx, cy), axes, 0, start_angle, end_angle, color, thickness)

    # ── Full HUD render ────────────────────────────────────────────────────

    def render(self, frame: np.ndarray, detections: List[dict] = None,
               zoom_factor: float = 1.0, fps: float = 30.0,
               battery: float = 100.0, temp_c: float = 45.0,
               led_on: bool = True) -> np.ndarray:
        """
        Main entry point — draw HUD on top of `frame`.
        Returns the HUD-overlaid frame (same shape as input).
        """
        self.frame_count += 1
        elapsed = time.time() - self.start_time
        pulse = abs(math.sin(elapsed * math.pi * self.cfg.get('HUD_PULSE_RATE', 1.5)))
        deg = elapsed * 10  # rotating element

        # Darken camera feed slightly for HUD contrast
        alpha = self.cfg.get('HUD_CAMERA_FEED_ALPHA', 0.60)
        if alpha < 1.0:
            canvas = cv2.convertScaleAbs(frame, alpha=alpha, beta=0)
        else:
            canvas = frame.copy()

        # ── Scan line ─────────────────────────────────────────────────────
        if self.cfg.get('HUD_SHOW_SCAN_LINE', True):
            self._draw_scan_line(canvas, elapsed)

        # ── Crosshair ─────────────────────────────────────────────────────
        if self.cfg.get('HUD_SHOW_CROSSHAIR', True):
            self._draw_crosshair(canvas, pulse, deg)

        # ── Corner brackets ───────────────────────────────────────────────
        self._draw_corner_elements(canvas, fps, battery, temp_c, zoom_factor)

        # ── Compass / heading ─────────────────────────────────────────────
        if self.cfg.get('HUD_SHOW_COMPASS', True):
            self._draw_compass(canvas, elapsed)

        # ── Time & date ───────────────────────────────────────────────────
        if self.cfg.get('HUD_SHOW_TIME', True):
            self._draw_time(canvas, elapsed)

        # ── Bottom status bar ─────────────────────────────────────────────
        self._draw_status_bar(canvas, zoom_factor, led_on, detections)

        # ── Object detections ────────────────────────────────────────────
        if detections:
            self._draw_detections(canvas, detections)

        return canvas

    def _draw_scan_line(self, canvas: np.ndarray, elapsed: float):
        """Animated horizontal scan line sweeping top to bottom."""
        speed = self.cfg.get('HUD_SCAN_LINE_SPEED', 2.0)
        self._scan_y = int((elapsed * speed * self.H) % self.H)
        line_y = self._scan_y

        # Main scan line with glow
        for g in range(5, 0, -1):
            intensity = int(180 * (g / 5))
            cv2.line(canvas, (0, line_y), (self.W, line_y),
                     (intensity // 3, intensity, intensity // 3), 1)

        # Dashed return line
        if self._scan_y > 5:
            cv2.line(canvas, (0, line_y - 3), (self.W, line_y - 3),
                     (0, 255, 255), 1)

    def _draw_crosshair(self, canvas: np.ndarray, pulse: float, deg: float):
        """Central reticle with rotating outer ring."""
        cx, cy = self._cx, self._cy
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))

        # Inner cross
        gap = 20
        cv2.line(canvas, (cx - 40, cy), (cx - gap, cy), c, 1)
        cv2.line(canvas, (cx + gap, cy), (cx + 40, cy), c, 1)
        cv2.line(canvas, (cx, cy - 40), (cx, cy - gap), c, 1)
        cv2.line(canvas, (cx, cy + gap), (cx, cy + 40), c, 1)

        # Center dot
        cv2.circle(canvas, (cx, cy), 3, c2, -1)

        # Rotating outer ring (segments)
        r_outer = 70
        for i in range(8):
            angle = math.radians(45 * i + deg)
            x1 = int(cx + (r_outer - 15) * math.cos(angle))
            y1 = int(cy + (r_outer - 15) * math.sin(angle))
            x2 = int(cx + r_outer * math.cos(angle))
            y2 = int(cy + r_outer * math.sin(angle))
            cv2.line(canvas, (x1, y1), (x2, y2), c2, 2)

        # Pulsing outer circle
        r_pulse = int(r_outer + pulse * 8)
        cv2.circle(canvas, (cx, cy), r_pulse, c2, 1)

        # Tick marks around outer ring
        for i in range(36):
            angle = math.radians(10 * i + deg * 0.5)
            if i % 3 != 0:
                inner_r = r_outer - 5
            else:
                inner_r = r_outer - 10
            x = int(cx + inner_r * math.cos(angle))
            y = int(cy + inner_r * math.sin(angle))
            cv2.circle(canvas, (x, y), 1, c2, -1)

    def _draw_corner_elements(self, canvas, fps, battery, temp_c, zoom_factor):
        """Draw HUD elements in all 4 corners."""
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))
        c_alert = self.cfg.get('HUD_COLOR_ALERT', (0, 80, 255))
        pad = 20

        # ── Top-left: Zoom + FPS ──────────────────────────────────────────
        if self.cfg.get('HUD_SHOW_ZOOM_LEVEL', True):
            zoom_text = f"ZOOM {zoom_factor:.1f}x"
            cv2.putText(canvas, zoom_text, (pad, pad + 20),
                       self._font_thin, 0.6, c, 1)
            # Zoom bar
            bar_w = 80
            bar_h = 4
            zoom_progress = (zoom_factor - 1) / 7  # normalize 1-8x to 0-1
            self._loading_bar(canvas, pad, pad + 28, bar_w, bar_h, zoom_progress, c2)

        if self.cfg.get('HUD_SHOW_FPS_COUNTER', True):
            fps_text = f"FPS {fps:.1f}"
            cv2.putText(canvas, fps_text, (pad, pad + 55),
                        self._font_thin, 0.5, c2, 1)

        # ── Top-right: Compass heading ───────────────────────────────────
        heading = int((time.time() * 0) % 360)  # static compass
        heading_text = f"HEADING {heading:03d}°"
        cv2.putText(canvas, heading_text, (self.W - pad - 100, pad + 20),
                    self._font_thin, 0.6, c, 1)

        # Compass arc
        arc_center = (self.W - pad - 50, pad + 50)
        self._draw_arc(canvas, arc_center, 30, -60, 60, c2, 1)
        cv2.putText(canvas, "N", (arc_center[0] - 5, arc_center[1] - 30),
                    self._font_thin, 0.5, c2, 1)

        # ── Bottom-left: Battery + Temperature ───────────────────────────
        by = self.H - pad - 10
        if self.cfg.get('HUD_SHOW_BATTERY', True):
            batt_text = f"BAT {battery:.0f}%"
            cv2.putText(canvas, batt_text, (pad, by),
                        self._font_thin, 0.5, c2, 1)
            # Battery icon
            bx, by2 = pad + 70, by - 12
            cv2.rectangle(canvas, (bx, by2), (bx + 40, by2 + 10), c2, 1)
            cv2.rectangle(canvas, (bx + 40, by2 + 3), (bx + 43, by2 + 7), c2, -1)
            # Battery fill
            fill_w = int(40 * battery / 100)
            batt_color = c2 if battery > 20 else c_alert
            cv2.rectangle(canvas, (bx + 1, by2 + 1), (bx + fill_w, by2 + 9), batt_color, -1)

        if self.cfg.get('HUD_SHOW_TEMPERATURE', True):
            temp_text = f"TEMP {temp_c:.0f}°C"
            cv2.putText(canvas, temp_text, (pad, by - 20),
                        self._font_thin, 0.5, c2, 1)

        # ── Bottom-right: System status ───────────────────────────────────
        sx = self.W - pad - 120
        status_y = self.H - pad - 10
        cv2.putText(canvas, "SYS ONLINE", (sx, status_y),
                    self._font_thin, 0.5, c2, 1)
        cv2.putText(canvas, "IR LEDs [ON]" if True else "IR LEDs [OFF]",
                    (sx, status_y - 20), self._font_thin, 0.5, c2, 1)

        # Corner brackets for the whole HUD frame
        corner_size = 60
        self._draw_bracket(canvas, 0, 0, corner_size, corner_size, c, 2)
        self._draw_bracket(canvas, self.W - corner_size, 0, corner_size, corner_size, c, 2)
        self._draw_bracket(canvas, 0, self.H - corner_size, corner_size, corner_size, c, 2)
        self._draw_bracket(canvas, self.W - corner_size, self.H - corner_size,
                          corner_size, corner_size, c, 2)

        # Top center — system name
        sys_text = "NIGHT VISION SYSTEM v1.0"
        tw, th = cv2.getTextSize(sys_text, self._font_thin, 0.5, 1)[0]
        tx = self._cx - tw // 2
        cv2.putText(canvas, sys_text, (tx, pad + 12),
                    self._font_thin, 0.5, c2, 1)

        # Subtle top divider line
        cv2.line(canvas, (corner_size + 20, pad + 18),
                 (self.W - corner_size - 20, pad + 18), c, 1)

    def _draw_compass(self, canvas, elapsed: float):
        """Animated compass strip at top."""
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        strip_h = 30
        strip_y = 40

        # Background strip
        cv2.rectangle(canvas, (0, strip_y), (self.W, strip_y + strip_h),
                      (0, 0, 0), -1)
        cv2.addWeighted(canvas[strip_y:strip_y + strip_h], 0.3,
                        canvas[strip_y:strip_y + strip_h], 0.7, 0, canvas[strip_y:strip_y + strip_h])

        # Tick marks and labels
        deg = elapsed * 5  # slowly rotating
        for i in range(-180, 181, 10):
            angle_pos = int((i + deg) % 360)
            x_pos = self._cx + int((angle_pos - 180) * 4)  # scale
            if 0 <= x_pos <= self.W:
                major = i % 90 == 0
                label = ['N', 'E', 'S', 'W'][i // 90 % 4] if major else ''
                cv2.line(canvas, (x_pos, strip_y), (x_pos, strip_y + (8 if major else 4)), c, 1)
                if label:
                    cv2.putText(canvas, label, (x_pos - 5, strip_y + 22),
                                self._font_thin, 0.4, c, 1)

        # Center triangle indicator
        cv2.line(canvas, (self._cx - 10, strip_y + strip_h),
                 (self._cx + 10, strip_y + strip_h), c, 1)
        cv2.line(canvas, (self._cx, strip_y), (self._cx - 8, strip_y + 10), c, 2)
        cv2.line(canvas, (self._cx, strip_y), (self._cx + 8, strip_y + 10), c, 2)

    def _draw_time(self, canvas, elapsed: float):
        """Timestamp in top-right with millisecond counter."""
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))
        now = datetime.now()
        ts = now.strftime("%H:%M:%S")
        ms = int((elapsed * 1000) % 1000)
        time_text = f"{ts}.{ms:03d}"
        cv2.putText(canvas, time_text, (self._cx + 80, 30),
                    self._font_main, 0.5, c, 1)
        date_text = now.strftime("%d %b %Y")
        cv2.putText(canvas, date_text, (self._cx + 80, 50),
                    self._font_thin, 0.4, c2, 1)

    def _draw_status_bar(self, canvas, zoom_factor: float, led_on: bool, detections: list):
        """Bottom status strip with mode info."""
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))
        bar_y = self.H - 70

        # Background strip
        cv2.rectangle(canvas, (0, bar_y), (self.W, self.H), (0, 0, 0), -1)
        cv2.addWeighted(canvas[bar_y:self.H], 0.4, canvas[bar_y:self.H], 0.6, 0, canvas[bar_y:self.H])

        # Mode labels
        modes = [
            ("ZOOM", f"{zoom_factor:.1f}x"),
            ("DETECT", "ON" if (detections and len(detections) > 0) else "OFF"),
            ("LED", "ON" if led_on else "OFF"),
            ("MODE", "NIGHT"),
        ]
        for i, (label, value) in enumerate(modes):
            x = 80 + i * 200
            cv2.putText(canvas, label, (x, bar_y + 25),
                        self._font_thin, 0.45, c2, 1)
            cv2.putText(canvas, value, (x, bar_y + 48),
                        self._font_main, 0.6, c, 1)
            # Separator
            if i < len(modes) - 1:
                cv2.line(canvas, (x + 150, bar_y + 10),
                         (x + 150, self.H - 10), c2, 1)

    def _draw_detections(self, canvas, detections: List[dict]):
        """Draw bounding boxes and labels for detected objects."""
        c_det = self.cfg.get('HUD_COLOR_DETECTION', (0, 255, 0))
        c_alert = self.cfg.get('HUD_COLOR_ALERT', (0, 80, 255))

        for det in detections:
            x, y, w, h = det.get('bbox', (0, 0, 0, 0))
            label = det.get('label', 'object')
            conf = det.get('confidence', 0.0)
            color = c_alert if conf > 0.7 else c_det

            # Bounding box
            cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)

            # Label background
            text = f"{label} {conf:.0%}"
            (tw, th2), _ = cv2.getTextSize(text, self._font_thin, 0.5, 1)
            cv2.rectangle(canvas, (x, y - th2 - 8), (x + tw + 8, y), (0, 0, 0), -1)
            cv2.putText(canvas, text, (x + 4, y - 4),
                       self._font_thin, 0.5, color, 1)

            # Corner brackets on detected object
            box_w, box_h = w, h
            self._draw_bracket(canvas, x, y, box_w, box_h, color, 1)