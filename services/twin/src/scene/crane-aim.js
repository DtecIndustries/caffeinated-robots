import * as THREE from 'three';
import { LINE_LAYOUT, beltXForSlot } from './line-layout.js';
import {
  isSideBaySlot,
  isTransferSlot,
  lerpAlongRow,
  lerpSlotWorld,
  ROBOT_LINE_GAZE,
  slotWorldXZ,
} from './crane-line.js';
import {
  BOX_TOP_Y,
  CARRY_Z_OFFSET,
  CLAW_APPROACH_Y,
  CLAW_ARC_PEAK_Y,
  CLAW_CARRY_Y,
  CLAW_HOVER_Y,
  easeInOutCubic,
  worldPointForPick,
} from './workspace-positions.js';
import { TIMING } from './transfer-controller.js';



const PICK_Y = BOX_TOP_Y + 0.03;

const ROW_Z = LINE_LAYOUT.mainRowZ;



const REACH_PICK_BY = 5.5;



const _pos = new THREE.Vector3();



function seg(elapsed, start, end) {

  if (elapsed <= start) return 0;

  if (elapsed >= end) return 1;

  return easeInOutCubic((elapsed - start) / (end - start));

}



function hookHomeX() {

  return beltXForSlot(4);

}



function hookHomeZ() {
  return ROW_Z;
}

/** Pickup start: row slots from packaging home; side bays from row Z at bay X. */
function pickupHomeXZ(fromSlot) {
  const tgt = slotWorldXZ(fromSlot);
  if (isSideBaySlot(fromSlot)) {
    return { x: tgt.x, z: LINE_LAYOUT.mainRowZ };
  }
  return { x: hookHomeX(), z: hookHomeZ() };
}

function travelsTowardRobot(fromSlot, toSlot) {

  if (isSideBaySlot(fromSlot) || isSideBaySlot(toSlot)) return false;

  const x0 = LINE_LAYOUT.stationX[fromSlot - 1];

  const x1 = LINE_LAYOUT.stationX[toSlot - 1];

  return x1 < x0;

}



/** Steady high carry over the base (no sine bob — that caused IK flicker). */

function carryClearance(travelT) {

  const t = Math.max(0, Math.min(1, travelT));

  const rampIn = t < 0.12 ? t / 0.12 : 1;

  const rampOut = t > 0.88 ? (1 - t) / 0.12 : 1;

  const blend = Math.min(rampIn, rampOut);

  const y = CLAW_CARRY_Y + (CLAW_ARC_PEAK_Y - CLAW_CARRY_Y) * blend;

  const z = ROW_Z + CARRY_Z_OFFSET * blend;

  return { y, z };

}



/** One eased parameter drives X, Y, and Z together. */

function pickupMotion(s, fromSlot, out) {
  const u = seg(s, 0, REACH_PICK_BY);
  const tgt = slotWorldXZ(fromSlot);
  const home = pickupHomeXZ(fromSlot);
  const x = home.x + (tgt.x - home.x) * u;
  const z = home.z + (tgt.z - home.z) * u;



  let y;

  if (u < 0.4) {

    const t = u / 0.4;

    y = CLAW_HOVER_Y + (CLAW_APPROACH_Y - CLAW_HOVER_Y) * t;

  } else if (s < REACH_PICK_BY) {

    const t = (u - 0.4) / 0.6;

    y = CLAW_APPROACH_Y + (PICK_Y - CLAW_APPROACH_Y) * t;

  } else {

    y = PICK_Y;

  }



  return out.set(x, y, z);

}



function placeY(s, fromSlot, toSlot, travelT) {

  const { TRANSFER_END } = TIMING;

  const onBoxBy = TRANSFER_END - 2.2;



  if (s < onBoxBy - 1.2) {

    return travelsTowardRobot(fromSlot, toSlot)

      ? carryClearance(travelT).y

      : CLAW_HOVER_Y;

  }

  if (s < onBoxBy) {

    const t = seg(s, onBoxBy - 1.2, onBoxBy);

    const startY = travelsTowardRobot(fromSlot, toSlot)

      ? carryClearance(1).y

      : CLAW_HOVER_Y;

    return startY + (PICK_Y - startY) * t;

  }

  return PICK_Y;

}



function placeZ(fromSlot, toSlot, travelT, fallbackZ) {

  if (!travelsTowardRobot(fromSlot, toSlot)) {

    return fallbackZ;

  }

  return carryClearance(travelT).z;

}



function travelPath(from, to, travel, y, out) {

  if (isSideBaySlot(from) || isSideBaySlot(to)) {

    return lerpSlotWorld(from, to, travel, y, out);

  }

  return lerpAlongRow(from, to, travel, y, out);

}



/**

 * IK target for top-down hooking.

 * @param {{ from, to, phase, elapsed, active }} tr

 * @param {THREE.Vector3} out

 */

export function craneAim(tr, out) {

  const { from, to, phase, elapsed: s, active } = tr;



  if (!active || !isTransferSlot(from) || !isTransferSlot(to)) {

    return out.copy(ROBOT_LINE_GAZE);

  }



  const fromXZ = slotWorldXZ(from);

  const { GRIP_CLOSE, LIFT_END, TRANSFER_END } = TIMING;

  const inward = travelsTowardRobot(from, to);

  const sideBayLeg = isSideBaySlot(from) || isSideBaySlot(to);



  if (phase === 'pickup') {

    return pickupMotion(s, from, out);

  }



  if (phase === 'lift') {

    const u = seg(s, GRIP_CLOSE, LIFT_END);

    const liftY = inward ? CLAW_ARC_PEAK_Y : CLAW_HOVER_Y;

    const z =

      sideBayLeg && isSideBaySlot(from)

        ? fromXZ.z + (ROW_Z - fromXZ.z) * (1 - u)

        : inward

          ? ROW_Z + CARRY_Z_OFFSET * 0.5

          : fromXZ.z;

    return out.set(fromXZ.x, PICK_Y + (liftY - PICK_Y) * u, z);

  }



  if (phase === 'place') {

    const travel = seg(s, LIFT_END, TRANSFER_END - 2.4);

    const onDescent = s >= TRANSFER_END - 2.2;



    travelPath(from, to, travel, CLAW_CARRY_Y, _pos);

    if (inward && !onDescent && !sideBayLeg) {

      const { y, z } = carryClearance(travel);

      _pos.y = y;

      _pos.z = z;

    } else {

      _pos.y = placeY(s, from, to, travel);

      _pos.z = placeZ(from, to, travel, _pos.z);

    }

    return out.copy(_pos);

  }



  return out.copy(worldPointForPick(to));

}



/** Inward carry — use stable IK + heavier aim smoothing in RobotModel. */

export function carryArcActive(tr) {

  if (!tr?.active) return false;

  return (

    travelsTowardRobot(tr.from, tr.to) &&

    (tr.phase === 'lift' || tr.phase === 'place') &&

    tr.elapsed >= TIMING.GRIP_CLOSE &&

    tr.elapsed < TIMING.TRANSFER_END - 2.3

  );

}


