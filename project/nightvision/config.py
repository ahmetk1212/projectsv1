"""
NightVision Goggles — Central Configuration
All hardware pins, camera settings, HUD params in one place.
"""

# ── Hardware ────────────────────────────────────────────────────────────────
CAMERA_FOV         = 60   # degrees (lens diagonal, used for HUD overlay)
CAMERA_RESOLUTION  = (640, 480)   # laptop-friendly default
CAMERA_FRAMERATE   = 30
CAMERA_ROTATION    = 0    # 0 / 90 / 180 / 270
CAMERA_SOURCE      = 'auto'   # 'auto' | 'picamera2' | 'webcam' | 'demo'

# IR LEDs — 3 × 3W, controlled via GPIO (only used on Raspberry Pi)
LED_PINS = [17, 27, 22]   # BCM numbering (swap if your wiring is different)

# LED defaults
LED_DEFAULT_BRIGHTNESS = 80   # percent 0–100
LED_FLASH_ON_DETECT    = True # pulse LEDs when object detected

# ── Zoom ────────────────────────────────────────────────────────────────────
ZOOM_MIN     = 1.0
ZOOM_MAX     = 8.0
ZOOM_DEFAULT = 1.0
ZOOM_STEP    = 0.5          # step per key press
ZOOM_SMOOTH  = True         # animate zoom transitions

# ── Object Detection ────────────────────────────────────────────────────────
DETECTION_MODEL      = "yolov4-tiny"
DETECTION_WEIGHTS    = "yolov4-tiny.weights"
DETECTION_CFG        = "yolov4-tiny.cfg"
DETECTION_CONFIDENCE = 0.45
DETECTION_NMS        = 0.45
DETECTION_CLASSES    = [
    "person", "bicycle", "car", "motorbike", "bus", "train", "truck",
    "boat", "dog", "cat", "bird", "horse", "cow", "elephant",
    "bear", "zebra", "backpack", "umbrella", "handbag", "chair",
    "sofa", "pottedplant", "diningtable", "tv", "laptop", "phone"
]
DETECTION_ENABLED    = True
MODEL_DIR            = "models"

# ── HUD (JARVIS style) ───────────────────────────────────────────────────────
HUD_FPS              = 30
HUD_WIDTH            = 640    # match camera for now
HUD_HEIGHT           = 480
HUD_CAMERA_FEED_ALPHA = 0.65  # how dark the camera feed is behind HUD

# Colors (BGR — matches OpenCV convention)
HUD_COLOR_PRIMARY    = (0, 255, 255)   # cyan
HUD_COLOR_SECONDARY  = (0, 200, 255)   # amber
HUD_COLOR_ALERT      = (0, 80, 255)    # red-orange
HUD_COLOR_DETECTION  = (0, 255, 0)     # green for detected objects

# HUD corner elements
HUD_SHOW_CROSSHAIR   = True
HUD_SHOW_COMPASS     = True
HUD_SHOW_BATTERY     = True
HUD_SHOW_ZOOM_LEVEL  = True
HUD_SHOW_FPS_COUNTER = True
HUD_SHOW_TIME        = True
HUD_SHOW_TEMPERATURE = True
HUD_SHOW_SCAN_LINE   = True

# HUD scanning effects
HUD_SCAN_LINE_SPEED  = 2.0    # pixels per frame
HUD_PULSE_ENABLED    = True
HUD_PULSE_RATE       = 1.5    # Hz

# ── Display ──────────────────────────────────────────────────────────────────
DISPLAY_FPS          = 30

# ── Keyboard shortcuts ───────────────────────────────────────────────────────
KEY_QUIT             = ord('q')
KEY_ZOOM_IN          = ord('i')
KEY_ZOOM_OUT         = ord('o')
KEY_ZOOM_RESET       = ord('r')
KEY_LED_TOGGLE       = ord('l')
KEY_LED_FLASH        = ord('f')
KEY_DETECTION_TOGGLE = ord('d')
KEY_SCREENSHOT       = ord('s')
KEY_NIGHT_MODE       = ord('n')
KEY_PAUSE            = ord(' ')   # spacebar to pause
KEY_HELP             = ord('h')