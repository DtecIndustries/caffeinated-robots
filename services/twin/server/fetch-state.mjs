import pg from 'pg';
import { getDatabaseUrl, describeDatabaseUrl } from '../scripts/load-env.mjs';
import { mapProductionLineToWorldState } from './map-state.mjs';

const { Pool } = pg;

let pool;

function getPool() {
  if (pool) return pool;
  const url = getDatabaseUrl();
  const info = describeDatabaseUrl(url);
  if (!info.ok) {
    throw new Error(info.error);
  }
  pool = new Pool({ connectionString: url, max: 4 });
  return pool;
}

/** Read-only: latest row from production_line (pos1–pos5) */
export async function fetchWorldStateFromDb() {
  const db = getPool();

  const result = await db.query(
    `SELECT id,
            pos1_item_present,
            pos1_item_status,
            pos2_item_present,
            pos2_item_status,
            pos3_item_present,
            pos3_item_status,
            pos4_item_present,
            pos4_item_status,
            pos5_item_present,
            pos5_item_status,
            robot_pose,
            robot_joints,
            robot_curr_pos,
            robot_next_pos,
            created_at
     FROM production_line
     ORDER BY id DESC
     LIMIT 1`,
  );

  return mapProductionLineToWorldState(result.rows[0] ?? null);
}
