import psycopg
from config import DB_URL


class StationWriter:
    def __init__(self):
        self._conn: psycopg.AsyncConnection | None = None

    async def connect(self):
        self._conn = await psycopg.AsyncConnection.connect(DB_URL)
        await self._ensure_table()
        await self._ensure_faulty_parts()

    async def _ensure_table(self):
        async with self._conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS production_line (
                    id                SERIAL PRIMARY KEY,
                    pos1_item_present BOOLEAN NOT NULL,
                    pos1_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    pos2_item_present BOOLEAN NOT NULL,
                    pos2_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    pos3_item_present BOOLEAN NOT NULL,
                    pos3_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    pos4_item_present BOOLEAN NOT NULL,
                    pos4_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    pos5_item_present BOOLEAN NOT NULL DEFAULT false,
                    pos5_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    robot_curr_pos    INTEGER,
                    robot_next_pos    INTEGER,
                    robot_joints      INTEGER[] NOT NULL DEFAULT '{}',
                    robot_pose        VARCHAR(128) NOT NULL DEFAULT ''
                )
            """)
            # Migrate existing tables
            await cur.execute("""
                ALTER TABLE production_line
                    ADD COLUMN IF NOT EXISTS pos5_item_present BOOLEAN NOT NULL DEFAULT false,
                    ADD COLUMN IF NOT EXISTS pos5_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS robot_pose        VARCHAR(128) NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS robot_joints      INTEGER[] NOT NULL DEFAULT '{}'
            """)
            # Replace old array-typed robot_curr_pos/next_pos with INTEGER
            await cur.execute("""
                ALTER TABLE production_line
                    DROP COLUMN IF EXISTS robot_curr_pos,
                    DROP COLUMN IF EXISTS robot_next_pos
            """)
            await cur.execute("""
                ALTER TABLE production_line
                    ADD COLUMN IF NOT EXISTS robot_curr_pos INTEGER,
                    ADD COLUMN IF NOT EXISTS robot_next_pos INTEGER
            """)
        await self._conn.commit()

    async def _ensure_faulty_parts(self):
        async with self._conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS faulty_parts (
                    id                 BIGSERIAL PRIMARY KEY,
                    detected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    station_pos        INTEGER,
                    fault              TEXT NOT NULL,
                    confidence         REAL,
                    image_b64          TEXT,
                    status             TEXT NOT NULL DEFAULT 'open',
                    discord_message_id TEXT,

                    resolution         TEXT,
                    resolution_note    TEXT,
                    resolved_by        TEXT DEFAULT NULL,
                    resolved_at        TIMESTAMPTZ DEFAULT NULL,

                    robot_acked        BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            # image_b64 holds a base64-encoded JPEG of the camera frame at detect time.
            await cur.execute(
                "ALTER TABLE faulty_parts ADD COLUMN IF NOT EXISTS image_b64 TEXT"
            )
        await self._conn.commit()

    async def record_fault(
        self,
        station_pos: int,
        fault: str,
        image_b64: str | None,
        confidence: float | None = None,
    ) -> int:
        """Insert one open faulty-part ticket with the captured frame. Returns its id."""
        async with self._conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO faulty_parts (station_pos, fault, confidence, image_b64, status)
                   VALUES (%s, %s, %s, %s, 'open')
                   RETURNING id""",
                (station_pos, fault, confidence, image_b64),
            )
            row = await cur.fetchone()
        await self._conn.commit()
        return row[0]

    async def write(self, states: dict[int, bool], statuses: dict[int, str] | None = None):
        """Update only station detection columns. Never touches robot_* fields."""
        s = statuses or {}
        async with self._conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO production_line (id,
                    pos1_item_present, pos1_item_status,
                    pos2_item_present, pos2_item_status,
                    pos3_item_present, pos3_item_status,
                    pos4_item_present, pos4_item_status,
                    pos5_item_present, pos5_item_status
                ) VALUES (1, %s,%s, %s,%s, %s,%s, %s,%s, %s,%s)
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
                    pos5_item_status  = EXCLUDED.pos5_item_status""",
                (
                    states.get(1, False), s.get(1, ""),
                    states.get(2, False), s.get(2, ""),
                    states.get(3, False), s.get(3, ""),
                    states.get(4, False), s.get(4, ""),
                    states.get(5, False), s.get(5, ""),
                ),
            )
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
