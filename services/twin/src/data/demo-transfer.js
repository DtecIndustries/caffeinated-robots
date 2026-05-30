import { beltNormalizedForSlot } from '../scene/line-layout.js';
import { TRANSFER_DURATION } from '../scene/transfer-controller.js';
import { presenceSlotFromState } from '../scene/transfer-controller.js';
import { HOLDING_DEF, REJECT_DEF } from './constants.js';
import { slotToStationId, SLOT_LABELS, robotRouteLabel } from './positions.js';

/** Default route: item at highest occupied slot → next station toward packaging. */
export function defaultTestRoute(state) {
  const at = presenceSlotFromState(state);
  if (at != null && at >= 1 && at < 4) {
    return { from: at, to: at + 1 };
  }
  return { from: 3, to: 4 };
}

/**
 * Overlay robot + transfer + on-line box for a local animation test (no DB write).
 * @returns {object} patched state clone
 */
export function applyDemoTransfer(state, fromSlot, toSlot) {
  const next = structuredClone(state);
  const from = fromSlot;
  const to = toSlot;

  next.robot = {
    ...(next.robot ?? {}),
    currSlot: from,
    nextSlot: to,
    transferring: true,
    carrying: false,
    action: 'transfer',
    routeLabel: robotRouteLabel(from, to, true),
    pose: 'transfer|demo',
  };

  next.transfer = {
    fromSlot: from,
    toSlot: to,
    fromStationId: slotToStationId(from),
    toStationId: slotToStationId(to),
    demo: true,
  };

  if (from === 5 && to === 6) {
    next.boxes = [];
    next.holding = [
      {
        ...HOLDING_DEF,
        occupied: true,
        itemId: 'demo-transfer-box',
        awaitingReview: true,
        faulty: true,
        hideItem: false,
      },
    ];
    next.reject = [
      {
        ...REJECT_DEF,
        occupied: false,
        itemId: null,
        noGo: false,
        faulty: false,
        hideItem: false,
      },
    ];
    next.qc = { lastResult: 'fail' };
    next.timestamp = new Date().toISOString();
    return next;
  }

  if (from === 5) {
    next.holding = [
      {
        ...HOLDING_DEF,
        occupied: true,
        itemId: 'demo-transfer-box',
        awaitingReview: true,
        faulty: true,
        hideItem: false,
      },
    ];
    next.boxes = [];
    if (next.stations?.[2]) next.stations[2].status = 'fail';
    next.qc = { lastResult: 'fail' };
  } else if (to === 5) {
    const stationId = slotToStationId(from) ?? 'qc';
    next.boxes = [
      {
        id: 'demo-transfer-box',
        position: beltNormalizedForSlot(from),
        stationId,
        onLine: true,
        qcHandled: true,
        humanApproved: false,
        faulty: true,
      },
    ];
    next.holding = [
      {
        ...HOLDING_DEF,
        occupied: false,
        itemId: null,
        awaitingReview: false,
        faulty: false,
        hideItem: false,
      },
    ];
    if (next.stations?.[2]) next.stations[2].status = 'fail';
    next.qc = { lastResult: 'fail' };
  } else {
    const stationId = slotToStationId(from) ?? 'qc';
    next.boxes = [
      {
        id: 'demo-transfer-box',
        position: beltNormalizedForSlot(from),
        stationId,
        onLine: true,
        qcHandled: from >= 3,
        humanApproved: false,
        faulty: false,
      },
    ];
  }

  next.timestamp = new Date().toISOString();
  return next;
}

export function demoTransferLabel(from, to) {
  return `${SLOT_LABELS[from] ?? from} → ${SLOT_LABELS[to] ?? to}`;
}

export { TRANSFER_DURATION };
