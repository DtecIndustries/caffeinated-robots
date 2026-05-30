import {
  isSideBaySlot,
  ROBOT_ROW_YAW,
  robotYawForSlot,
} from './crane-line.js';
import { easeInOutCubic } from './workspace-positions.js';
import {
  TIMING,
  TRANSFER_OPEN_BLEND_SEC,
} from './transfer-controller.js';

function lerpAngle(a, b, t) {
  let d = b - a;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
}

/** Yaw the pedestal should face for this transfer (holding uses base slew). */
export function craneBaseYaw(tr) {
  if (!tr?.active) return ROBOT_ROW_YAW;

  const { from, to, elapsed: s } = tr;
  const involvesSideBay = isSideBaySlot(from) || isSideBaySlot(to);

  if (!involvesSideBay) {
    return ROBOT_ROW_YAW;
  }

  const fromYaw = robotYawForSlot(from);
  const toYaw = robotYawForSlot(to);

  // Pick + lift: face the source bay (holding for 5→6, not reject).
  if (s < TIMING.LIFT_END) {
    const u = easeInOutCubic(Math.min(1, s / TRANSFER_OPEN_BLEND_SEC));
    return lerpAngle(ROBOT_ROW_YAW, fromYaw, u);
  }

  // Place: slew from source bay to destination (holding → reject).
  const placeT = s - TIMING.LIFT_END;
  const u = easeInOutCubic(Math.min(1, placeT / TRANSFER_OPEN_BLEND_SEC));
  return lerpAngle(fromYaw, toYaw, u);
}

/** True when DB route should slew the base (any leg touches pos5). */
export function baseSlewActive(tr) {
  if (!tr?.active) return false;
  return isSideBaySlot(tr.from) || isSideBaySlot(tr.to);
}
