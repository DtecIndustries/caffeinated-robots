import pg from 'pg';
import { getDatabaseUrl } from './load-env.mjs';

const c = new pg.Client({ connectionString: getDatabaseUrl() });
await c.connect();
const cols = await c.query(
  `SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'production_line'
   ORDER BY ordinal_position`,
);
console.log('production_line columns:');
for (const r of cols.rows) {
  console.log(`  ${r.column_name}: ${r.data_type}`);
}
const row = await c.query('SELECT * FROM production_line ORDER BY id DESC LIMIT 1');
console.log('\nlatest row sample:');
console.log(JSON.stringify(row.rows[0], null, 2));
await c.end();
