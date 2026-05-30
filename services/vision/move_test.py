"""
Move a single servo by a small delta to verify control.

Usage:
    uv run move_test.py <servo_id> [delta] [duration]
    uv run move_test.py 1           # servo 1, +30 ticks over 2s
    uv run move_test.py 1 -30       # servo 1, -30 ticks over 2s
    uv run move_test.py 1 100 5     # servo 1, +100 ticks over 5s

Units: raw encoder ticks (0–4095 = full 360°). Delta of 30 = ~2.6°.
No unit conversion — read in ticks, delta in ticks, write in ticks.
"""
import sys
import os
import time
from dotenv import load_dotenv

load_dotenv()

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

servo_id = int(sys.argv[1])
delta    = int(sys.argv[2]) if len(sys.argv) > 2 else 30
duration = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
port     = os.getenv("ROBOT_PORT", "/dev/ttyUSB0")

from robot.servo_client import ServoClient
from db.robot_writer import update_robot_state

client = ServoClient(port=port, servo_ids=[servo_id])
try:
    client.connect()

    # --- safety checks before touching anything ---

    torque = client.read_torque_enabled(servo_id)
    current = client.read_position(servo_id)

    if current is None:
        print(f"Servo {servo_id} did not respond. Check ID and connection.")
        sys.exit(1)

    target = max(0, min(4095, current + delta))
    degrees = abs(delta) / 4095 * 360

    print(f"Servo {servo_id}")
    print(f"  Current position : {current} ticks")
    print(f"  Target position  : {target} ticks  (Δ{delta:+} = {degrees:.1f}°)")
    print(f"  Duration         : {duration}s  (40 interpolated steps)")
    print(f"  Torque enabled   : {torque}")
    print()

    if torque:
        print("⚠  Torque is ON — servo will move immediately when you confirm.")
    else:
        print("ℹ  Torque is OFF — position command will be stored but servo won't move.")
        print("   Enable torque manually if you want it to actually move.")

    print()
    try:
        input("Press Enter to send position command, Ctrl+C to cancel... ")
    except KeyboardInterrupt:
        print("\nCancelled — nothing sent.")
        sys.exit(0)

    update_robot_state(curr_pos=[current], next_pos=[target], pose="move_test")
    client.set_position_slow(servo_id, target, duration=duration)

    confirmed = client.read_position(servo_id)
    update_robot_state(curr_pos=[confirmed], next_pos=[], pose="move_test")
    print(f"Position now: {confirmed} ticks")

except Exception as e:
    print(f"Error: {e}")
finally:
    client.disconnect()
