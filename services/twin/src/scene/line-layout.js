import * as THREE from 'three';

const SLOT_COUNT = 4;
/** Compact touching pads — closer centers so the crane reaches all four boxes. */
const PAD = 1.0;

/**
 * Touching pad centers for slots 1–4 (CNC, Assembly, QC, Packaging).
 * Slot 4 (Packaging) is leftmost; slot 1 (CNC) is rightmost.
 */
function buildStationX(padSize) {
  const half = ((SLOT_COUNT - 1) / 2) * padSize;
  return [
    half,
    half - padSize,
    half - 2 * padSize,
    half - 3 * padSize,
  ];
}

const stationX = buildStationX(PAD);

/**
 * Physical line layout (top view, from the crane):
 *
 *   🤖 [Pkg][QC][Asm][CNC]   ← pos4 … pos1 (touching pads, no gaps)
 *    [Reject]               ← pos6, fed from holding only (mirror across row)
 *         [Holding]          ← pos5
 */
const SIDE_BAY_X = stationX[2];
const SIDE_BAY_Z = 1.28;

export const LINE_LAYOUT = {
  padSize: PAD,
  stationX,
  mainRowZ: 0,
  padY: 0.42,
  /** Closer to the crane so the base can slew to it without full arm stretch. */
  holding: { x: SIDE_BAY_X, z: -SIDE_BAY_Z },
  /** Opposite side of holding — same X and |Z| for symmetric reach. */
  reject: { x: SIDE_BAY_X, z: SIDE_BAY_Z },
  /** Set back from the row so inward carries miss the pedestal. */
  robot: { x: stationX[3] - 2.45, y: 0.35, z: 0.48 },
  belt: { length: SLOT_COUNT * PAD, width: PAD, y: 0.35, z: 0 },
  table: { width: 6.2, depth: 5.5, y: 0.32 },
  /** Box footprint on a pad (smaller than pad for clearance). */
  boxFootprint: PAD * 0.82,
  boxHeight: 0.42,
};

export const BOX_TOP_Y = LINE_LAYOUT.padY + LINE_LAYOUT.boxHeight;
export const BOX_CENTER_Y = LINE_LAYOUT.padY + LINE_LAYOUT.boxHeight / 2;
/** Travel between stations — just above box height. */
export const CLAW_HOVER_Y = BOX_TOP_Y + 0.1;
/** Carrying toward Packaging — above the pedestal envelope. */
export const CLAW_CARRY_Y = BOX_TOP_Y + 0.38;
/** Mid-travel arc peak (QC→Pkg) — clears boom/elbow over the base. */
export const CLAW_ARC_PEAK_Y = BOX_TOP_Y + 0.58;
/** Lateral offset while arcing past the crane (world Z). */
export const CARRY_Z_OFFSET = 0.22;
/** Just above the box top — brief step before full pick depth. */
export const CLAW_APPROACH_Y = BOX_TOP_Y + 0.02;

export const STATION_LABELS = ['CNC', 'Assembly', 'QC', 'Packaging'];

export function stationPosition(slot) {
  if (slot >= 1 && slot <= 4) {
    return {
      x: LINE_LAYOUT.stationX[slot - 1],
      y: LINE_LAYOUT.padY,
      z: LINE_LAYOUT.mainRowZ,
    };
  }
  if (slot === 5) {
    return {
      x: LINE_LAYOUT.holding.x,
      y: LINE_LAYOUT.padY,
      z: LINE_LAYOUT.holding.z,
    };
  }
  if (slot === 6) {
    return {
      x: LINE_LAYOUT.reject.x,
      y: LINE_LAYOUT.padY,
      z: LINE_LAYOUT.reject.z,
    };
  }
  return null;
}

export function holdingVector() {
  return new THREE.Vector3(
    LINE_LAYOUT.holding.x,
    LINE_LAYOUT.padY,
    LINE_LAYOUT.holding.z,
  );
}

export function rejectVector() {
  return new THREE.Vector3(
    LINE_LAYOUT.reject.x,
    LINE_LAYOUT.padY,
    LINE_LAYOUT.reject.z,
  );
}

function beltExtents() {
  const xs = LINE_LAYOUT.stationX;
  const min = Math.min(...xs);
  const max = Math.max(...xs);
  const half = LINE_LAYOUT.padSize / 2;
  return { min: min - half, max: max + half, span: max - min };
}

/** Normalized belt coordinate 0–1 (0 = Packaging, 1 = CNC). */
export function beltNormalizedForSlot(slot) {
  if (slot < 1 || slot > 4) return 0;
  const { min, max } = beltExtents();
  const span = max - min;
  return span > 0 ? (LINE_LAYOUT.stationX[slot - 1] - min) / span : 0;
}

/** World X on the belt for a slot pad center. */
export function beltXForSlot(slot) {
  if (slot < 1 || slot > 4) return 0;
  return LINE_LAYOUT.stationX[slot - 1];
}

/** Belt X for normalized position t (0 = Packaging, 1 = CNC). */
export function beltXFromPosition(t) {
  const { min, max } = beltExtents();
  return min + t * (max - min);
}
