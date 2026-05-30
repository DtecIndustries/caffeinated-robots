import { DEFAULT_ROBOT } from './robot-state.js';
import { HOLDING_DEF, REJECT_DEF } from './constants.js';
import { beltNormalizedForSlot } from '../scene/line-layout.js';
import { robotRouteLabel, slotToStationId } from './positions.js';

/** Production flow: CNC → Assembly → QC → Packaging */
export const STATION_DEFS = [
  { id: 'cnc', label: 'CNC (Laser)' },
  { id: 'assembly', label: 'Assembly' },
  { id: 'qc', label: 'Quality Control' },
  { id: 'packaging', label: 'Packaging' },
];

export const HOLDING_DEFS = [HOLDING_DEF];
export const REJECT_DEFS = [REJECT_DEF];

/** Human reviewer approved — enters at packaging pad center */
export const PACKAGING_ENTRY_POSITION = beltNormalizedForSlot(4);

const SPEED = 0.018;

let tick = 0;
let boxCounter = 1;

function onLineBox(state) {
  return state.boxes.find((b) => b.onLine) ?? null;
}

function lineIsClear(state) {
  return !onLineBox(state);
}

/** New work enters at CNC (far end); t=1 is CNC, t=0 is Packaging. */
function spawnLineBox(state, position = beltNormalizedForSlot(1) - 0.03) {
  if (!lineIsClear(state)) return null;

  boxCounter += 1;
  const box = {
    id: `box-${boxCounter}`,
    position,
    stationId: null,
    onLine: true,
    qcHandled: false,
    humanApproved: false,
    faulty: false,
  };
  state.boxes.push(box);
  return box;
}

function placeApprovedOnLine(state, itemId) {
  if (!lineIsClear(state)) return false;

  let box = state.boxes.find((b) => b.id === itemId);
  if (!box) {
    box = {
      id: itemId,
      position: PACKAGING_ENTRY_POSITION,
      stationId: 'packaging',
      onLine: true,
      qcHandled: true,
      humanApproved: true,
      faulty: false,
    };
    state.boxes.push(box);
  } else {
    box.onLine = true;
    box.position = PACKAGING_ENTRY_POSITION;
    box.stationId = 'packaging';
    box.qcHandled = true;
    box.humanApproved = true;
    box.faulty = false;
  }

  state.qc.lastResult = 'pass';
  state.packagingQueue = state.packagingQueue.filter((id) => id !== itemId);
  return true;
}

function enqueuePackaging(state, itemId) {
  if (!state.packagingQueue.includes(itemId)) {
    state.packagingQueue.push(itemId);
  }
}

/** Approved packaging queue first, then new work from CNC */
function tryLoadOnLine(state) {
  if (!lineIsClear(state) || state.line.status === 'halted') return;

  if (state.packagingQueue.length > 0) {
    const itemId = state.packagingQueue.shift();
    placeApprovedOnLine(state, itemId);
    return;
  }

  spawnLineBox(state);
}

export function getInitialWorldState() {
  return {
    timestamp: new Date().toISOString(),
    line: { status: 'running', reason: null },
    stations: STATION_DEFS.map((s) => ({ ...s, status: 'idle' })),
    holding: HOLDING_DEFS.map((h) => ({
      ...h,
      occupied: false,
      itemId: null,
      awaitingReview: false,
      faulty: false,
    })),
    reject: REJECT_DEFS.map((r) => ({
      ...r,
      occupied: false,
      itemId: null,
      noGo: false,
      faulty: false,
      hideItem: false,
    })),
    packagingQueue: [],
    scrapped: [],
    boxes: [
      {
        id: 'box-1',
        position: beltNormalizedForSlot(1) - 0.03,
        stationId: 'cnc',
        onLine: true,
        qcHandled: false,
        humanApproved: false,
        faulty: false,
      },
    ],
    robot: { ...DEFAULT_ROBOT },
    transfer: null,
    qc: { lastResult: null },
  };
}

function setRobotTransfer(state, currSlot, nextSlot, pose = 'transfer') {
  const transferring =
    currSlot != null && nextSlot != null && currSlot !== nextSlot;
  state.robot = {
    currSlot,
    nextSlot,
    pose,
    action: transferring ? 'transfer' : 'idle',
    transferring,
    carrying: false,
    routeLabel: robotRouteLabel(currSlot, nextSlot),
  };
  state.transfer = transferring
    ? {
        fromSlot: currSlot,
        toSlot: nextSlot,
        fromStationId: slotToStationId(currSlot),
        toStationId: slotToStationId(nextSlot),
      }
    : null;
}

function setRobotIdle(state) {
  state.robot = { ...DEFAULT_ROBOT };
  state.transfer = null;
}

function stationIndexAt(position) {
  if (position > beltNormalizedForSlot(1) - 0.14) return 0;
  if (position > beltNormalizedForSlot(2) - 0.14) return 1;
  if (position > beltNormalizedForSlot(3) - 0.14) return 2;
  return 3;
}

function findFreeHolding(holding) {
  return holding.find((h) => !h.occupied);
}

function occupyHolding(slot, itemId, faulty = false) {
  slot.occupied = true;
  slot.itemId = itemId;
  slot.awaitingReview = true;
  slot.faulty = faulty;
}

function clearHoldingSlot(slot) {
  slot.occupied = false;
  slot.itemId = null;
  slot.awaitingReview = false;
  slot.faulty = false;
}

function allHoldingFull(holding) {
  return holding.every((h) => h.occupied);
}

function setRobotPose(state, action) {
  if (!state.robot) state.robot = { ...DEFAULT_ROBOT };
  state.robot.action = action;
  if (action === 'idle') {
    state.robot.transferring = false;
    state.robot.carrying = false;
  }
}

function haltLine(state, reason) {
  state.line.status = 'halted';
  state.line.reason = reason;
  for (const station of state.stations) {
    if (station.status !== 'fail') station.status = 'halted';
  }
  setRobotPose(state, 'idle');
}

function resumeLine(state) {
  state.line.status = 'running';
  state.line.reason = null;
  for (const station of state.stations) {
    if (station.status === 'halted') station.status = 'idle';
  }
}

function divertToHolding(state, box) {
  const slot = findFreeHolding(state.holding);
  if (!slot) {
    haltLine(state, 'Holding full — awaiting human review');
    return false;
  }

  box.stationId = 'qc';
  box.position = beltNormalizedForSlot(3);
  box.humanApproved = false;
  box.faulty = true;
  state.stations[2].status = 'fail';
  state.qc.lastResult = 'fail';
  setRobotTransfer(state, 3, 5, 'pick');
  return true;
}

/** Human approved QC — send to packaging when line is clear */
export function approveHolding(state, holdingId) {
  const next = structuredClone(state);
  const slot = next.holding.find((h) => h.id === holdingId);
  if (!slot?.occupied) return next;

  const itemId = slot.itemId;
  clearHoldingSlot(slot);
  next.timestamp = new Date().toISOString();

  if (!placeApprovedOnLine(next, itemId)) {
    enqueuePackaging(next, itemId);
    setRobotTransfer(next, 5, 4, 'place');
  } else {
    setRobotIdle(next);
    next.robot.currSlot = 4;
    next.robot.nextSlot = 4;
    next.robot.routeLabel = robotRouteLabel(4, 4);
  }

  if (next.line.status === 'halted' && !allHoldingFull(next.holding)) {
    resumeLine(next);
  }

  return next;
}

/** After crane leg Holding → Reject finishes. */
export function finalizeRejectHolding(state, holdingId, itemId) {
  const next = structuredClone(state);
  const slot = next.holding.find((h) => h.id === holdingId);
  if (slot) clearHoldingSlot(slot);

  const rejectSlot = next.reject?.[0];
  if (rejectSlot && itemId) {
    rejectSlot.occupied = true;
    rejectSlot.itemId = itemId;
    rejectSlot.noGo = true;
    rejectSlot.faulty = true;
    rejectSlot.hideItem = false;
  }

  setRobotIdle(next);
  return next;
}

/** Human rejected — crane moves Holding (5) → Reject (6), then scrap. */
export function rejectHolding(state, holdingId) {
  const next = structuredClone(state);
  const slot = next.holding.find((h) => h.id === holdingId);
  if (!slot?.occupied) return next;

  const itemId = slot.itemId;
  next.timestamp = new Date().toISOString();
  next.pendingReject = { holdingId, itemId };

  next.packagingQueue = next.packagingQueue.filter((id) => id !== itemId);

  const box = next.boxes.find((b) => b.id === itemId);
  if (box) {
    box.onLine = false;
    box.stationId = null;
    box.faulty = true;
    box.humanApproved = false;
  }

  next.qc.lastResult = 'fail';
  if (!next.scrapped.some((s) => s.id === itemId)) {
    next.scrapped.push({
      id: itemId,
      scrappedAt: next.timestamp,
      reason: 'Rejected by human reviewer',
    });
  }

  const rejectSlot = next.reject?.[0];
  if (rejectSlot) {
    rejectSlot.occupied = false;
    rejectSlot.itemId = null;
    rejectSlot.noGo = false;
    rejectSlot.faulty = false;
  }

  setRobotTransfer(next, 5, 6, 'transfer');

  if (next.line.status === 'halted' && !allHoldingFull(next.holding)) {
    resumeLine(next);
  }

  return next;
}

/** Operator triggers QC fail (UI button). */
export function triggerQcFail(state) {
  const next = structuredClone(state);
  next.timestamp = new Date().toISOString();

  const box = onLineBox(next);
  if (!box) return next;

  box.position = beltNormalizedForSlot(3);
  box.stationId = 'qc';
  box.qcHandled = true;
  next.stations[2].status = 'fail';
  next.qc.lastResult = 'fail';
  setRobotPose(next, 'idle');

  if (allHoldingFull(next.holding)) {
    haltLine(
      next,
      'Holding full — line halted until human review clears a slot',
    );
    return next;
  }

  divertToHolding(next, box);
  tryLoadOnLine(next);
  return next;
}

function applyBoxStationEvents(state, box) {
  const idx = stationIndexAt(box.position);
  const station = state.stations[idx];
  box.stationId = station.id;

  if (station.status === 'idle' || station.status === 'busy') {
    station.status = 'busy';
  }

  const at = (slot) => beltNormalizedForSlot(slot);
  const near = (slot, eps = 0.06) =>
    Math.abs(box.position - at(slot)) < eps;

  if (station.id === 'cnc' && near(1, 0.08)) {
    setRobotPose(state, 'idle');
  } else if (station.id === 'assembly' && near(2)) {
    setRobotPose(state, 'place');
  } else if (station.id === 'qc' && near(3) && !box.qcHandled) {
    station.status = 'pass';
    state.qc.lastResult = 'pass';
    box.qcHandled = true;
    setRobotPose(state, 'place');
  } else if (station.id === 'packaging' && near(4)) {
    station.status = 'pass';
    setRobotPose(state, 'pick');
  }
}

export function tickWorldState(prev) {
  tick += 1;
  const next = structuredClone(prev);
  next.timestamp = new Date().toISOString();

  if (next.line.status === 'halted') {
    return next;
  }

  for (const station of next.stations) {
    if (station.status === 'pass' || station.status === 'fail') {
      station.status = 'idle';
    }
  }

  tryLoadOnLine(next);

  const box = onLineBox(next);
  if (!box) {
    return next;
  }

  box.position -= SPEED;

  if (box.position < 0) {
    box.onLine = false;
    box.stationId = null;
    box.humanApproved = false;
    tryLoadOnLine(next);
    const nextBox = onLineBox(next);
    if (nextBox) applyBoxStationEvents(next, nextBox);
    return next;
  }

  applyBoxStationEvents(next, box);
  return next;
}
