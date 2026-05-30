import * as THREE from 'three';
import {
  BOX_CENTER_Y,
  CLAW_HOVER_Y,
  LINE_LAYOUT,
  stationPosition,
} from './line-layout.js';
import {
  CRANE_TRAVEL_Y,
  ROBOT_LINE_GAZE,
  lerpAlongLine,
  lineAimForSlot,
} from './crane-line.js';

export {
  CRANE_TRAVEL_Y,
  ROBOT_LINE_GAZE,
  lerpAlongLine,
  lerpAlongLine as lerpAlongRow,
  lineAimForSlot,
  isMainRowSlot,
  isHoldingSlot,
  isRejectSlot,
  isSideBaySlot,
  isTransferSlot,
  projectToRow,
} from './crane-line.js';

export {
  BOX_CENTER_Y,
  CARRY_Z_OFFSET,
  CLAW_APPROACH_Y,
  CLAW_ARC_PEAK_Y,
  CLAW_CARRY_Y,
  CLAW_HOVER_Y,
  BOX_TOP_Y,
} from './line-layout.js';

function boxPoint(slot) {
  const p = stationPosition(slot);
  if (!p) return new THREE.Vector3(0, BOX_CENTER_Y, 0);
  return new THREE.Vector3(p.x, BOX_CENTER_Y, p.z);
}

const BOX_WORLD = {
  1: boxPoint(1),
  2: boxPoint(2),
  3: boxPoint(3),
  4: boxPoint(4),
  5: boxPoint(5),
  6: boxPoint(6),
};

/** @deprecated alias */
export const ROBOT_HOME_AIM = ROBOT_LINE_GAZE;

export function worldPointForSlot(slot) {
  return lineAimForSlot(slot)?.clone() ?? ROBOT_LINE_GAZE.clone();
}

/** Where the gripper should meet the box (box center, not above it). */
export function worldPointForPick(slot) {
  return BOX_WORLD[slot]?.clone() ?? ROBOT_LINE_GAZE.clone();
}

export function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}
