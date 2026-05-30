import pg from 'pg';
import { getDatabaseUrl, describeDatabaseUrl } from './load-env.mjs';

const url = getDatabaseUrl();
const info = describeDatabaseUrl(url);
if (!info.ok) {
  console.log('CONNECT_FAIL');
  console.log('message:', info.error);
  console.log('hint: Put DATABASE_URL in services/twin/.env (not your-url-here in PowerShell)');
  console.log('hint: If you set $env:DATABASE_URL earlier, run: Remove-Item Env:DATABASE_URL');
  process.exit(1);
}

console.log(`Connecting to ${info.host}:${info.port}/${info.database} …`);

const client = new pg.Client({
  connectionString: url,
  connectionTimeoutMillis: 10000,
});

try {
  await client.connect();
  const v = await client.query('SELECT version()');
  const db = await client.query('SELECT current_database(), current_user');
  const tables = await client.query(`
    SELECT table_schema, table_name, table_type
    FROM information_schema.tables
    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY table_schema, table_name
  `);

  console.log('CONNECT_OK');
  console.log('database:', db.rows[0].current_database);
  console.log('user:', db.rows[0].current_user);
  console.log('version:', v.rows[0].version.split(' ').slice(0, 2).join(' '));
  console.log('tables:', tables.rowCount);
  for (const r of tables.rows) {
    console.log(` - ${r.table_schema}.${r.table_name} (${r.table_type})`);
  }

  if (tables.rowCount > 0) {
    const first = tables.rows[0];
    const sample = await client.query(
      `SELECT * FROM "${first.table_schema}"."${first.table_name}" LIMIT 3`,
    );
    console.log(`sample from ${first.table_schema}.${first.table_name}:`, sample.rowCount, 'rows');
    if (sample.rows[0]) {
      console.log('columns:', Object.keys(sample.rows[0]).join(', '));
    }
  }

  await client.end();
} catch (e) {
  console.log('CONNECT_FAIL');
  console.log('code:', e.code);
  console.log('message:', e.message);
  if (e.code === 'ENOTFOUND') {
    console.log('hint: Host not found — check DATABASE_URL in .env');
    console.log('hint: Clear stale shell var: Remove-Item Env:DATABASE_URL');
    console.log(`hint: Parsed host was "${info.host}" — should be your DB IP (e.g. 49.13.213.49)`);
  }
  process.exit(1);
}
