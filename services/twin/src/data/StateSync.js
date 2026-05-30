import { USE_MOCK, POLL_MS, STATE_URL } from '../config.js';
import {
  getInitialWorldState,
  tickWorldState,
  approveHolding,
  finalizeRejectHolding,
  rejectHolding,
  triggerQcFail,
} from './mock.js';
import {
  applyDemoTransfer,
  defaultTestRoute,
  TRANSFER_DURATION,
} from './demo-transfer.js';
import {
  stateFingerprint,
  diffStateChanges,
  formatTimeAgo,
} from './sync-debug.js';

function createDebug() {
  return {
    mode: USE_MOCK ? 'mock' : 'database',
    pollMs: POLL_MS,
    stateUrl: STATE_URL,
    fetchCount: 0,
    lastFetchAt: null,
    lastFetchMs: null,
    lastFetchOk: null,
    lastFetchError: null,
    stateChanged: false,
    changes: [],
    fingerprint: null,
    dbTimestamp: null,
    history: [],
  };
}

const MAX_HISTORY = 8;

export class StateSync {
  #onUpdate;
  #state = getInitialWorldState();
  #prevState = null;
  #timer = null;
  #readOnly = false;
  #debug = createDebug();
  /** Local crane animation overlay (survives DB polls until cleared). */
  #demoTransfer = null;
  #demoClearTimer = null;
  #rejectFinalizeTimer = null;

  constructor(onUpdate) {
    this.#onUpdate = onUpdate;
  }

  start() {
    this.#recordUpdate('start');
    this.#timer = setInterval(() => this.#tick(), POLL_MS);
  }

  stop() {
    if (this.#timer) clearInterval(this.#timer);
  }

  getState() {
    return this.#state;
  }

  getDebug() {
    return this.#debug;
  }

  isReadOnly() {
    return this.#readOnly;
  }

  triggerQcFail() {
    if (this.#readOnly || !USE_MOCK) return;
    this.#state = triggerQcFail(this.#state);
    this.#recordUpdate('qc-fail');
  }

  approveHolding(holdingId) {
    if (this.#readOnly || !USE_MOCK) return;
    this.#state = approveHolding(this.#state, holdingId);
    this.#recordUpdate('approve');
  }

  rejectHolding(holdingId) {
    if (this.#readOnly || !USE_MOCK) return;
    if (this.#rejectFinalizeTimer) {
      clearTimeout(this.#rejectFinalizeTimer);
      this.#rejectFinalizeTimer = null;
    }
    this.#state = rejectHolding(this.#state, holdingId);
    const pending = this.#state.pendingReject;
    if (pending) {
      this.#rejectFinalizeTimer = setTimeout(() => {
        this.#rejectFinalizeTimer = null;
        this.#state = finalizeRejectHolding(
          this.#state,
          pending.holdingId,
          pending.itemId,
        );
        delete this.#state.pendingReject;
        this.#recordUpdate('reject-complete');
      }, TRANSFER_DURATION * 1000 + 400);
    }
    this.#recordUpdate('reject');
  }

  /**
   * Play full pick/place animation (mock + read-only DB).
   * @param {number} [fromSlot]
   * @param {number} [toSlot]
   */
  triggerTestTransfer(fromSlot, toSlot) {
    if (this.#demoClearTimer) {
      clearTimeout(this.#demoClearTimer);
      this.#demoClearTimer = null;
    }

    const route =
      fromSlot != null && toSlot != null
        ? { from: fromSlot, to: toSlot }
        : defaultTestRoute(this.#state);

    this.#demoTransfer = route;
    this.#state = applyDemoTransfer(this.#state, route.from, route.to);

    this.#demoClearTimer = setTimeout(() => {
      const route = this.#demoTransfer;
      this.#demoTransfer = null;
      this.#demoClearTimer = null;
      if (USE_MOCK && route?.from === 5 && route?.to === 6) {
        this.#state = finalizeRejectHolding(
          this.#state,
          'holding',
          'demo-transfer-box',
        );
      }
      if (!USE_MOCK) {
        this.#tick();
      } else {
        this.#recordUpdate('demo-transfer-end');
      }
    }, TRANSFER_DURATION * 1000 + 400);

    this.#recordUpdate('demo-transfer');
  }

  #mergeDemoTransfer(base) {
    if (!this.#demoTransfer) return base;
    return applyDemoTransfer(base, this.#demoTransfer.from, this.#demoTransfer.to);
  }

  #recordUpdate(source) {
    const fp = stateFingerprint(this.#state);
    const changes = diffStateChanges(this.#prevState, this.#state);
    const changed = changes.length > 0 && this.#prevState !== null;

    this.#debug.fetchCount += 1;
    this.#debug.lastFetchAt = new Date().toISOString();
    this.#debug.lastFetchOk = true;
    this.#debug.lastFetchError = null;
    this.#debug.fingerprint = fp.slice(0, 80) + (fp.length > 80 ? '…' : '');
    this.#debug.dbTimestamp = this.#state.timestamp ?? null;
    this.#debug.stateChanged = changed;
    this.#debug.changes = changes.length ? changes : changed ? [] : ['(no visual change)'];
    this.#debug.lastSource = source;

    this.#pushHistory(source, changed, changes);

    this.#prevState = structuredClone(this.#state);
    this.#emit();
  }

  #pushHistory(source, changed, changes) {
    this.#debug.history.unshift({
      at: new Date().toISOString(),
      source,
      changed,
      summary: changes[0] ?? (changed ? 'updated' : 'unchanged'),
    });
    this.#debug.history = this.#debug.history.slice(0, MAX_HISTORY);
  }

  async #tick() {
    if (USE_MOCK) {
      this.#readOnly = false;
      const t0 = performance.now();
      this.#state = this.#mergeDemoTransfer(tickWorldState(this.#state));
      this.#debug.lastFetchMs = Math.round(performance.now() - t0);
      this.#recordUpdate('mock-tick');
      return;
    }

    const t0 = performance.now();
    try {
      const res = await fetch(STATE_URL);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.#state = this.#mergeDemoTransfer(await res.json());
      this.#readOnly = this.#state.readOnly !== false;
      this.#debug.lastFetchMs = Math.round(performance.now() - t0);
      this.#recordUpdate('db-fetch');
    } catch (err) {
      this.#debug.lastFetchMs = Math.round(performance.now() - t0);
      this.#debug.fetchCount += 1;
      this.#debug.lastFetchAt = new Date().toISOString();
      this.#debug.lastFetchOk = false;
      this.#debug.lastFetchError = err.message;
      this.#debug.stateChanged = false;
      this.#debug.changes = [];
      this.#debug.lastSource = 'db-fetch-error';
      this.#pushHistory('db-fetch-error', false, [err.message]);
      console.warn('[StateSync] DB fetch failed', err);
      this.#emit();
    }
  }

  #emit() {
    this.#onUpdate(this.#state, {
      readOnly: this.#readOnly,
      debug: { ...this.#debug, ago: formatTimeAgo(this.#debug.lastFetchAt) },
    });
  }
}
