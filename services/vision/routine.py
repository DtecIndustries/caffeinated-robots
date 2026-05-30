"""
Run a sequence of poses with pauses in between, then unlock motors.

Edit the POSES list below to define your routine.
Each pose is 6 servo positions (IDs 1–6), in ticks (0–4095).

Usage:
    uv run routine.py
"""
import os
import time
from dotenv import load_dotenv

load_dotenv()

# ── Define your routine here ──────────────────────────────────────────────────
#
#  Each entry: (name, [p1, p2, p3, p4, p5, p6])
#           or (name, [p1, p2, p3, p4, p5, p6], pause_seconds)
#
#  name        — label printed to console, purely cosmetic
#  positions   — 6 servo ticks (0–4095)
#  pause_s     — optional, overrides DEFAULT_PAUSE for this pose only

POSES = [
    ("home",   [2052, 1132, 2574, 3011, 2069, 1816]),
    ("move_above", [2060, 1955, 1907, 2865, 2069, 1825], 4.0),
    ("open_gripper", [2060, 1955, 1907, 2865, 2069, 2603], 4.0),
    ("reach_down", [2045, 2301, 1951, 2778, 2069, 2603], 5.0),
    ("close_gripper", [2045, 2301, 1951, 2778, 2069, 2053], 6.0),
    ("move_up", [2052, 1955, 1907, 2865, 2069, 2053], 4.0),
    ("home_again", [2052, 1131, 2573, 3011, 2069, 2053]),
]

MOVE_SPEED    = 250   # hardware speed limit per servo (0 = max, ~100 = slow, ~500 = normal)
DEFAULT_PAUSE = 4.0   # seconds to hold each pose (can be overridden per pose above)

# ─────────────────────────────────────────────────────────────────────────────

port = os.getenv("ROBOT_PORT", "/dev/ttyUSB0")
ids  = [int(i) for i in os.getenv("ROBOT_SERVO_IDS", "1 2 3 4 5 6").split()]

from robot.servo_client import ServoClient


def move_to_pose(client: ServoClient, name: str, targets: dict[int, int]):
    print(f"→ {name}")
    for sid, pos in targets.items():
        client.set_position(sid, pos)


client = ServoClient(port=port, servo_ids=ids)
try:
    client.connect()
    print(f"Connected — running {len(POSES)} pose routine\n")

    # Set hardware speed limit on all servos — smooth, no software jitter
    client.set_speed_all(MOVE_SPEED)

    for entry in POSES:
        name, positions, *rest = entry
        pause = rest[0] if rest else DEFAULT_PAUSE
        targets = dict(zip(ids, positions))
        move_to_pose(client, name, targets)
        print(f"  holding {pause}s...")
        time.sleep(pause)

    print("\nRoutine complete.")

except KeyboardInterrupt:
    print("\nInterrupted.")
except Exception as e:
    print(f"Error: {e}")
finally:
    for sid in ids:
        client.enable_torque(sid, False)
    print("Motors unlocked.")
    client.disconnect()
