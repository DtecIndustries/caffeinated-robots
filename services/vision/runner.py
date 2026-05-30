"""
Autonomous robot runner — polls faulty_parts and dispatches actions.

Decision rules (checked in priority order):
  1. resolution='go',    robot_acked=false  → 5_4  (holding → packaging)
  2. resolution='no_go', robot_acked=false  → 5_R  (holding → reject)
  3. resolution=NULL,    status='open'      → 3_5  (QC station → holding)

Only ONE action runs at a time. The loop waits for the routine to finish
before checking again — subprocess.run() is blocking.

Usage:
    uv run runner.py
"""
import os
import sys
import time
import subprocess
import psycopg
from dotenv import load_dotenv

load_dotenv()

_DB_URL      = os.getenv("DB_URL", "")
_POLL_S      = float(os.getenv("RUNNER_POLL_INTERVAL", 5.0))
_PYTHON      = sys.executable   # same uv-managed interpreter


def _query(conn) -> tuple[str, int] | None:
    """
    Return (action, record_id) for the highest-priority pending job,
    or None if nothing to do.
    """
    # Priority 1 & 2: items already in holding awaiting a decision
    row = conn.execute("""
        SELECT id, resolution
        FROM faulty_parts
        WHERE robot_acked = false
          AND resolution IN ('go', 'no_go')
        ORDER BY detected_at ASC
        LIMIT 1
    """).fetchone()

    if row:
        action = "5_4" if row[1] == "go" else "5_R"
        return action, row[0]

    # Priority 3: new open items not yet moved to holding
    row = conn.execute("""
        SELECT id
        FROM faulty_parts
        WHERE robot_acked = false
          AND resolution IS NULL
          AND status = 'open'
        ORDER BY detected_at ASC
        LIMIT 1
    """).fetchone()

    if row:
        return "3_5", row[0]

    return None


def _mark_in_holding(conn):
    """After 3_5 completes, mark open unresolved items as 'in_holding'."""
    conn.execute("""
        UPDATE faulty_parts
        SET status = 'in_holding'
        WHERE robot_acked = false
          AND resolution IS NULL
          AND status = 'open'
    """)
    conn.commit()


def _run_action(action: str):
    print(f"\n[runner] Dispatching: {action}")
    result = subprocess.run(
        ["uv", "run", "routine.py", action],
        cwd=os.path.dirname(__file__),
    )
    if result.returncode != 0:
        print(f"[runner] ⚠  routine.py exited with code {result.returncode}")
    return result.returncode == 0


def main():
    if not _DB_URL:
        print("[runner] DB_URL not set — nothing to do.")
        sys.exit(1)

    print(f"[runner] Started. Polling every {_POLL_S}s.")

    while True:
        try:
            with psycopg.connect(_DB_URL) as conn:
                job = _query(conn)

            if job:
                action, record_id = job
                print(f"[runner] Job found — record #{record_id}, action: {action}")
                ok = _run_action(action)

                if ok and action == "3_5":
                    with psycopg.connect(_DB_URL) as conn:
                        _mark_in_holding(conn)
                        print(f"[runner] Marked items as in_holding.")
            else:
                print(f"[runner] Nothing to do.", end="\r")

        except Exception as e:
            print(f"[runner] Error: {e}")

        time.sleep(_POLL_S)


if __name__ == "__main__":
    main()
