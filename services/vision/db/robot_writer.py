import os
import psycopg
from dotenv import load_dotenv
from db.sqlite_client import write_robot

load_dotenv()

_DB_URL = os.getenv("DB_URL", "")


def update_robot_state(
    curr_pos: int | None,
    next_pos: int | None,
    joints: list[int],
    pose: str,
):
    # Always write to local SQLite
    try:
        write_robot(curr_pos=curr_pos, next_pos=next_pos, joints=joints, pose=pose)
    except Exception as e:
        print(f"  [local] {e}")

    # Write to PostgreSQL if configured
    if not _DB_URL:
        return
    try:
        with psycopg.connect(_DB_URL) as conn:
            conn.execute(
                """UPDATE production_line SET
                    robot_curr_pos = %s,
                    robot_next_pos = %s,
                    robot_joints   = %s,
                    robot_pose     = %s
                WHERE id = 1""",
                (curr_pos, next_pos, joints, pose),
            )
            conn.commit()
    except Exception as e:
        print(f"  [db] {e}")


def mark_robot_handled() -> int:
    """Mark the no-go faulty parts the robot just pulled off the line as handled.

    Records the robot-handled event on the faulty_parts row (robot_acked +
    robot_acked_at) so those defects drop off the dashboard. Returns how many
    rows were acked.
    """
    if not _DB_URL:
        return 0
    try:
        with psycopg.connect(_DB_URL) as conn:
            cur = conn.execute(
                """UPDATE faulty_parts
                   SET robot_acked = TRUE, robot_acked_at = now()
                   WHERE resolution = 'no_go' AND robot_acked = FALSE""",
            )
            conn.commit()
            return cur.rowcount
    except Exception as e:
        print(f"  [db] {e}")
        return 0
