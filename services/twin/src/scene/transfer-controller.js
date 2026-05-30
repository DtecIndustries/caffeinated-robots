import { isMainRowSlot, isTransferSlot } from './crane-line.js';
import { slotFromStationId } from '../data/positions.js';
import { easeInOutCubic } from './workspace-positions.js';

/** Full pick → carry → place cycle (seconds). */
export const TRANSFER_DURATION = 18;

/** First quarter of a transfer — blend out of idle in joint space (one scalar for all DOFs). */
export const TRANSFER_OPEN_BLEND_SEC = TRANSFER_DURATION * 0.25;

/** 0→1 over the opening segment so every joint uses the same motion parameter. */
export function transferMotionBlend(elapsedSec) {
  const t = Math.min(1, (elapsedSec ?? TRANSFER_OPEN_BLEND_SEC) / TRANSFER_OPEN_BLEND_SEC);
  return easeInOutCubic(t);
}

/**
 * Physical timing (seconds from transfer start):
 * - 0–4   travel down, claws begin to open
 * - 4–7   claws fully open (3 s)
 * - 7–12  wait open, then grip / pick up (5 s)
 * - 12–14 lift up (2 s)
 * - 14–18 travel to next station and drop (4 s)
 */
export const TIMING = {
  CLAWS_OPEN_START: 4,
  CLAWS_FULL_OPEN: 7,
  GRIP_CLOSE: 12,
  LIFT_END: 14,
  /** Hook over pad at pick height (matches crane-aim place descent end). */
  PLACE_AT_TARGET: 15.8,
  PLACE_DROP_END: 17.5,
  TRANSFER_END: 18,
};

/** 0 until the arm is above the place slot; then eased release onto the pad. */
export function placeDropProgress(elapsedSec) {
  const s = elapsedSec ?? 0;
  if (s < TIMING.PLACE_AT_TARGET) return 0;
  if (s >= TIMING.PLACE_DROP_END) return 1;
  return easeInOutCubic(
    (s - TIMING.PLACE_AT_TARGET) /
      (TIMING.PLACE_DROP_END - TIMING.PLACE_AT_TARGET),
  );
}

/** Normalized 0–1 markers (legacy exports). */
export const PICK_END = TIMING.GRIP_CLOSE / TRANSFER_DURATION;
export const PLACE_START = TIMING.LIFT_END / TRANSFER_DURATION;
export const PLACE_END = TIMING.TRANSFER_END / TRANSFER_DURATION;

/** Highest pos1–4 with item_present (matches map-state). */
export function presenceSlotFromState(state) {
  const row = state.db?.row;
  if (row) {
    for (let i = 4; i >= 1; i--) {
      if (row[`pos${i}_item_present`]) return i;
    }
    return null;
  }
  const box = state.boxes?.find((b) => b.onLine);
  if (!box) return null;
  return slotFromStationId(box.stationId);
}

/** Route from DB tags: robot_curr_pos / robot_next_pos / transfer block. */
export function routeFromState(state) {
  const robot = state.robot ?? {};
  const t = state.transfer;

  let from = t?.fromSlot ?? robot.currSlot ?? null;
  let to = t?.toSlot ?? robot.nextSlot ?? null;

  if (from != null && to != null && from === to) {
    to = null;
  }

  if (from == null && to != null && isTransferSlot(to)) {
    const at = presenceSlotFromState(state);
    if (at != null && at !== to) from = at;
  }

  if (
    from != null &&
    to != null &&
    isTransferSlot(from) &&
    isTransferSlot(to)
  ) {
    return { from, to, key: `${from}->${to}` };
  }

  return null;
}

/** DB / PLC: collect or deposit at a side bay (pos5 holding, pos6 reject). */
export function isSideBayRoute(from, to) {
  return from === 5 || to === 5 || from === 6 || to === 6;
}

/** @deprecated use isSideBayRoute */
export function isHoldingRoute(from, to) {
  return isSideBayRoute(from, to);
}

export function transferTimeline(elapsedSec) {
  const s = elapsedSec ?? TRANSFER_DURATION;

  if (s >= TIMING.TRANSFER_END) {
    return { phase: 'idle', t: 0, elapsed: s, gripping: false };
  }
  if (s < TIMING.GRIP_CLOSE) {
    return {
      phase: 'pickup',
      t: s / TIMING.GRIP_CLOSE,
      elapsed: s,
      gripping: false,
    };
  }
  if (s < TIMING.LIFT_END) {
    return {
      phase: 'lift',
      t: (s - TIMING.GRIP_CLOSE) / (TIMING.LIFT_END - TIMING.GRIP_CLOSE),
      elapsed: s,
      gripping: true,
    };
  }
  const drop = placeDropProgress(s);
  return {
    phase: 'place',
    t: (s - TIMING.LIFT_END) / (TIMING.TRANSFER_END - TIMING.LIFT_END),
    elapsed: s,
    gripping: drop < 0.88,
  };
}

/**
 * Local playback of pick/place — runs to completion even if DB stops flagging "transferring".
 */
export class TransferController {
  #routeKey = '';
  #from = null;
  #to = null;
  #elapsed = TRANSFER_DURATION;
  #lastPresenceSlot = null;
  #lastAnimatedKey = '';

  /** @returns {{ from, to, elapsed, active, phase, t, gripping }} */
  update(state, delta) {
    const route = routeFromState(state);
    const presence = presenceSlotFromState(state);

    if (!this.#isAnimating()) {
      if (route && route.key !== this.#lastAnimatedKey) {
        this.#start(route.from, route.to);
      } else if (
        presence != null &&
        this.#lastPresenceSlot != null &&
        presence !== this.#lastPresenceSlot
      ) {
        const prev = this.#lastPresenceSlot;
        const key = `${prev}->${presence}`;
        if (
          isTransferSlot(prev) &&
          isTransferSlot(presence) &&
          key !== this.#lastAnimatedKey
        ) {
          this.#start(prev, presence);
        }
      }
    }

    if (this.#lastPresenceSlot !== presence) {
      this.#lastPresenceSlot = presence;
    }

    if (this.#isAnimating()) {
      this.#elapsed = Math.min(
        TIMING.TRANSFER_END,
        this.#elapsed + delta,
      );
      if (this.#elapsed >= TIMING.TRANSFER_END) {
        this.#lastAnimatedKey = this.#routeKey;
      }
    }

    const tl = transferTimeline(this.#isAnimating() ? this.#elapsed : TIMING.TRANSFER_END);

    return {
      from: this.#from,
      to: this.#to,
      elapsed: this.#elapsed,
      active: this.#isAnimating(),
      phase: tl.phase,
      t: tl.t,
      gripping: tl.gripping,
    };
  }

  #isAnimating() {
    return (
      this.#elapsed < TIMING.TRANSFER_END &&
      this.#from != null &&
      this.#to != null
    );
  }

  #start(from, to) {
    const key = `${from}->${to}`;
    this.#routeKey = key;
    this.#from = from;
    this.#to = to;
    this.#elapsed = 0;
  }
}
