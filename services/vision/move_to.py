"""
Move all servos to a target pose (6 positions simultaneously).

Usage:
    uv run move_to.py <p1> <p2> <p3> <p4> <p5> <p6> [duration]
    uv run move_to.py 2105 1131 2573 3011 2069 1816        # move over 3s (default)
    uv run move_to.py 2105 1131 2573 3011 2069 1816 5      # move over 5s
"""
import sys
import os
import time
from dotenv import load_dotenv

load_dotenv()

if len(sys.argv) < 7:
    print(__doc__)
    sys.exit(1)

targets  = {i + 1: int(sys.argv[i + 1]) for i in range(6)}
duration = float(sys.argv[7]) if len(sys.argv) > 7 else 3.0
port     = os.getenv("ROBOT_PORT", "/dev/ttyUSB0")
ids      = list(targets.keys())

from robot.servo_client import ServoClient

STEPS = 50

client = ServoClient(port=port, servo_ids=ids)
try:
    client.connect()

    currents = client.read_positions()

    print(f"{'Servo':<8} {'Current':>10} {'Target':>10} {'Delta':>8}  {'Degrees':>8}")
    print("-" * 52)
    for sid in ids:
        cur = currents[sid]
        tgt = targets[sid]
        if cur is None:
            print(f"{sid:<8} {'NO RESPONSE':>10}")
            sys.exit(1)
        delta = tgt - cur
        print(f"{sid:<8} {cur:>10} {tgt:>10} {delta:>+8}  {delta / 4095 * 360:>7.1f}°")

    print()
    print(f"Duration: {duration}s  ({STEPS} steps)")
    print()

    torques = {sid: client.read_torque_enabled(sid) for sid in ids}
    any_on = any(v for v in torques.values())
    if any_on:
        print(f"⚠  Torque ON for servos: {[sid for sid, v in torques.items() if v]}")
        print("   All servos will move simultaneously when you confirm.")
    else:
        print("ℹ  Torque is OFF — command will be stored but servos won't move.")

    print()
    try:
        input("Press Enter to move, Ctrl+C to cancel... ")
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)

    delay = duration / STEPS
    for step in range(1, STEPS + 1):
        t = step / STEPS
        for sid in ids:
            pos = int(currents[sid] + (targets[sid] - currents[sid]) * t)
            pos = max(0, min(4095, pos))
            client.set_position(sid, pos)
        time.sleep(delay)

    print("Done.")
    final = client.read_positions()
    print()
    print(f"{'Servo':<8} {'Target':>10} {'Actual':>10}")
    print("-" * 32)
    for sid in ids:
        print(f"{sid:<8} {targets[sid]:>10} {final[sid]:>10}")

except Exception as e:
    print(f"Error: {e}")
finally:
    client.disconnect()
