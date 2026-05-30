import * as THREE from 'three';
import {
  LINE_LAYOUT,
} from './line-layout.js';
import { CLAW_CARRY_Y, CLAW_HOVER_Y } from './line-layout.js';

/** Default row travel height (see crane-aim for carry lift toward the base). */
export const CRANE_TRAVEL_Y = CLAW_HOVER_Y;
export { CLAW_CARRY_Y };

export const HOLDING_SLOT = 5;
export const REJECT_SLOT = 6;

/** Base swivel (Y) — forward axis along the four in-line stations. */
export function robotLineYaw() {
  const { x: bx, z: bz } = LINE_LAYOUT.robot;
  const midX =
    (Math.min(...LINE_LAYOUT.stationX) + Math.max(...LINE_LAYOUT.stationX)) / 2;
  return Math.atan2(midX - bx, LINE_LAYOUT.mainRowZ - bz);
}

/** Default yaw facing the main row (+π flips toward stations). */
export const ROBOT_ROW_YAW = robotLineYaw() + Math.PI;

/** @deprecated use ROBOT_ROW_YAW */
export const ROBOT_FIXED_YAW = ROBOT_ROW_YAW;

/** Main row: CNC, Assembly, QC, Packaging. */
export function isMainRowSlot(slot) {
  return slot >= 1 && slot <= 4;
}

export function isHoldingSlot(slot) {
  return slot === HOLDING_SLOT;
}

export function isRejectSlot(slot) {
  return slot === REJECT_SLOT;
}

export function isSideBaySlot(slot) {
  return isHoldingSlot(slot) || isRejectSlot(slot);
}

/** Any animated crane slot (row + holding + reject). */
export function isTransferSlot(slot) {
  return isMainRowSlot(slot) || isSideBaySlot(slot);
}

export function slotWorldXZ(slot) {
  if (isHoldingSlot(slot)) {
    return { x: LINE_LAYOUT.holding.x, z: LINE_LAYOUT.holding.z };
  }
  if (isRejectSlot(slot)) {
    return { x: LINE_LAYOUT.reject.x, z: LINE_LAYOUT.reject.z };
  }
  if (isMainRowSlot(slot)) {
    return {
      x: LINE_LAYOUT.stationX[slot - 1],
      z: LINE_LAYOUT.mainRowZ,
    };
  }
  return { x: 0, z: LINE_LAYOUT.mainRowZ };
}

/** Base Y rotation to face a world target from the robot pedestal. */
export function robotYawForPoint(x, z) {
  const { x: bx, z: bz } = LINE_LAYOUT.robot;
  return Math.atan2(x - bx, z - bz) + Math.PI;
}

export function robotYawForSlot(slot) {
  if (isHoldingSlot(slot)) {
    const h = LINE_LAYOUT.holding;
    return robotYawForPoint(h.x, h.z);
  }
  if (isRejectSlot(slot)) {
    const r = LINE_LAYOUT.reject;
    return robotYawForPoint(r.x, r.z);
  }
  return ROBOT_ROW_YAW;
}

/** Aim point for a slot (grip height). */
export function lineAimForSlot(slot, y = CRANE_TRAVEL_Y) {
  if (isHoldingSlot(slot)) {
    const h = LINE_LAYOUT.holding;
    return new THREE.Vector3(h.x, y, h.z);
  }
  if (isRejectSlot(slot)) {
    const r = LINE_LAYOUT.reject;
    return new THREE.Vector3(r.x, y, r.z);
  }
  if (!isMainRowSlot(slot)) {
    return new THREE.Vector3(0, y, LINE_LAYOUT.mainRowZ);
  }
  const x = LINE_LAYOUT.stationX[slot - 1];
  return new THREE.Vector3(x, y, LINE_LAYOUT.mainRowZ);
}

/** Interpolate hook target in XZ (used for row and holding legs). */
export function lerpSlotWorld(fromSlot, toSlot, t, y, out = _lerp) {
  const a = slotWorldXZ(fromSlot);
  const b = slotWorldXZ(toSlot);
  return out.set(a.x + (b.x - a.x) * t, y, a.z + (b.z - a.z) * t);
}

/** Idle gaze — CNC end of the straight row. */
export const ROBOT_LINE_GAZE = lineAimForSlot(1);

const _lerp = new THREE.Vector3();

/** Slide gripper along the row; Y is set by crane-aim (caller overwrites). */
export function lerpAlongRow(fromSlot, toSlot, t, y, out = _lerp) {
  if (!isMainRowSlot(fromSlot) || !isMainRowSlot(toSlot)) {
    return out.copy(lineAimForSlot(isMainRowSlot(fromSlot) ? fromSlot : 4, y));
  }
  const x0 = LINE_LAYOUT.stationX[fromSlot - 1];
  const x1 = LINE_LAYOUT.stationX[toSlot - 1];
  return out.set(x0 + (x1 - x0) * t, y, LINE_LAYOUT.mainRowZ);
}

/** @deprecated use lerpAlongRow — holding transfers are not animated sideways */
export function lerpAlongLine(fromSlot, toSlot, t, y = CRANE_TRAVEL_Y, out = _lerp) {
  return lerpAlongRow(fromSlot, toSlot, t, y, out);
}

/** Force a world target onto the main row axis (straight line through the four pads). */
export function projectToRow(target, out = _lerp) {
  return out.set(target.x, target.y, LINE_LAYOUT.mainRowZ);
}
