"""
LED Simulator — test the LED control logic without GPIO hardware.
Useful for laptop development before deploying to Pi.
"""
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 50)
    print("  LED CONTROLLER SIMULATOR")
    print("=" * 50)
    print("  No GPIO on this machine — running simulation.")
    print("  Press Ctrl+C to stop.")
    print("=" * 50)
    print()
    print("Commands:")
    print("  on [brightness]  Turn LEDs on (default 80%)")
    print("  off              Turn LEDs off")
    print("  toggle           Toggle on/off")
    print("  flash [n]        Flash N times (default 3)")
    print("  brightness [0-100]  Set brightness")
    print("  pulse [Hz]       Start pulsing")
    print("  status           Show current state")
    print("  quit             Exit")
    print()

    from led.controller import LEDController
    led = LEDController(pins=[17, 27, 22], default_brightness=80)
    state = {'on': False, 'brightness': 80, 'pulsing': False}

    def print_state():
        print(f"  → State: on={state['on']}, brightness={state['brightness']}%, "
              f"pulsing={state['pulsing']}")

    print_state()
    while True:
        try:
            cmd = input("LED> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        parts = cmd.split()
        action = parts[0]

        if action in ('quit', 'q', 'exit'):
            break
        elif action == 'on':
            b = int(parts[1]) if len(parts) > 1 else None
            led.on(b)
            state['on'] = True
            if b is not None:
                state['brightness'] = b
            print_state()
        elif action == 'off':
            led.off()
            state['on'] = False
            state['pulsing'] = False
            print_state()
        elif action == 'toggle':
            result = led.toggle()
            state['on'] = result
            print_state()
        elif action == 'flash':
            n = int(parts[1]) if len(parts) > 1 else 3
            print(f"  Flashing {n} times...")
            led.flash(0.2, n)
            print_state()
        elif action in ('brightness', 'b'):
            if len(parts) > 1:
                b = int(parts[1])
                led.set_brightness(b)
                state['brightness'] = b
                print_state()
        elif action == 'pulse':
            hz = float(parts[1]) if len(parts) > 1 else 1.0
            state['pulsing'] = True
            led.pulse(hz)
            print(f"  Pulsing at {hz} Hz")
        elif action == 'status':
            print_state()
        else:
            print(f"  Unknown command: {action}")

    print("\nExiting LED simulator.")


if __name__ == '__main__':
    main()