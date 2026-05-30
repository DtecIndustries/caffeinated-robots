import pg from 'pg';
import { getDatabaseUrl } from './load-env.mjs';

const url = process.env.DATABASE_URL || getDatabaseUrl();
if (!url || url.includes('USER:PASSWORD')) {
  console.error('Copy .env.example to .env and set DATABASE_URL');
  process.exit(1);
}

const tables = [
  'production_line',
  'stations',
  'products',
  'detections',
  'decisions',
  'line_overview',
];

const client = new pg.Client({ connectionString: url });
await client.connect();

for (const t of tables) {
  const cols = await client.query(
    `SELECT column_name, data_type
     FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = $1
     ORDER BY ordinal_position`,
    [t],
  );
  let count = { rows: [{ n: '?' }] };
  try {
    count = await client.query(`SELECT COUNT(*)::int AS n FROM public.${t}`);
  } catch {
    /* view may differ */
  }
  console.log(`--- ${t} (${count.rows[0].n} rows)`);
  for (const r of cols.rows) {
    console.log(`    ${r.column_name}: ${r.data_type}`);
  }
}

await client.end();
