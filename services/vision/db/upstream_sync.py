"""
Reads local SQLite (vision + robot tables), applies business logic,
and pushes the merged result to PostgreSQL.

Business rules applied before upstream write:
- If robot pose contains 'part_true' AND curr_pos is set:
    the robot is holding an item above that station.
    Override that station's item_present → False (robot has the item, not the conveyor).
"""
import asyncio
import sqlite3
import json
import os
import psycopg
from dotenv import load_dotenv
from db.sqlite_client import write_vision_calculated
from db.rules import apply_rules

load_dotenv()

_DB_URL  = os.getenv("DB_URL", "")
_DB_PATH = os.getenv("SQLITE_PATH", "local.db")

_change_event: asyncio.Event | None = None  # initialised inside the event loop


def notify_change():
    """Call this (from the asyncio thread) whenever local data changes."""
    if _change_event is not None:
        _change_event.set()


def _read_local() -> dict:
    """Read the current singleton rows from both SQLite tables."""
    with sqlite3.connect(_DB_PATH) as db:
        db.row_factory = sqlite3.Row

        vision_row = db.execute("SELECT * FROM vision WHERE id = 1").fetchone()
        robot_row  = db.execute("SELECT * FROM robot  WHERE id = 1").fetchone()

    vision = dict(vision_row) if vision_row else {}
    robot  = dict(robot_row)  if robot_row  else {}

    if robot.get("joints"):
        try:
            robot["joints"] = json.loads(robot["joints"])
        except Exception:
            robot["joints"] = []

    return {"vision": vision, "robot": robot}




async def _push(vision: dict, robot: dict):
    merged = apply_rules(vision, robot)
    await asyncio.to_thread(write_vision_calculated, merged)

    joints = robot.get("joints", [])

    async with await psycopg.AsyncConnection.connect(_DB_URL) as conn:
        await conn.execute(
            """INSERT INTO production_line (id,
                pos1_item_present, pos1_item_status,
                pos2_item_present, pos2_item_status,
                pos3_item_present, pos3_item_status,
                pos4_item_present, pos4_item_status,
                pos5_item_present, pos5_item_status,
                robot_curr_pos, robot_next_pos, robot_joints, robot_pose
            ) VALUES (1, %s,%s, %s,%s, %s,%s, %s,%s, %s,%s, %s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                pos1_item_present = EXCLUDED.pos1_item_present,
                pos1_item_status  = EXCLUDED.pos1_item_status,
                pos2_item_present = EXCLUDED.pos2_item_present,
                pos2_item_status  = EXCLUDED.pos2_item_status,
                pos3_item_present = EXCLUDED.pos3_item_present,
                pos3_item_status  = EXCLUDED.pos3_item_status,
                pos4_item_present = EXCLUDED.pos4_item_present,
                pos4_item_status  = EXCLUDED.pos4_item_status,
                pos5_item_present = EXCLUDED.pos5_item_present,
                pos5_item_status  = EXCLUDED.pos5_item_status,
                robot_curr_pos    = EXCLUDED.robot_curr_pos,
                robot_next_pos    = EXCLUDED.robot_next_pos,
                robot_joints      = EXCLUDED.robot_joints,
                robot_pose        = EXCLUDED.robot_pose""",
            (
                bool(merged.get("pos1_item_present")), merged.get("pos1_item_status", ""),
                bool(merged.get("pos2_item_present")), merged.get("pos2_item_status", ""),
                bool(merged.get("pos3_item_present")), merged.get("pos3_item_status", ""),
                bool(merged.get("pos4_item_present")), merged.get("pos4_item_status", ""),
                bool(merged.get("pos5_item_present")), merged.get("pos5_item_status", ""),
                robot.get("curr_pos"), robot.get("next_pos"),
                joints, robot.get("pose", ""),
            ),
        )
        await conn.commit()


def _fingerprint(vision: dict, robot: dict) -> tuple:
    """Cheap snapshot to detect changes — only push when this changes."""
    return (
        tuple(vision.get(f"pos{i}_item_present") for i in range(1, 6)),
        tuple(vision.get(f"pos{i}_item_status",  "") for i in range(1, 6)),
        robot.get("curr_pos"),
        robot.get("next_pos"),
        robot.get("pose", ""),
        tuple(robot.get("joints") or []),
    )


async def sync_loop():
    if not _DB_URL:
        return

    global _change_event
    _change_event = asyncio.Event()
    last_fp = None

    while True:
        # Wait for a change signal, with a 2s fallback to catch robot writes
        # from routine.py (separate process — can't signal this event directly)
        try:
            await asyncio.wait_for(_change_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        _change_event.clear()

        try:
            data = await asyncio.to_thread(_read_local)
            fp   = _fingerprint(data["vision"], data["robot"])
            if fp != last_fp:
                await _push(data["vision"], data["robot"])
                last_fp = fp
        except Exception as e:
            print(f"  [sync] {e}")
