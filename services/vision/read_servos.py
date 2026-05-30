"""
Continuously read and print servo positions.

Usage:
    uv run read_servos.py                       # uses .env values
    uv run read_servos.py /dev/tty.usbserial-* 1 2 3 4 5 6
"""
import sys
import os
import time
from dotenv import load_dotenv

load_dotenv()

port = sys.argv[1] if len(sys.argv) > 1 else os.getenv("ROBOT_PORT", "/dev/ttyUSB0")
ids  = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else [
    int(i) for i in os.getenv("ROBOT_SERVO_IDS", "1 2 3 4 5 6").split()
]

from robot.servo_client import ServoClient

client = ServoClient(port=port, servo_ids=ids)
try:
    client.connect()
    print(f"Connected to {port}  |  servos: {ids}")
    print("Move joints to verify readings. Ctrl+C to stop.\n")
    header = f"{'ID':<5}" + "".join(f"  servo {sid:>2}" for sid in ids)
    print(header)
    print("-" * len(header))
    while True:
        positions = client.read_positions()
        row = "     " + "".join(
            f"  {pos:>8}" if pos is not None else f"  {'???':>8}"
            for pos in positions.values()
        )
        print(row, end="\r")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nStopped.")
except Exception as e:
    print(f"\nError: {e}")
    print("Check ROBOT_PORT in .env, or run: uv run find_port.py")
finally:
    client.disconnect()
