"""Postgres access for the dashboards.

Connects directly via DB_URL (the same straw-backed database the vision service
writes detections to). All defect logic lives in one SQL query so the overview
count and the operator detail view can never disagree about what "faulty" means.
"""

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from config import DB_URL

_pool: AsyncConnectionPool | None = None

# A product is faulty if it has a most-recent failed QC detection, OR its status
# is rejected/hold. This single CTE backs every view.
_FAULTY_SQL = """
WITH failed AS (
    SELECT DISTINCT ON (product_id)
        product_id, ts, station_id, confidence, image_url, payload
    FROM detections
    WHERE verdict = 'fail'
    ORDER BY product_id, ts DESC
)
SELECT
    p.id                                        AS product_id,
    p.label                                     AS label,
    p.status::text                              AS product_status,
    p.metadata->>'sku'                          AS sku,
    p.metadata->>'batch'                        AS batch,
    COALESCE(p.current_station, f.station_id)   AS station_id,
    s.name                                      AS station_name,
    s.position                                  AS station_position,
    (f.product_id IS NOT NULL)                  AS has_failed_detection,
    f.ts                                        AS failed_at,
    f.confidence                                AS confidence,
    f.image_url                                 AS image_url,
    f.payload->>'defect_code'                   AS defect_code,
    COALESCE(f.payload->>'defect', '')          AS defect,
    COALESCE(f.payload->>'severity', '')        AS severity,
    COALESCE(f.payload->>'reason', '')          AS reason,
    COALESCE(f.ts, p.last_seen)                 AS detected_at
FROM products p
LEFT JOIN failed   f ON f.product_id = p.id
LEFT JOIN stations s ON s.id = COALESCE(p.current_station, f.station_id)
WHERE f.product_id IS NOT NULL
   OR p.status IN ('rejected', 'hold')
"""


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
    sev = (row.get("severity") or "").lower()
    if sev == "major" or row.get("product_status") == "rejected":
        return 0
    if sev == "minor" or row.get("product_status") == "hold":
        return 1
    return 2


async def list_defects() -> list[dict]:
    """Every currently-faulty part, most severe / most recent first."""
    rows = await _fetch(_FAULTY_SQL)
    rows.sort(key=lambda r: (_severity_rank(r), -(r["detected_at"].timestamp())))
    return rows


async def get_defect(product_id: int) -> dict | None:
    rows = await _fetch(_FAULTY_SQL + " AND p.id = %(pid)s", {"pid": product_id})
    return rows[0] if rows else None


async def get_summary() -> dict:
    rows = await list_defects()
    by_station: dict[str, int] = {}
    by_severity = {"major": 0, "minor": 0, "other": 0}
    for r in rows:
        st = r.get("station_name") or "unknown"
        by_station[st] = by_station.get(st, 0) + 1
        sev = (r.get("severity") or "").lower()
        if sev not in ("major", "minor"):
            # Backfill from status the same way the dashboards do.
            sev = {"rejected": "major", "hold": "minor"}.get(r.get("product_status"), "other")
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return {
        "faulty_count": len(rows),
        "by_station": by_station,
        "by_severity": by_severity,
    }


async def get_line() -> list[dict]:
    """Stations ordered by their position on the line."""
    return await _fetch(
        "SELECT id, name, position, status FROM stations ORDER BY position"
    )


async def get_defect_image_meta(product_id: int) -> dict | None:
    """Lightweight check for the latest captured image of a product.

    Returns the content type and capture time WITHOUT loading the image bytes,
    so the polled detail endpoint stays cheap. Returns None when none exists.
    """
    rows = await _fetch(
        "SELECT content_type, captured_at FROM defect_images "
        "WHERE product_id = %(pid)s ORDER BY captured_at DESC LIMIT 1",
        {"pid": product_id},
    )
    return rows[0] if rows else None


async def get_defect_image(product_id: int) -> tuple[bytes, str] | None:
    """The latest captured image bytes + content type for a product, or None."""
    rows = await _fetch(
        "SELECT image, content_type FROM defect_images "
        "WHERE product_id = %(pid)s ORDER BY captured_at DESC LIMIT 1",
        {"pid": product_id},
    )
    if not rows:
        return None
    return bytes(rows[0]["image"]), rows[0]["content_type"]
