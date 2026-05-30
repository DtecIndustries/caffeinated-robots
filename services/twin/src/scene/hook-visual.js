import * as THREE from 'three';
import { LINE_LAYOUT, beltXForSlot } from './line-layout.js';
import { isMainRowSlot, lerpAlongRow } from './crane-line.js';
import { BOX_CENTER_Y, easeInOutCubic } from './workspace-positions.js';
import { TIMING } from './transfer-controller.js';

export const CEILING_Y = 5.35;
export const HOVER_Y = 2.55;
const PICK_Y = BOX_CENTER_Y + 0.12;
const ROW_Z = LINE_LAYOUT.mainRowZ;

const _pos = new THREE.Vector3();

function seg(elapsed, start, end) {
  if (elapsed <= start) return 0;
  if (elapsed >= end) return 1;
  return easeInOutCubic((elapsed - start) / (end - start));
}

export function hookHomeX() {
  return beltXForSlot(4);
}

/**
 * Ceiling hook pose from elapsed seconds on the transfer timeline.
 * @param {{ from: number|null, to: number|null, phase: string, elapsed: number, gripping: boolean, active: boolean }} tr
 */
export function hookPose(tr) {
  const { from, to, phase, elapsed: s, gripping, active } = tr;

  if (!active || !isMainRowSlot(from) || !isMainRowSlot(to)) {
    return {
      x: hookHomeX(),
      z: ROW_Z,
      headY: CEILING_Y,
      gripping: false,
    };
  }

  const xFrom = beltXForSlot(from);
  const xTo = beltXForSlot(to);
  const { CLAWS_OPEN_START, CLAWS_FULL_OPEN, GRIP_CLOSE, LIFT_END, TRANSFER_END } =
    TIMING;

  if (phase === 'pickup') {
    const moveX = seg(s, 0, CLAWS_OPEN_START * 0.5);
    const lower = seg(s, CLAWS_OPEN_START * 0.5, CLAWS_OPEN_START);
    const clawOpen = seg(s, CLAWS_OPEN_START, CLAWS_FULL_OPEN);
    const x = hookHomeX() + (xFrom - hookHomeX()) * moveX;
    const headY = CEILING_Y + (PICK_Y - CEILING_Y) * lower;

    return { x, z: ROW_Z, headY, gripping: false, clawOpen };
  }

  if (phase === 'lift') {
    const u = seg(s, GRIP_CLOSE, LIFT_END);
    return {
      x: xFrom,
      z: ROW_Z,
      headY: PICK_Y + (HOVER_Y - PICK_Y) * u,
      gripping: true,
      clawOpen: 0,
    };
  }

  if (phase === 'place') {
    const travel = seg(s, LIFT_END, TRANSFER_END - 1.2);
    const lower = seg(s, TRANSFER_END - 1.8, TRANSFER_END - 0.5);
    const retract = seg(s, TRANSFER_END - 0.5, TRANSFER_END);

    lerpAlongRow(from, to, travel, _pos);

    let headY = HOVER_Y;
    if (s >= TRANSFER_END - 1.8) {
      headY = HOVER_Y + (PICK_Y - HOVER_Y) * lower;
    }
    if (s >= TRANSFER_END - 0.5) {
      headY = PICK_Y + (CEILING_Y - PICK_Y) * retract;
    }

    return {
      x: _pos.x,
      z: ROW_Z,
      headY,
      gripping,
      clawOpen: gripping ? 0 : 1,
    };
  }

  return { x: xTo, z: ROW_Z, headY: CEILING_Y, gripping: false };
}
