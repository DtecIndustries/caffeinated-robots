import { isMainRowSlot, isTransferSlot } from './workspace-positions.js';
import { placeDropProgress, TIMING } from './transfer-controller.js';

export {
  PICK_END,
  PLACE_START,
  PLACE_END,
  TRANSFER_DURATION,
  TIMING,
} from './transfer-controller.js';

/**
 * Which box mesh to show during crane transfer.
 */
export function boxDisplay(state, tr) {
  const animActive =
    tr.active && isTransferSlot(tr.from) && isTransferSlot(tr.to);

  if (animActive) {
    if (tr.elapsed < TIMING.GRIP_CLOSE) {
      if (tr.from === 5) {
        return { type: 'holding' };
      }
      if (tr.from === 6) {
        return { type: 'reject' };
      }
      if (isMainRowSlot(tr.from)) {
        return { type: 'belt', slot: tr.from };
      }
    }
    if (tr.elapsed < TIMING.TRANSFER_END - 0.5) {
      const dropT =
        tr.phase === 'place' ? placeDropProgress(tr.elapsed) : 0;
      return {
        type: 'gripper',
        fromSlot: tr.from,
        placeSlot: dropT > 0 ? tr.to : null,
        placeT: dropT > 0 ? dropT : null,
      };
    }
  }

  if (state.boxes?.some((b) => b.onLine)) {
    return { type: 'belt', slot: null };
  }

  if (state.holding?.some((h) => h.occupied && !h.hideItem)) {
    return { type: 'holding' };
  }

  if (state.reject?.some((r) => r.occupied && !r.hideItem)) {
    return { type: 'reject' };
  }

  return { type: 'none' };
}
