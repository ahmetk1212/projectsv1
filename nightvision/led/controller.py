"""
LED Controller — 3 × 3W IR LEDs via GPIO PWM
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LEDController:
    """
    Controls up to 3 IR LEDs via BCM GPIO pins using PWM.
    Supports brightness control (0–100), on/off toggle, and flash mode.
    """

    def __init__(self, pins: list, default_brightness: int = 80):
        self.pins = pins
        self.default_brightness = default_brightness
        self._gpio_available = False

        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setwarnings(False)
            for pin in self.pins:
                self.GPIO.setup(pin, self.GPIO.OUT)
            self.pwm = {pin: self.GPIO.PWM(pin, 1000) for pin in self.pins}
            for pwm_obj in self.pwm.values():
                pwm_obj.start(0)
            self._gpio_available = True
            logger.info(f"LED controller initialized on GPIO pins {pins}")
        except Exception as e:
            logger.warning(f"GPIO not available ({e}) — LED control disabled. Running in simulation mode.")
            self.pwm = {}

    def on(self, brightness: Optional[int] = None):
        """Turn all LEDs on at given brightness (0–100) or default."""
        if not self._gpio_available:
            logger.debug(f"[SIM] LEDs ON at brightness={brightness or self.default_brightness}")
            return
        b = brightness if brightness is not None else self.default_brightness
        for pwm_obj in self.pwm.values():
            pwm_obj.ChangeDutyCycle(b)
        logger.debug(f"LEDs ON at {b}%")

    def off(self):
        """Turn all LEDs off."""
        if not self._gpio_available:
            logger.debug("[SIM] LEDs OFF")
            return
        for pwm_obj in self.pwm.values():
            pwm_obj.ChangeDutyCycle(0)
        logger.debug("LEDs OFF")

    def toggle(self):
        """Toggle between on and off."""
        if not hasattr(self, '_state') or self._state is None:
            self._state = False
        self._state = not self._state
        if self._state:
            self.on()
        else:
            self.off()
        return self._state

    def set_brightness(self, brightness: int):
        """Set brightness (0–100) for all LEDs."""
        self.default_brightness = max(0, min(100, brightness))
        if self._gpio_available:
            for pwm_obj in self.pwm.values():
                pwm_obj.ChangeDutyCycle(self.default_brightness)
        logger.debug(f"LED brightness set to {self.default_brightness}%")

    def flash(self, duration: float = 0.3, times: int = 3):
        """Flash LEDs for a given duration, repeat `times`."""
        if not self._gpio_available:
            logger.debug(f"[SIM] LED flash {times}x for {duration}s")
            return
        for _ in range(times):
            self.on(100)
            time.sleep(duration)
            self.off()
            time.sleep(duration)

    def pulse(self, speed_hz: float = 2.0):
        """Start pulsing LEDs at given frequency."""
        if not self._gpio_available:
            return
        import threading
        def _pulse():
            while self._pulse_running:
                self.on(100)
                time.sleep(1 / (speed_hz * 2))
                self.off()
                time.sleep(1 / (speed_hz * 2))
        self._pulse_running = True
        self._pulse_thread = threading.Thread(target=_pulse, daemon=True)
        self._pulse_thread.start()

    def stop_pulse(self):
        """Stop pulsing."""
        self._pulse_running = False
        self.off()

    def cleanup(self):
        """Release GPIO resources."""
        if self._gpio_available:
            self.off()
            for pwm_obj in self.pwm.values():
                pwm_obj.stop()
            self.GPIO.cleanup(self.pins)
            logger.info("LED GPIO cleaned up")