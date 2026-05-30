/** production_line slot index (1–5) → twin station id */
export const SLOT_TO_STATION = {
  1: 'cnc',
  2: 'assembly',
  3: 'qc',
  4: 'packaging',
  5: 'holding',
  6: 'reject',
};

export const SLOT_LABELS = {
  0: 'Home',
  1: 'CNC',
  2: 'Assembly',
  3: 'QC',
  4: 'Packaging',
  5: 'Holding',
  6: 'Reject',
};

/** Joint values from DB are stored ×1000 (e.g. 2051 → 2.051 rad). */
export const JOINT_SCALE = 1000;

/** Parse robot_curr_pos / robot_next_pos (integer slot 0–5). 0 = home. */
export function parseRobotSlot(value) {
  if (value == null || value === '') return null;
  const n = Number(value);
  if (!Number.isInteger(n) || n < 0 || n > 6) return null;
  return n === 0 ? null : n;
}

/** @deprecated use parseRobotSlot — accepts legacy integer[] with one element */
export function parseRobotPosSlot(arr) {
  if (Array.isArray(arr)) {
    if (arr.length === 0) return null;
    return parseRobotSlot(arr[0]);
  }
  return parseRobotSlot(arr);
}

/** Parse robot_joints integer[6] as joint angles (radians). */
export function parseRobotJoints(arr) {
  if (arr == null) return null;
  const list = Array.isArray(arr) ? arr : [];
  if (list.length < 6) return null;

  const nums = list.slice(0, 6).map((v) => Number(v) / JOINT_SCALE);
  if (nums.some((n) => !Number.isFinite(n))) return null;
  return nums;
}

export function jointsDiffer(a, b, epsilon = 0.02) {
  if (!a || !b || a.length < 6 || b.length < 6) return false;
  for (let i = 0; i < 6; i++) {
    if (Math.abs(a[i] - b[i]) > epsilon) return true;
  }
  return false;
}

export function slotToStationId(slot) {
  if (slot == null) return null;
  return SLOT_TO_STATION[slot] ?? null;
}

export function slotFromStationId(stationId) {
  if (!stationId) return null;
  for (const [slot, id] of Object.entries(SLOT_TO_STATION)) {
    if (id === stationId) return Number(slot);
  }
  if (stationId === 'holding') return 5;
  if (stationId === 'reject') return 6;
  return null;
}

export function robotRouteLabel(currSlot, nextSlot, transferring) {
  const label = (n) =>
    n == null ? 'Home' : (SLOT_LABELS[n] ?? `Slot ${n}`);

  if (transferring && nextSlot != null) {
    return `${label(currSlot)} → ${label(nextSlot)}`;
  }
  return label(currSlot ?? nextSlot);
}
