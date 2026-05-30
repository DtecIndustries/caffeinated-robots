"""Postgres access for the dashboards.

Connects directly via DB_URL (the same database the vision service writes to).
The vision pipeline records every defect as a row in `faulty_parts` — that is
the single source of truth for the dashboards. A part is "faulty" (still needs
attention) while its status is anything other than `resolved`.

The camera snapshot lives in `faulty_parts.image_b64` as a base64-encoded JPEG;
the dashboard decodes it on demand and serves the raw bytes.
"""

import base64
import binascii

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from config import DB_URL

_pool: AsyncConnectionPool | None = None

# Defects still live on the line, newest first within the Python-side severity
# sort. station_pos joins to the stations layout.
#
# The supervisor resolves tickets over Discord (GO = false positive, the part
# continues; NO-GO = the part is pulled and the line is cleared). Either way a
# resolved ticket is off the line. And once the *latest* ticket (highest id) is
# resolved, the whole batch is considered handled — the line is available again
# and EVERY remaining ticket drops off. So a defect shows only while it is
# unresolved AND the most recent ticket is still unresolved.
_FAULTY_SQL = """
SELECT
    fp.id                                           AS defect_id,
    fp.detected_at                                  AS detected_at,
    fp.station_pos                                  AS station_pos,
    fp.fault                                        AS fault,
    fp.confidence                                   AS confidence,
    fp.status                                       AS status,
    fp.resolution                                   AS resolution,
    s.id                                            AS station_id,
    s.name                                          AS station_name,
    (fp.image_b64 IS NOT NULL AND length(fp.image_b64) > 0) AS has_image
FROM faulty_parts fp
LEFT JOIN stations s ON s.position = fp.station_pos
WHERE fp.resolution IS NULL
  AND fp.robot_acked = FALSE
  AND (SELECT resolution FROM faulty_parts ORDER BY id DESC LIMIT 1) IS NULL
"""

# The vision line has five physical positions even though `stations` only names
# the first four.
LINE_LENGTH = 5


async def connect():
    global _pool
    if not DB_URL:
        raise RuntimeError("DB_URL is not set — configure it in services/dashboard/.env")
    _pool = AsyncConnectionPool(DB_URL, min_size=1, max_size=4, open=False)
    await _pool.open()


async def close():
    if _pool:
        await _pool.close()


def configured() -> bool:
    return bool(DB_URL)


async def _fetch(sql: str, params: dict | None = None) -> list[dict]:
    async with _pool.connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(sql, params or {})
            return await cur.fetchall()


def _severity_rank(row: dict) -> int:
    c = row.get("confidence")
    if c is not None and c >= 0.85:
        return 0  # major
    return 1      # minor


async def list_defects() -> list[dict]:
    """Every currently-faulty part, most severe / most recent first."""
    rows = await _fetch(_FAULTY_SQL)
    rows.sort(key=lambda r: (_severity_rank(r), -r["detected_at"].timestamp()))
    return rows


async def get_defect(defect_id: int) -> dict | None:
    rows = await _fetch(_FAULTY_SQL + " AND fp.id = %(id)s", {"id": defect_id})
    return rows[0] if rows else None


async def get_summary() -> dict:
    rows = await list_defects()
    by_station: dict[str, int] = {}
    by_severity = {"major": 0, "minor": 0}
    for r in rows:
        st = r.get("station_name") or f"station {r['station_pos']}"
        by_station[st] = by_station.get(st, 0) + 1
        by_severity["major" if _severity_rank(r) == 0 else "minor"] += 1
    # Everything shown is unresolved → the line is on hold whenever any show.
    return {
        "faulty_count": len(rows),
        "awaiting_resolution": len(rows),
        "on_hold": len(rows) > 0,
        "by_station": by_station,
        "by_severity": by_severity,
    }


async def get_line() -> list[dict]:
    """The line as positions 1..LINE_LENGTH, named from `stations` where known."""
    rows = await _fetch("SELECT id, name, position, status FROM stations ORDER BY position")
    by_pos = {r["position"]: r for r in rows}
    max_pos = max([LINE_LENGTH, *by_pos.keys()])
    line = []
    for p in range(1, max_pos + 1):
        s = by_pos.get(p)
        line.append({
            "id": s["id"] if s else None,
            "name": s["name"] if s else f"station {p}",
            "position": p,
            "status": s["status"] if s else "idle",
        })
    return line


async def list_history(limit: int = 50) -> list[dict]:
    """Resolved defects, most recently resolved first — the defect history."""
    return await _fetch(
        """
        SELECT fp.id                  AS defect_id,
               fp.detected_at         AS detected_at,
               fp.station_pos         AS station_pos,
               fp.fault               AS fault,
               fp.resolution          AS resolution,
               fp.resolution_note     AS resolution_note,
               fp.resolved_by         AS resolved_by,
               fp.resolved_at         AS resolved_at,
               fp.robot_acked         AS robot_acked,
               s.name                 AS station_name,
               (fp.image_b64 IS NOT NULL AND length(fp.image_b64) > 0) AS has_image
        FROM faulty_parts fp
        LEFT JOIN stations s ON s.position = fp.station_pos
        WHERE fp.resolution IS NOT NULL
        ORDER BY COALESCE(fp.resolved_at, fp.detected_at) DESC
        LIMIT %(lim)s
        """,
        {"lim": limit},
    )


def _decode_image(image_b64: str | None) -> tuple[bytes, str] | None:
    """Decode a base64 image and sniff its type. None if absent or not a real image.

    Guards against the legacy placeholder rows whose image_b64 isn't a valid
    JPEG/PNG — we'd rather show no image than a broken one.
    """
    if not image_b64:
        return None
    try:
        data = base64.b64decode(image_b64, validate=False)
    except (binascii.Error, ValueError):
        return None
    if data[:3] == b"\xff\xd8\xff":
        return data, "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return data, "image/png"
    return None


async def get_defect_image_meta(defect_id: int) -> dict | None:
    """Whether a real captured image exists for this defect, without serving it."""
    rows = await _fetch(
        "SELECT image_b64, detected_at FROM faulty_parts WHERE id = %(id)s", {"id": defect_id}
    )
    if not rows:
        return None
    decoded = _decode_image(rows[0]["image_b64"])
    if not decoded:
        return None
    return {"content_type": decoded[1], "captured_at": rows[0]["detected_at"]}


async def get_defect_image(defect_id: int) -> tuple[bytes, str] | None:
    """The captured image bytes + content type for a defect, or None."""
    rows = await _fetch(
        "SELECT image_b64 FROM faulty_parts WHERE id = %(id)s", {"id": defect_id}
    )
    if not rows:
        return None
    return _decode_image(rows[0]["image_b64"])
