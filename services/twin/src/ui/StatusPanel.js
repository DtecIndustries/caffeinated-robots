const STATUS_LABEL = {
  idle: 'Idle',
  busy: 'Busy',
  pass: 'Pass',
  fail: 'Fail',
  halted: 'Halted',
};

export class StatusPanel {
  #root;
  #handlers;
  #boundClick;

  constructor(rootEl, handlers = {}) {
    this.#root = rootEl;
    this.#handlers = handlers;
    this.#boundClick = (e) => this.#onClick(e);
    this.#root.addEventListener('click', this.#boundClick);
  }

  destroy() {
    this.#root.removeEventListener('click', this.#boundClick);
  }

  #onClick(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn || btn.disabled) return;

    const action = btn.dataset.action;
    const holding = btn.dataset.holding;

    if (action === 'qc-fail') {
      this.#handlers.onQcFail?.();
    } else if (action === 'approve-holding') {
      this.#handlers.onApproveHolding?.(holding);
    } else     if (action === 'reject-holding') {
      this.#handlers.onRejectHolding?.(holding);
    } else if (action === 'test-transfer') {
      const from = btn.dataset.from ? Number(btn.dataset.from) : undefined;
      const to = btn.dataset.to ? Number(btn.dataset.to) : undefined;
      this.#handlers.onTestTransfer?.(from, to);
    }
  }

  render(state, meta = {}) {
    const readOnly = meta.readOnly ?? state.readOnly ?? false;
    const readOnlyAttr = readOnly ? 'disabled' : '';
    const halted = state.line?.status === 'halted';
    const lineClass = halted ? 'halted' : 'running';
    const lineText = halted
      ? `LINE HALTED — ${state.line?.reason ?? 'Not operational'}`
      : 'Line operational';

    const onLine = state.boxes?.some((b) => b.onLine);
    const queueLen = state.packagingQueue?.length ?? 0;
    const queueNote =
      queueLen > 0
        ? `${queueLen} approved for packaging — waiting for line`
        : '';

    const scrappedLen = state.scrapped?.length ?? 0;

    const qc = state.qc?.lastResult;
    const qcClass = qc ?? 'idle';
    const qcText =
      qc === 'pass'
        ? 'QC PASS'
        : qc === 'fail'
          ? 'QC FAIL → Holding'
          : 'Awaiting QC';

    const stationsHtml = state.stations
      .map((s) => {
        const color =
          s.status === 'pass'
            ? '#3fb950'
            : s.status === 'fail'
              ? '#f85149'
              : s.status === 'halted'
                ? '#6e7681'
                : s.status === 'busy'
                  ? '#d29922'
                  : '#484f58';
        return `
          <div class="station-row">
            <span class="label">
              <span class="dot" style="background:${color}"></span>
              ${s.label}
            </span>
            <span class="status">${STATUS_LABEL[s.status] ?? s.status}</span>
          </div>`;
      })
      .join('');

    const holdingHtml = (state.holding ?? [])
      .map((h) => {
        const status = h.occupied
          ? h.awaitingReview
            ? 'Awaiting review'
            : 'Occupied'
          : 'Empty';
        const color = h.occupied
          ? h.awaitingReview
            ? '#a371f7'
            : '#d29922'
          : '#484f58';
        return `
          <div class="station-row">
            <span class="label">
              <span class="dot" style="background:${color}"></span>
              ${h.label}
            </span>
            <span class="status">${status}</span>
          </div>`;
      })
      .join('');

    const reviewButtons = (state.holding ?? [])
      .map((h) => {
        const label = h.label;
        const disabled = readOnly || !h.occupied ? 'disabled' : '';
        return `
          <div class="holding-actions">
            <span class="holding-label">${label}</span>
            <div class="control-row">
              <button
                type="button"
                class="btn btn-approve"
                data-action="approve-holding"
                data-holding="${h.id}"
                ${disabled}
              >
                → Packaging
              </button>
              <button
                type="button"
                class="btn btn-reject"
                data-action="reject-holding"
                data-holding="${h.id}"
                ${disabled}
              >
                Faulty
              </button>
            </div>
          </div>`;
      })
      .join('');

    const robotAction = state.robot?.action ?? 'idle';
    const robotRoute = state.robot?.routeLabel ?? 'Idle';
    const transferring = state.robot?.transferring;
    const demoRoute = state.transfer?.demo
      ? `${state.transfer.fromStationId ?? ''} → ${state.transfer.toStationId ?? ''}`
      : null;
    const gripper = state.robot?.joints?.[5] ?? 0;
    const gripperPct = Math.round(
      (transferring ? 0.12 : gripper) * 100,
    );

    this.#root.innerHTML = `
      <h1>Production line</h1>
      ${readOnly ? '<div class="readonly-banner">Read-only — live data from database</div>' : ''}
      <div class="line-banner ${lineClass}">${lineText}</div>
      <div class="qc-banner ${qcClass}">${qcText}</div>

      <div class="section-title">Line controls</div>
      <div class="controls">
        <button
          type="button"
          class="btn btn-secondary"
          data-action="test-transfer"
          title="Run full crane pick/place cycle (~18s) using live-style robot_curr/next slots"
        >
          Test crane transfer
        </button>
        <button
          type="button"
          class="btn btn-secondary"
          data-action="test-transfer"
          data-from="3"
          data-to="4"
          title="QC → Packaging (common live route)"
        >
          Test QC → Packaging
        </button>
        <p class="control-hint">Animation test only — does not write to the database. Works in read-only mode.</p>
        <button
          type="button"
          class="btn btn-danger"
          data-action="qc-fail"
          ${readOnly || !onLine || halted ? 'disabled' : ''}
          title="${readOnly ? 'Read-only mode' : halted ? 'Clear holding to resume first' : 'Send current item to holding for review'}"
        >
          QC fail
        </button>
        ${queueNote ? `<p class="queue-banner">${queueNote}</p>` : ''}
        ${scrappedLen > 0 ? `<p class="scrap-banner">${scrappedLen} scrapped (faulty)</p>` : ''}
      </div>

      <div class="section-title">Human review (holding)</div>
      <p class="control-hint">${readOnly ? 'Review actions are disabled (read-only).' : 'QC done by reviewer. Approve → Packaging. Faulty → scrapped.'}</p>
      <div class="controls holding-test-controls">
        <button
          type="button"
          class="btn btn-secondary"
          data-action="test-transfer"
          data-from="3"
          data-to="5"
          title="QC fail route: base slew + deposit cube at pos5 (~18s demo)"
        >
          Test QC → Holding
        </button>
        <button
          type="button"
          class="btn btn-secondary"
          data-action="test-transfer"
          data-from="5"
          data-to="4"
          title="After approve: collect cube from holding → Packaging (~18s demo)"
        >
          Test Holding → Packaging
        </button>
        <button
          type="button"
          class="btn btn-secondary"
          data-action="test-transfer"
          data-from="5"
          data-to="6"
          title="Human reject: pick at holding, place in reject bay (~18s demo)"
        >
          Test Holding → Reject
        </button>
        <p class="control-hint">Side-bay animation only — no database write. Works in read-only mode.</p>
      </div>
      <div class="review-controls">${reviewButtons}</div>

      <div class="section-title">Process</div>
      <div class="stations">${stationsHtml}</div>
      <div class="section-title">Holding</div>
      <div class="stations">${holdingHtml}</div>
      <div class="section-title">Reject (no-go)</div>
      <div class="stations">${(state.reject ?? [])
        .map((r) => {
          const status = r.occupied ? 'No-go' : 'Empty';
          const color = r.occupied ? 0xf85149 : 0x3d2020;
          return `
          <div class="station-row">
            <span class="label">
              <span class="dot" style="background:#${color.toString(16).padStart(6, '0')}"></span>
              ${r.label}
            </span>
            <span class="status">${status}</span>
          </div>`;
        })
        .join('')}</div>
      <div class="robot">
        Robot: <strong>${robotAction}</strong>
        <div class="gripper">${robotRoute}${transferring ? ' (moving)' : ''}${demoRoute ? ' [demo]' : ''}</div>
        <div class="gripper">Gripper: ${transferring ? 'closed' : `${gripperPct}% open`}</div>
      </div>
    `;
  }
}
