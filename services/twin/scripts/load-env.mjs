import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const envPath = resolve(root, '.env');

/** Keys from .env always override the shell (fixes stale $env:DATABASE_URL in PowerShell). */
const FILE_OVERRIDES = new Set(['DATABASE_URL']);

export function loadEnv() {
  if (!existsSync(envPath)) {
    return false;
  }

  const text = readFileSync(envPath, 'utf8');
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (FILE_OVERRIDES.has(key) || !(key in process.env)) {
      process.env[key] = value;
    }
  }
  return true;
}

export function getDatabaseUrl() {
  loadEnv();
  return process.env.DATABASE_URL ?? null;
}

/** Parse host for error messages (never log password). */
export function describeDatabaseUrl(url) {
  if (!url) return { ok: false, error: 'DATABASE_URL is not set' };
  if (url === 'your-url-here' || url.includes('USER:PASSWORD')) {
    return {
      ok: false,
      error:
        'DATABASE_URL is still a placeholder — set the real URL in services/twin/.env',
    };
  }

  try {
    const parsed = new URL(url);
    return {
      ok: true,
      host: parsed.hostname,
      port: parsed.port || '5432',
      database: parsed.pathname.replace(/^\//, '') || '(default)',
    };
  } catch {
    return {
      ok: false,
      error:
        'DATABASE_URL is not a valid URL. Use postgresql://user:pass@host:5432/dbname',
    };
  }
}
