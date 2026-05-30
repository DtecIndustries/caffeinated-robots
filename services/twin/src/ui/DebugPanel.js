import { SHOW_DEBUG_PANEL } from '../config.js';
import { formatClock } from '../data/sync-debug.js';

export class DebugPanel {
  #root;
  #open = true;

  constructor(rootEl) {
    this.#root = rootEl;
    this.#root.addEventListener('click', (e) => {
      const toggle = e.target.closest('[data-debug-toggle]');
      if (toggle) {
        this.#open = !this.#open;
        this.#root.querySelector('.debug-body')?.classList.toggle('collapsed', !this.#open);
        toggle.textContent = this.#open ? '▼' : '▶';
      }
    });
  }

  #formatDbRow(row) {
    if (!row) return '';
    const lines = [];
    for (let i = 1; i <= 5; i++) {
      const present = row[`pos${i}_item_present`];
      if (i === 5) {
        const st = row.pos5_item_status ?? '';
        lines.push(`pos5 (holding): present=${present} status="${st}"`);
        if (String(st).toLowerCase().includes('no-go') || String(st).toLowerCase().includes('nogo')) {
          lines.push('  → no-go on pos5: item in reject bay (after holding → reject)');
        }
      } else {
        lines.push(
          `pos${i}: present=${present} status="${row[`pos${i}_item_status`] ?? ''}"`,
        );
      }
    }
    if (row.robot_pose != null && row.robot_pose !== '') {
      lines.push(`robot_pose: "${row.robot_pose}"`);
    }
    lines.push(
      `robot_joints: [${(row.robot_joints ?? []).join(', ')}]`,
    );
    lines.push(`robot_curr_pos: ${row.robot_curr_pos ?? '—'} (slot 0=home)`);
    lines.push(`robot_next_pos: ${row.robot_next_pos ?? '—'}`);
    const curr = Number(row.robot_curr_pos);
    const next = Number(row.robot_next_pos);
    if (next === 5 && curr !== 5) {
      lines.push('→ holding leg: deposit to pos5 (QC fail / review)');
    } else if (curr === 5 && next === 4) {
      lines.push('→ holding leg: collect from pos5 → packaging');
    } else if (curr === 5 && next === 6) {
      lines.push('→ holding → reject: pick pos5, place pos6');
    } else if (curr === 5 || next === 5) {
      lines.push('→ holding leg: base slew + pos5 motion');
    }
    if (row.created_at) lines.push(`created_at: ${row.created_at}`);
    return lines.join('\n');
  }

  render(debug, state) {
    if (!SHOW_DEBUG_PANEL) {
      this.#root.innerHTML = '';
      return;
    }

    if (!debug) {
      this.#root.innerHTML = '';
      return;
    }

    const dbRow = state?.db?.row ? this.#formatDbRow(state.db.row) : null;

    const statusClass = debug.lastFetchOk === false ? 'fail' : debug.stateChanged ? 'changed' : 'ok';
    const statusText =
      debug.lastFetchOk === false
        ? `Error: ${debug.lastFetchError}`
        : debug.stateChanged
          ? 'Data changed'
          : 'No change';

    const changesHtml =
      debug.changes?.length > 0
        ? debug.changes.map((c) => `<li>${c}</li>`).join('')
        : '<li class="muted">—</li>';

    const historyHtml =
      debug.history?.length > 0
        ? debug.history
            .map(
              (h) =>
                `<li class="${h.changed ? 'changed' : ''}"><span class="t">${formatClock(h.at)}</span> ${h.source} — ${h.summary}</li>`,
            )
            .join('')
        : '<li class="muted">—</li>';

    this.#root.innerHTML = `
      <details class="debug-panel" open>
        <summary>
          <span>Sync debugger</span>
          <span class="debug-badge ${statusClass}">${statusText}</span>
          <button type="button" class="debug-toggle" data-debug-toggle aria-label="Toggle">${this.#open ? '▼' : '▶'}</button>
        </summary>
        <div class="debug-body ${this.#open ? '' : 'collapsed'}">
          <div class="debug-grid">
            <span class="k">Mode</span><span class="v">${debug.mode}</span>
            <span class="k">Poll</span><span class="v">${debug.pollMs} ms</span>
            <span class="k">Endpoint</span><span class="v mono">${debug.stateUrl}</span>
            <span class="k">Last fetch</span><span class="v">${formatClock(debug.lastFetchAt)} <span class="muted">(${debug.ago ?? '—'})</span></span>
            <span class="k">Latency</span><span class="v">${debug.lastFetchMs != null ? `${debug.lastFetchMs} ms` : '—'}</span>
            <span class="k">Fetches</span><span class="v">${debug.fetchCount}</span>
            <span class="k">DB timestamp</span><span class="v mono">${debug.dbTimestamp ? formatClock(debug.dbTimestamp) : '—'}</span>
            <span class="k">Source</span><span class="v">${debug.lastSource ?? '—'}</span>
          </div>
          ${debug.dbRow ? `
          <div class="debug-section">
            <div class="debug-section-title">production_line (fetched)</div>
            <pre class="debug-raw">${debug.dbRow}</pre>
          </div>` : ''}
          <div class="debug-section">
            <div class="debug-section-title">Changes this poll</div>
            <ul class="debug-list">${changesHtml}</ul>
          </div>
          <div class="debug-section">
            <div class="debug-section-title">Recent activity</div>
            <ul class="debug-list debug-history">${historyHtml}</ul>
          </div>
        </div>
      </details>
    `;
  }
}
