import psycopg
from config import DB_URL


class StationWriter:
    def __init__(self):
        self._conn: psycopg.AsyncConnection | None = None

    async def connect(self):
        self._conn = await psycopg.AsyncConnection.connect(DB_URL)
        await self._ensure_table()

    async def _ensure_table(self):
        async with self._conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS production_line (
                    id               SERIAL PRIMARY KEY,
                    pos1_item_present BOOLEAN NOT NULL,
                    pos1_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    pos2_item_present BOOLEAN NOT NULL,
                    pos2_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    pos3_item_present BOOLEAN NOT NULL,
                    pos3_item_status  VARCHAR(128) NOT NULL DEFAULT '',
                    pos4_item_present BOOLEAN NOT NULL,
                    pos4_item_status  VARCHAR(128) NOT NULL DEFAULT ''
                )
            """)
        await self._conn.commit()

    async def write(self, states: dict[int, bool], statuses: dict[int, str] | None = None):
        s = statuses or {}
        async with self._conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO production_line (id,
                    pos1_item_present, pos1_item_status,
                    pos2_item_present, pos2_item_status,
                    pos3_item_present, pos3_item_status,
                    pos4_item_present, pos4_item_status
                ) VALUES (1, %s,%s, %s,%s, %s,%s, %s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    pos1_item_present = EXCLUDED.pos1_item_present,
                    pos1_item_status  = EXCLUDED.pos1_item_status,
                    pos2_item_present = EXCLUDED.pos2_item_present,
                    pos2_item_status  = EXCLUDED.pos2_item_status,
                    pos3_item_present = EXCLUDED.pos3_item_present,
                    pos3_item_status  = EXCLUDED.pos3_item_status,
                    pos4_item_present = EXCLUDED.pos4_item_present,
                    pos4_item_status  = EXCLUDED.pos4_item_status""",
                (
                    states[1], s.get(1, ""),
                    states[2], s.get(2, ""),
                    states[3], s.get(3, ""),
                    states[4], s.get(4, ""),
                ),
            )
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
