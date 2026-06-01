"""
NightVision Goggles — Central Configuration
All hardware pins, camera settings, HUD params in one place.
"""

# ── Hardware ────────────────────────────────────────────────────────────────
CAMERA_FOV        = 60   # degrees (lens diagonal, used for HUD overlay)
CAMERA_RESOLUTION = (1280, 720)
CAMERA_FRAMERATE  = 30
CAMERA_ROTATION   = 0    # 0 / 90 / 180 / 270

# IR LEDs — 3 × 3W, controlled via GPIO
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
ZOOM_FPS     = 30

# ── Object Detection ────────────────────────────────────────────────────────
# Tiny YOLO (yolov4-tiny) — works on Pi 3A+ in real time
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

# ── HUD (JARVIS style) ───────────────────────────────────────────────────────
HUD_FPS              = 30
HUD_WIDTH            = 1280
HUD_HEIGHT           = 720
HUD_CAMERA_FEED_ALPHA = 0.60  # how dark the camera feed is behind HUD

# Colors (BGR — matches OpenCV convention)
HUD_COLOR_PRIMARY    = (0, 255, 255)   # cyan   #00FFFF
HUD_COLOR_SECONDARY  = (0, 200, 255)   # amber  #FFC800
HUD_COLOR_ALERT      = (0, 80, 255)    # red-orange
HUD_COLOR_DETECTION  = (0, 255, 0)    # green for detected objects
HUD_COLOR_COOL       = (255, 100, 0)   # blue-orange

# HUD corner elements
HUD_SHOW_CROSSHAIR   = True
HUD_SHOW_COMPASS     = True
HUD_SHOW_BATTERY     = True
HUD_SHOW_ZOOM_LEVEL  = True
HUD_SHOW_FPS_COUNTER = True
HUD_SHOW_TIME        = True
HUD_SHOW_TEMPERATURE = True
HUD_SHOW_SCAN_LINE   = True   # horizontal scan line animation

# HUD scanning effects
HUD_SCAN_LINE_SPEED  = 2.0    # pixels per frame
HUD_PULSE_ENABLED    = True
HUD_PULSE_RATE       = 1.5   # Hz

# ── Display ──────────────────────────────────────────────────────────────────
DISPLAY_TFT_ROTATION = 0
DISPLAY_FPS          = 30

# ── Keyboard shortcuts ───────────────────────────────────────────────────────
KEY_QUIT             = 'q'
KEY_ZOOM_IN          = 'i'
KEY_ZOOM_OUT         = 'o'
KEY_ZOOM_RESET       = 'r'
KEY_LED_TOGGLE       = 'l'
KEY_LED_FLASH        = 'f'
KEY_DETECTION_TOGGLE = 'd'
KEY_SCREENSHOT       = 's'
KEY_NIGHT_MODE       = 'n'