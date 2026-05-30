"""
Run a named action (set of poses) with pauses in between, then unlock motors.

Usage:
    uv run routine.py           # runs default action (3_4)
    uv run routine.py 3_4
    uv run routine.py 3_5
    uv run routine.py 5_4
    uv run routine.py 5_R
"""
import os
import sys
import json
import time
import urllib.request
from dotenv import load_dotenv

load_dotenv()

_VISION_URL = f"http://localhost:{os.getenv('STREAM_PORT', '8000')}"


def _force_station(station: int, value: bool | None):
    try:
        data = json.dumps({"station": station, "value": value}).encode()
        req = urllib.request.Request(
            f"{_VISION_URL}/stations/force",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1)
    except Exception as e:
        print(f"  [force] {e}")


def _apply_forces(forces: dict[int, bool | None]):
    for station, value in forces.items():
        _force_station(station, value)


def _update_robot_display(pose: str, curr_pos, next_pos, joints: list[int]):
    try:
        data = json.dumps({
            "pose": pose, "curr_pos": curr_pos,
            "next_pos": next_pos, "joints": joints,
        }).encode()
        req = urllib.request.Request(
            f"{_VISION_URL}/robot/state",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass


# ── Define your actions here ──────────────────────────────────────────────────
#
# Each action is a named list of poses. Call with: uv run routine.py <action>
#
# Pose fields:
#   name      — label shown in console + stored as robot_pose in DB
#   positions — 6 servo ticks (0–4095), one per joint
#   pause     — seconds to hold this pose (default: DEFAULT_PAUSE)
#   station   — station number where gripper is (stored as robot_curr_pos)
#   forces    — {station_id: True/False/None} applied before moving

ACTIONS = {

    "3_4": [
        {
            "name":      "home|part_false|gripper_closed",
            "positions": [2052, 973, 2306, 2970, 2068, 1816],
        },
        {
            "name":      "above|part_false|gripper_closed",
            "positions": [2060, 1955, 1907, 2865, 2069, 1825],
            "pause":     2.0,
            "station":   0,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "above|part_false|gripper_open",
            "positions": [2060, 1955, 1907, 2865, 2069, 2603],
            "pause":     4.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "lower|part_false|gripper_open",
            "positions": [2045, 2301, 1951, 2778, 2069, 2603],
            "pause":     2.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "lower|part_true|gripper_closed",
            "positions": [2045, 2301, 1951, 2778, 2069, 2060],
            "pause":     2.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "above|part_true|gripper_closed",
            "positions": [2052, 1955, 1907, 2865, 2069, 2060],
            "pause":     1.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "home|part_true|gripper_closed",
            "positions": [2052, 973, 2306, 2970, 2068, 2060],
            "pause":     4.0,
            "station":   0,
            "forces":    {3: None, 4: None},
        },
    ],

    "3_5": [
        {
            "name":      "home|part_false|gripper_closed",
            "positions": [2052, 973, 2306, 2970, 2068, 1816],
        },
        {
            "name":      "above|part_false|gripper_closed",
            "positions": [2060, 1955, 1907, 2865, 2069, 1825],
            "pause":     2.0,
            "station":   0,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "above|part_false|gripper_open",
            "positions": [2060, 1955, 1907, 2865, 2069, 2603],
            "pause":     4.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "lower|part_false|gripper_open",
            "positions": [2045, 2301, 1951, 2778, 2069, 2603],
            "pause":     2.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "lower|part_true|gripper_closed",
            "positions": [2045, 2301, 1951, 2778, 2069, 2060],
            "pause":     2.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "above|part_true|gripper_closed",
            "positions": [2052, 1955, 1907, 2865, 2069, 2060],
            "pause":     1.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "home|part_true|gripper_closed",
            "positions": [2052, 973, 2306, 2970, 2068, 2060],
            "pause":     4.0,
            "station":   0,
            "forces":    {3: None, 4: None},
        },
    ],

    "5_4": [
        {
            "name":      "home|part_false|gripper_closed",
            "positions": [2052, 973, 2306, 2970, 2068, 1816],
        },
        {
            "name":      "above|part_false|gripper_closed",
            "positions": [2060, 1955, 1907, 2865, 2069, 1825],
            "pause":     2.0,
            "station":   0,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "above|part_false|gripper_open",
            "positions": [2060, 1955, 1907, 2865, 2069, 2603],
            "pause":     4.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "lower|part_false|gripper_open",
            "positions": [2045, 2301, 1951, 2778, 2069, 2603],
            "pause":     2.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "lower|part_true|gripper_closed",
            "positions": [2045, 2301, 1951, 2778, 2069, 2060],
            "pause":     2.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "above|part_true|gripper_closed",
            "positions": [2052, 1955, 1907, 2865, 2069, 2060],
            "pause":     1.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "home|part_true|gripper_closed",
            "positions": [2052, 973, 2306, 2970, 2068, 2060],
            "pause":     4.0,
            "station":   0,
            "forces":    {3: None, 4: None},
        },
    ],

    "5_R": [
        {
            "name":      "home|part_false|gripper_closed",
            "positions": [2052, 973, 2306, 2970, 2068, 1816],
        },
        {
            "name":      "above|part_false|gripper_closed",
            "positions": [2060, 1955, 1907, 2865, 2069, 1825],
            "pause":     2.0,
            "station":   0,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "above|part_false|gripper_open",
            "positions": [2060, 1955, 1907, 2865, 2069, 2603],
            "pause":     4.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "lower|part_false|gripper_open",
            "positions": [2045, 2301, 1951, 2778, 2069, 2603],
            "pause":     2.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "lower|part_true|gripper_closed",
            "positions": [2045, 2301, 1951, 2778, 2069, 2060],
            "pause":     2.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "above|part_true|gripper_closed",
            "positions": [2052, 1955, 1907, 2865, 2069, 2060],
            "pause":     1.0,
            "station":   3,
            "forces":    {3: True, 4: True},
        },
        {
            "name":      "home|part_true|gripper_closed",
            "positions": [2052, 973, 2306, 2970, 2068, 2060],
            "pause":     4.0,
            "station":   0,
            "forces":    {3: None, 4: None},
        },
    ],

}

MOVE_SPEED    = 250
DEFAULT_PAUSE = 4.0

# ─────────────────────────────────────────────────────────────────────────────

port = os.getenv("ROBOT_PORT", "/dev/ttyUSB0")
ids  = [int(i) for i in os.getenv("ROBOT_SERVO_IDS", "1 2 3 4 5 6").split()]

from robot.servo_client import ServoClient
from db.robot_writer import update_robot_state, mark_robot_handled


def move_to_pose(client: ServoClient, name: str, targets: dict[int, int]):
    print(f"→ {name}")
    for sid, pos in targets.items():
        client.set_position(sid, pos)


action_name = sys.argv[1] if len(sys.argv) > 1 else "3_4"
if action_name not in ACTIONS:
    print(f"Unknown action '{action_name}'. Available: {list(ACTIONS.keys())}")
    sys.exit(1)

POSES = ACTIONS[action_name]

client = ServoClient(port=port, servo_ids=ids)
try:
    client.connect()
    print(f"Action: {action_name}  |  {len(POSES)} poses\n")

    client.set_speed_all(MOVE_SPEED)

    for i, pose in enumerate(POSES):
        name      = pose["name"]
        positions = pose["positions"]
        pause     = pose.get("pause", DEFAULT_PAUSE)
        station   = pose.get("station")
        forces    = pose.get("forces", {})

        next_station = next(
            (p["station"] for p in POSES[i + 1:] if "station" in p), None  # POSES is the selected action
        )

        if forces:
            _apply_forces(forces)

        targets     = dict(zip(ids, positions))
        curr_joints = list(client.read_positions().values())
        update_robot_state(curr_pos=station, next_pos=next_station, joints=curr_joints, pose=name)
        _update_robot_display(pose=name, curr_pos=station, next_pos=next_station, joints=curr_joints)

        move_to_pose(client, name, targets)
        print(f"  holding {pause}s...")
        time.sleep(pause)

        settled_joints = list(client.read_positions().values())
        update_robot_state(curr_pos=station, next_pos=next_station, joints=settled_joints, pose=name)
        _update_robot_display(pose=name, curr_pos=station, next_pos=next_station, joints=settled_joints)

    # The robot has pulled the flagged part off the line — record it so the
    # no-go defect(s) drop off the dashboard.
    handled = mark_robot_handled()
    if handled:
        print(f"  marked {handled} faulty part(s) as robot-handled")

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
