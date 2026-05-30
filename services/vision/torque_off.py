"""
Disable torque on all servos so they can be moved freely by hand.

Usage:
    uv run torque_off.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

port = os.getenv("ROBOT_PORT", "/dev/ttyUSB0")
ids  = [int(i) for i in os.getenv("ROBOT_SERVO_IDS", "1 2 3 4 5 6").split()]

from robot.servo_client import ServoClient

client = ServoClient(port=port, servo_ids=ids)
try:
    client.connect()
    for sid in ids:
        client.enable_torque(sid, False)
        state = client.read_torque_enabled(sid)
        status = "OFF" if state == False else ("ON" if state else "?")
        print(f"Servo {sid}: torque {status}")
    print("\nAll servos released.")
except Exception as e:
    print(f"Error: {e}")
finally:
    client.disconnect()
