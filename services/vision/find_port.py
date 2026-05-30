"""
Find the serial port of your robot by unplugging it.

Usage: uv run find_port.py
"""
import serial.tools.list_ports


def list_ports():
    return {p.device for p in serial.tools.list_ports.comports()}


print("Scanning ports...")
before = list_ports()
print(f"Found {len(before)} port(s): {sorted(before) or '(none)'}")
print()
input("Unplug the robot USB, then press Enter...")

after = list_ports()
gone = before - after

if not gone:
    print("No ports disappeared. Make sure you unplugged the right cable.")
elif len(gone) == 1:
    port = next(iter(gone))
    print(f"\nRobot port: {port}")
    print(f'\nAdd this to your .env:\n  ROBOT_PORT={port}')
else:
    print(f"Multiple ports disappeared: {gone}")
    print("Unplug only the robot cable and try again.")
