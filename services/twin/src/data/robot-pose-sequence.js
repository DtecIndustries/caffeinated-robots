import { JOINT_SCALE } from './positions.js';
import { LINE_LAYOUT, stationPosition } from '../scene/line-layout.js';

/** Calibrated pick poses (joints ×1000) — station 4 / packaging in the real rig. */
export const ROBOT_POSE_SEQUENCE = [
  {
    name: 'home|part_false|gripper_closed',
    positions: [2052, 1132, 2574, 3011, 2069, 1816],
  },
  {
    name: 'above|part_false|gripper_closed',
    positions: [2060, 1955, 1907, 2865, 2069, 1825],
    station: 0,
  },
  {
    name: 'above|part_false|gripper_open',
    positions: [2060, 1955, 1907, 2865, 2069, 2603],
    station: 4,
  },
  {
    name: 'lower|part_false|gripper_open',
    positions: [2045, 2301, 1951, 2778, 2069, 2603],
    station: 4,
  },
  {
    name: 'lower|part_true|gripper_closed',
    positions: [2045, 2301, 1951, 2778, 2069, 2070],
    station: 4,
  },
  {
    name: 'above|part_true|gripper_closed',
    positions: [2052, 1955, 1907, 2865, 2069, 2070],
    station: 4,
  },
  {
    name: 'home|part_true|gripper_closed',
    positions: [2052, 1131, 2573, 3011, 2069, 2070],
    station: 0,
  },
];

/** Ordered keyframes for one pick cycle (ends lifted, ready to carry). */
export const PICK_KEYFRAME_NAMES = [
  'home|part_false|gripper_closed',
  'above|part_false|gripper_closed',
  'above|part_false|gripper_open',
  'lower|part_false|gripper_open',
  'lower|part_true|gripper_closed',
  'above|part_true|gripper_closed',
];

/** Slot used when the real poses were recorded. */
const REFERENCE_PICK_SLOT = 4;

const poseMap = new Map(
  ROBOT_POSE_SEQUENCE.map((p) => [p.name, p.positions]),
);

export function parseRecordedJoints(raw) {
  if (!raw?.length) return null;
  const pose = raw.map((v) => Number(v) / JOINT_SCALE);
  pose[1] = 0;
  return pose;
}

export function poseJointsByName(name) {
  const raw = poseMap.get(name);
  return raw ? parseRecordedJoints(raw) : null;
}

function baseSwivelForSlot(slot) {
  const target = stationPosition(slot);
  if (!target) return null;
  const { x: bx, z: bz } = LINE_LAYOUT.robot;
  return Math.atan2(target.x - bx, target.z - bz);
}

function adjustBaseForSlot(joints, fromSlot) {
  if (!joints || fromSlot == null) return joints;
  const ref = baseSwivelForSlot(REFERENCE_PICK_SLOT);
  const at = baseSwivelForSlot(fromSlot);
  if (ref == null || at == null) return joints;
  const out = joints.slice();
  out[0] = joints[0] + (at - ref);
  out[1] = 0;
  return out;
}

const PICK_FRAMES = PICK_KEYFRAME_NAMES.map((name) => poseJointsByName(name)).filter(
  Boolean,
);

/**
 * @param {number} progress 0–1 through the pick cycle
 * @param {number|null} fromSlot
 * @returns {number[]|null}
 */
export function resolvePickPose(progress, fromSlot) {
  if (PICK_FRAMES.length < 2) return null;

  const t = Math.max(0, Math.min(1, progress));
  const segCount = PICK_FRAMES.length - 1;
  const scaled = t * segCount;
  const idx = Math.min(segCount - 1, Math.floor(scaled));
  const localT = scaled - idx;

  const from = adjustBaseForSlot(PICK_FRAMES[idx], fromSlot);
  const to = adjustBaseForSlot(PICK_FRAMES[idx + 1], fromSlot);
  if (!from || !to) return null;

  const out = [];
  for (let i = 0; i < 6; i++) {
    let d = to[i] - from[i];
    while (d > Math.PI) d -= Math.PI * 2;
    while (d < -Math.PI) d += Math.PI * 2;
    out[i] = from[i] + d * localT;
  }
  out[1] = 0;
  return out;
}

export function matchPoseFromDb(poseRaw) {
  const key = String(poseRaw ?? '').trim().toLowerCase();
  if (!key) return null;
  for (const name of poseMap.keys()) {
    if (key === name || key.includes(name)) return poseJointsByName(name);
  }
  return null;
}
