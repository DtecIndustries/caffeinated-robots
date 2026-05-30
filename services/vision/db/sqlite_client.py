import sqlite3
import json
import os

_DB_PATH = os.getenv("SQLITE_PATH", "local.db")


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(_DB_PATH)


def ensure_tables():
    with _conn() as db:
        db.executescript("""
            DROP TABLE IF EXISTS vision;
            CREATE TABLE vision (
                id                INTEGER PRIMARY KEY,
                pos1_item_present INTEGER NOT NULL DEFAULT 0,
                pos1_item_status  TEXT    NOT NULL DEFAULT '',
                pos2_item_present INTEGER NOT NULL DEFAULT 0,
                pos2_item_status  TEXT    NOT NULL DEFAULT '',
                pos3_item_present INTEGER NOT NULL DEFAULT 0,
                pos3_item_status  TEXT    NOT NULL DEFAULT '',
                pos4_item_present INTEGER NOT NULL DEFAULT 0,
                pos4_item_status  TEXT    NOT NULL DEFAULT '',
                pos5_item_present INTEGER NOT NULL DEFAULT 0,
                pos5_item_status  TEXT    NOT NULL DEFAULT ''
            );

            DROP TABLE IF EXISTS robot;
            CREATE TABLE robot (
                id             INTEGER PRIMARY KEY,
                curr_pos       INTEGER,
                next_pos       INTEGER,
                joints         TEXT    NOT NULL DEFAULT '[]',
                pose           TEXT    NOT NULL DEFAULT ''
            );

            DROP TABLE IF EXISTS vision_calculated;
            CREATE TABLE vision_calculated (
                id                INTEGER PRIMARY KEY,
                pos1_item_present INTEGER NOT NULL DEFAULT 0,
                pos1_item_status  TEXT    NOT NULL DEFAULT '',
                pos2_item_present INTEGER NOT NULL DEFAULT 0,
                pos2_item_status  TEXT    NOT NULL DEFAULT '',
                pos3_item_present INTEGER NOT NULL DEFAULT 0,
                pos3_item_status  TEXT    NOT NULL DEFAULT '',
                pos4_item_present INTEGER NOT NULL DEFAULT 0,
                pos4_item_status  TEXT    NOT NULL DEFAULT '',
                pos5_item_present INTEGER NOT NULL DEFAULT 0,
                pos5_item_status  TEXT    NOT NULL DEFAULT ''
            );
        """)


def write_vision(states: dict[int, bool], statuses: dict[int, str] | None = None):
    s = statuses or {}
    with _conn() as db:
        db.execute(
            """INSERT INTO vision (id,
                pos1_item_present, pos1_item_status,
                pos2_item_present, pos2_item_status,
                pos3_item_present, pos3_item_status,
                pos4_item_present, pos4_item_status,
                pos5_item_present, pos5_item_status
            ) VALUES (1, ?,?, ?,?, ?,?, ?,?, ?,?)
            ON CONFLICT(id) DO UPDATE SET
                pos1_item_present = excluded.pos1_item_present,
                pos1_item_status  = excluded.pos1_item_status,
                pos2_item_present = excluded.pos2_item_present,
                pos2_item_status  = excluded.pos2_item_status,
                pos3_item_present = excluded.pos3_item_present,
                pos3_item_status  = excluded.pos3_item_status,
                pos4_item_present = excluded.pos4_item_present,
                pos4_item_status  = excluded.pos4_item_status,
                pos5_item_present = excluded.pos5_item_present,
                pos5_item_status  = excluded.pos5_item_status""",
            (
                int(states.get(1, False)), s.get(1, ""),
                int(states.get(2, False)), s.get(2, ""),
                int(states.get(3, False)), s.get(3, ""),
                int(states.get(4, False)), s.get(4, ""),
                int(states.get(5, False)), s.get(5, ""),
            ),
        )


def read_vision_calculated() -> dict:
    """Return the current singleton row from vision_calculated, or empty dict."""
    try:
        with _conn() as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM vision_calculated WHERE id = 1").fetchone()
            return dict(row) if row else {}
    except Exception:
        return {}


def write_vision_calculated(states: dict):
    """Write the post-rules merged vision state."""
    with _conn() as db:
        db.execute(
            """INSERT INTO vision_calculated (id,
                pos1_item_present, pos1_item_status,
                pos2_item_present, pos2_item_status,
                pos3_item_present, pos3_item_status,
                pos4_item_present, pos4_item_status,
                pos5_item_present, pos5_item_status
            ) VALUES (1, ?,?, ?,?, ?,?, ?,?, ?,?)
            ON CONFLICT(id) DO UPDATE SET
                pos1_item_present = excluded.pos1_item_present,
                pos1_item_status  = excluded.pos1_item_status,
                pos2_item_present = excluded.pos2_item_present,
                pos2_item_status  = excluded.pos2_item_status,
                pos3_item_present = excluded.pos3_item_present,
                pos3_item_status  = excluded.pos3_item_status,
                pos4_item_present = excluded.pos4_item_present,
                pos4_item_status  = excluded.pos4_item_status,
                pos5_item_present = excluded.pos5_item_present,
                pos5_item_status  = excluded.pos5_item_status""",
            (
                int(bool(states.get("pos1_item_present"))), states.get("pos1_item_status", ""),
                int(bool(states.get("pos2_item_present"))), states.get("pos2_item_status", ""),
                int(bool(states.get("pos3_item_present"))), states.get("pos3_item_status", ""),
                int(bool(states.get("pos4_item_present"))), states.get("pos4_item_status", ""),
                int(bool(states.get("pos5_item_present"))), states.get("pos5_item_status", ""),
            ),
        )


def write_robot(curr_pos: int | None, next_pos: int | None, joints: list[int], pose: str):
    with _conn() as db:
        db.execute(
            """INSERT INTO robot (id, curr_pos, next_pos, joints, pose)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                curr_pos = excluded.curr_pos,
                next_pos = excluded.next_pos,
                joints   = excluded.joints,
                pose     = excluded.pose""",
            (curr_pos, next_pos, json.dumps(joints), pose),
        )
