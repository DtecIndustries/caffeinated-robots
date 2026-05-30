export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
export const READ_ONLY_DB = import.meta.env.VITE_READ_ONLY_DB !== 'false';
export const SHOW_DEBUG_PANEL = import.meta.env.VITE_DEBUG_PANEL !== 'false';
export const POLL_MS = Number(import.meta.env.VITE_POLL_MS) || 500;
export const VISION_STREAM_URL =
  import.meta.env.VITE_VISION_STREAM_URL || 'http://localhost:8000/stream';

/** DB mode: always same-origin /api/state (Vite → Postgres). Mock: optional vision /state URL. */
export const STATE_URL = USE_MOCK
  ? import.meta.env.VITE_STATE_URL || 'http://localhost:8000/state'
  : import.meta.env.VITE_DB_STATE_URL || '/api/state';
