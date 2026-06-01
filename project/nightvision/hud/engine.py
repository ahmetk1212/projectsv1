"""
HUD Engine — JARVIS-style overlay renderer
Optimized for real-time rendering on laptop CPU.
"""
import math
import time
from datetime import datetime
from typing import List, Optional

import numpy as np
import cv2


class HUDEngine:
    """
    Sci-fi HUD overlay (JARVIS / Iron Man style) drawn on a camera feed.
    Static elements are pre-rendered once; only animated parts update.
    """

    def __init__(self, width: int, height: int, config: dict):
        self.W = width
        self.H = height
        self.cfg = config
        self.start_time = time.time()
        self._scan_y = 0
        self._font_main = cv2.FONT_HERSHEY_DUPLEX
        self._font_thin = cv2.FONT_HERSHEY_SIMPLEX

        # Pre-rendered static layer (background gradient, corner brackets, etc.)
        self._static_layer = self._build_static_layer()
        # Compass strip texture (regenerated each frame for animation)

        # Lookup tables
        self._rad_sin = None
        self._rad_cos = None

    def _make_color(self, base, glow_factor=0.0):
        """Generate a dimmer color for glow effect."""
        return tuple(max(0, int(v * (1 - glow_factor))) for v in base)

    def _build_static_layer(self) -> np.ndarray:
        """Pre-render all static HUD elements once."""
        layer = np.zeros((self.H, self.W, 3), dtype=np.uint8)
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))

        # Corner brackets (4 corners)
        cs = 50
        self._draw_bracket(layer, 0, 0, cs, cs, c, 2)
        self._draw_bracket(layer, self.W - cs, 0, cs, cs, c, 2)
        self._draw_bracket(layer, 0, self.H - cs, cs, cs, c, 2)
        self._draw_bracket(layer, self.W - cs, self.H - cs, cs, cs, c, 2)

        # Top divider
        cv2.line(layer, (cs + 20, 25), (self.W - cs - 20, 25), c, 1)
        # Bottom status bar background
        cv2.rectangle(layer, (0, self.H - 70), (self.W, self.H), (0, 0, 0), -1)
        # Separators
        for i in range(4):
            x = 80 + i * 200 + 150
            cv2.line(layer, (x, self.H - 60), (x, self.H - 10), c2, 1)
        return layer

    # ── Drawing helpers ────────────────────────────────────────────────────

    def _draw_bracket(self, canvas, x, y, w, h, color, thickness=2):
        b_len = min(w, h) // 4
        cv2.line(canvas, (x, y + b_len), (x, y), color, thickness)
        cv2.line(canvas, (x, y), (x + b_len, y), color, thickness)
        cv2.line(canvas, (x + w - b_len, y), (x + w, y), color, thickness)
        cv2.line(canvas, (x + w, y), (x + w, y + b_len), color, thickness)
        cv2.line(canvas, (x, y + h - b_len), (x, y + h), color, thickness)
        cv2.line(canvas, (x, y + h), (x + b_len, y + h), color, thickness)
        cv2.line(canvas, (x + w - b_len, y + h), (x + w, y + h), color, thickness)
        cv2.line(canvas, (x + w, y + h - b_len), (x + w, y + h), color, thickness)

    def _loading_bar(self, canvas, x, y, w, h, progress, color):
        """Segmented loading bar."""
        segments = 10
        seg_w = w // segments
        for i in range(segments):
            filled = (i / segments) <= progress
            sx = x + i * seg_w
            c = color if filled else (color[0] // 4, color[1] // 4, color[2] // 4)
            cv2.rectangle(canvas, (sx, y), (sx + seg_w - 1, y + h), c, -1)

    # ── Public render entry ────────────────────────────────────────────────

    def render(self, frame: np.ndarray, detections: List[dict] = None,
               zoom_factor: float = 1.0, fps: float = 30.0,
               battery: float = 100.0, temp_c: float = 45.0,
               led_on: bool = True) -> np.ndarray:
        canvas = self._apply_tint(frame.copy())
        elapsed = time.time() - self.start_time
        pulse = abs(math.sin(elapsed * math.pi * self.cfg.get('HUD_PULSE_RATE', 1.5)))
        deg = math.degrees(elapsed) * 10

        # Static layer
        cv2.add(canvas, self._static_layer, dst=canvas)

        # Animated scan line
        if self.cfg.get('HUD_SHOW_SCAN_LINE', True):
            self._draw_scan_line(canvas, elapsed)

        # Crosshair
        if self.cfg.get('HUD_SHOW_CROSSHAIR', True):
            self._draw_crosshair(canvas, pulse, deg)

        # Corner text overlays
        self._draw_corner_text(canvas, fps, battery, temp_c, zoom_factor, led_on)

        # Compass
        if self.cfg.get('HUD_SHOW_COMPASS', True):
            self._draw_compass(canvas, elapsed)

        # Time
        if self.cfg.get('HUD_SHOW_TIME', True):
            self._draw_time(canvas, elapsed)

        # Bottom status
        self._draw_status_bar(canvas, zoom_factor, led_on, detections)

        # Detections
        if detections:
            self._draw_detections(canvas, detections)

        return canvas

    def _apply_tint(self, frame: np.ndarray) -> np.ndarray:
        """Darken camera feed slightly for HUD contrast."""
        alpha = self.cfg.get('HUD_CAMERA_FEED_ALPHA', 0.65)
        if alpha < 1.0:
            frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=0)
        return frame

    def _draw_scan_line(self, canvas, elapsed):
        speed = self.cfg.get('HUD_SCAN_LINE_SPEED', 2.0)
        line_y = int((elapsed * speed * self.H) % self.H)
        cv2.line(canvas, (0, line_y), (self.W, line_y), (60, 200, 60), 1)
        if line_y > 3:
            cv2.line(canvas, (0, line_y - 3), (self.W, line_y - 3), (30, 100, 30), 1)

    def _draw_crosshair(self, canvas, pulse, deg):
        cx, cy = self.W // 2, self.H // 2
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))
        gap = 18
        # Inner cross
        cv2.line(canvas, (cx - 35, cy), (cx - gap, cy), c, 1)
        cv2.line(canvas, (cx + gap, cy), (cx + 35, cy), c, 1)
        cv2.line(canvas, (cx, cy - 35), (cx, cy - gap), c, 1)
        cv2.line(canvas, (cx, cy + gap), (cx, cy + 35), c, 1)
        cv2.circle(canvas, (cx, cy), 3, c2, -1)
        # Rotating segments (precompute angles)
        r_outer = 60
        for i in range(8):
            angle = math.radians(45 * i + deg)
            x1 = int(cx + (r_outer - 12) * math.cos(angle))
            y1 = int(cy + (r_outer - 12) * math.sin(angle))
            x2 = int(cx + r_outer * math.cos(angle))
            y2 = int(cy + r_outer * math.sin(angle))
            cv2.line(canvas, (x1, y1), (x2, y2), c2, 2)
        # Pulsing circle
        r_pulse = int(r_outer + pulse * 6)
        cv2.circle(canvas, (cx, cy), r_pulse, c2, 1)

    def _draw_corner_text(self, canvas, fps, battery, temp_c, zoom_factor, led_on=True):
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))
        c_alert = self.cfg.get('HUD_COLOR_ALERT', (0, 80, 255))
        pad = 18
        c2_dim = tuple(v // 2 for v in c2)

        # Top-left: ZOOM + FPS
        if self.cfg.get('HUD_SHOW_ZOOM_LEVEL', True):
            cv2.putText(canvas, f"ZOOM {zoom_factor:.1f}x",
                        (pad, pad + 8), self._font_thin, 0.5, c, 1)
            self._loading_bar(canvas, pad, pad + 14, 60, 3,
                              (zoom_factor - 1) / 7, c2)

        if self.cfg.get('HUD_SHOW_FPS_COUNTER', True):
            cv2.putText(canvas, f"FPS {fps:.1f}",
                        (pad, pad + 35), self._font_thin, 0.4, c2, 1)

        # Top-right: HEADING + N indicator
        cv2.putText(canvas, "HDG 000", (self.W - pad - 60, pad + 8),
                    self._font_thin, 0.5, c, 1)
        cv2.putText(canvas, "N", (self.W - pad - 10, pad + 30),
                    self._font_thin, 0.5, c2, 1)

        # Top-center: system name
        sys_text = "NIGHT VISION SYSTEM v1.0"
        tw, _ = cv2.getTextSize(sys_text, self._font_thin, 0.4, 1)[0]
        cv2.putText(canvas, sys_text, (self.W // 2 - tw // 2, 18),
                    self._font_thin, 0.4, c2, 1)

        # Bottom-left: BATTERY + TEMP
        by = self.H - 18
        if self.cfg.get('HUD_SHOW_BATTERY', True):
            cv2.putText(canvas, f"BAT {battery:.0f}%", (pad, by),
                        self._font_thin, 0.4, c2, 1)
            # Battery icon
            bx = pad + 65
            by2 = by - 10
            batt_color = c_alert if battery < 20 else c2
            cv2.rectangle(canvas, (bx, by2), (bx + 30, by2 + 8), c2, 1)
            cv2.rectangle(canvas, (bx + 30, by2 + 2), (bx + 33, by2 + 6), c2, -1)
            fw = int(30 * battery / 100)
            cv2.rectangle(canvas, (bx + 1, by2 + 1), (bx + fw, by2 + 7), batt_color, -1)

        if self.cfg.get('HUD_SHOW_TEMPERATURE', True):
            cv2.putText(canvas, f"TEMP {temp_c:.0f}C", (pad, by - 22),
                        self._font_thin, 0.4, c2, 1)

        # Bottom-right: SYS
        sx = self.W - pad - 90
        cv2.putText(canvas, "SYS ONLINE", (sx, by), self._font_thin, 0.4, c2, 1)
        cv2.putText(canvas, "IR [ON]" if led_on else "IR [OFF]",
                    (sx, by - 22), self._font_thin, 0.4, c2, 1)

    def _draw_compass(self, canvas, elapsed):
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))
        strip_h = 22
        strip_y = 30

        # Background
        cv2.rectangle(canvas, (0, strip_y), (self.W, strip_y + strip_h),
                      (0, 0, 0), -1)

        deg = elapsed * 5
        cx = self.W // 2
        # Tick marks
        for i in range(-180, 181, 15):
            x_pos = cx + int(i * 3 + deg * 3)
            if 0 <= x_pos <= self.W:
                major = i % 90 == 0
                th = 1 if major else 1
                cv2.line(canvas, (x_pos, strip_y + strip_h),
                         (x_pos, strip_y + strip_h - (6 if major else 3)), c, th)
                if major:
                    label = ['N', 'E', 'S', 'W'][(i // 90) % 4]
                    cv2.putText(canvas, label, (x_pos - 4, strip_y + 10),
                                self._font_thin, 0.3, c2, 1)
        # Center indicator
        cv2.line(canvas, (cx - 8, strip_y), (cx, strip_y + 5), c, 2)
        cv2.line(canvas, (cx + 8, strip_y), (cx, strip_y + 5), c, 2)

    def _draw_time(self, canvas, elapsed):
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))
        now = datetime.now()
        ts = now.strftime("%H:%M:%S")
        cv2.putText(canvas, ts, (self.W // 2 + 80, 16),
                    self._font_thin, 0.4, c2, 1)

    def _draw_status_bar(self, canvas, zoom_factor, led_on, detections):
        c = self.cfg.get('HUD_COLOR_PRIMARY', (0, 255, 255))
        c2 = self.cfg.get('HUD_COLOR_SECONDARY', (0, 200, 255))
        bar_y = self.H - 70

        # Mode labels (positioned to align with separators drawn in static layer)
        modes = [
            ("ZOOM", f"{zoom_factor:.1f}x"),
            ("DETECT", "ON" if detections and len(detections) > 0 else "OFF"),
            ("LED", "ON" if led_on else "OFF"),
            ("MODE", "NIGHT"),
        ]
        for i, (label, value) in enumerate(modes):
            x = 80 + i * 200
            cv2.putText(canvas, label, (x, bar_y + 22),
                        self._font_thin, 0.4, c2, 1)
            cv2.putText(canvas, value, (x, bar_y + 48),
                        self._font_thin, 0.55, c, 1)

    def _draw_detections(self, canvas, detections):
        c_det = self.cfg.get('HUD_COLOR_DETECTION', (0, 255, 0))
        c_alert = self.cfg.get('HUD_COLOR_ALERT', (0, 80, 255))

        for det in detections:
            x, y, w, h = det.get('bbox', (0, 0, 0, 0))
            if w <= 0 or h <= 0:
                continue
            label = det.get('label', 'object')
            conf = det.get('confidence', 0.0)
            color = c_alert if conf > 0.7 else c_det

            cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)

            text = f"{label} {conf:.0%}"
            (tw, th), _ = cv2.getTextSize(text, self._font_thin, 0.4, 1)
            cv2.rectangle(canvas, (x, y - th - 6), (x + tw + 6, y), (0, 0, 0), -1)
            cv2.putText(canvas, text, (x + 3, y - 3),
                        self._font_thin, 0.4, color, 1)
            # Corner brackets
            self._draw_bracket(canvas, x, y, w, h, color, 1)