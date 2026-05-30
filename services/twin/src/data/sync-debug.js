/** Stable snapshot for change detection (ignores poll timestamp). */
export function stateFingerprint(state) {
  const snap = {
    production_line: state.db?.row ?? null,
    line: state.line,
    stations: state.stations?.map((s) => ({ id: s.id, status: s.status })),
    boxes: state.boxes
      ?.filter((b) => b.onLine)
      .map((b) => ({
        id: b.id,
        position: Number(b.position?.toFixed(3)),
        stationId: b.stationId,
      })),
    qc: state.qc,
  };
  return JSON.stringify(snap);
}

export function diffStateChanges(prev, next) {
  if (!prev || !next) return ['(initial)'];

  const changes = [];

  if (prev.line?.status !== next.line?.status) {
    changes.push(`line: ${prev.line?.status} → ${next.line?.status}`);
  }

  for (const s of next.stations ?? []) {
    const p = prev.stations?.find((x) => x.id === s.id);
    if (p && p.status !== s.status) {
      changes.push(`${s.label}: ${p.status} → ${s.status}`);
    }
  }

  for (const h of next.holding ?? []) {
    const p = prev.holding?.find((x) => x.id === h.id);
    if (p && p.occupied !== h.occupied) {
      changes.push(
        `${h.label}: ${p.occupied ? 'occupied' : 'empty'} → ${h.occupied ? 'occupied' : 'empty'}`,
      );
    }
  }

  for (const r of next.reject ?? []) {
    const p = prev.reject?.find((x) => x.id === r.id);
    if (p && p.occupied !== r.occupied) {
      changes.push(
        `${r.label}: ${p.occupied ? 'no-go' : 'empty'} → ${r.occupied ? 'no-go' : 'empty'}`,
      );
    }
  }

  const prevBox = prev.boxes?.find((b) => b.onLine);
  const nextBox = next.boxes?.find((b) => b.onLine);
  if (!prevBox && nextBox) {
    changes.push(`box on line: ${nextBox.stationId} @ ${nextBox.position?.toFixed(2)}`);
  } else if (prevBox && !nextBox) {
    changes.push('box left line');
  } else if (prevBox && nextBox) {
    if (Math.abs(prevBox.position - nextBox.position) > 0.001) {
      changes.push(
        `box: ${prevBox.position?.toFixed(2)} → ${nextBox.position?.toFixed(2)} (${nextBox.stationId})`,
      );
    }
    if (prevBox.stationId !== nextBox.stationId) {
      changes.push(`box station: ${prevBox.stationId} → ${nextBox.stationId}`);
    }
  }

  if (prev.qc?.lastResult !== next.qc?.lastResult) {
    changes.push(`QC: ${prev.qc?.lastResult ?? '—'} → ${next.qc?.lastResult ?? '—'}`);
  }

  const prevRobot = prev.robot;
  const nextRobot = next.robot;
  if (prevRobot?.routeLabel !== nextRobot?.routeLabel) {
    changes.push(
      `robot: ${prevRobot?.routeLabel ?? '—'} → ${nextRobot?.routeLabel ?? '—'}`,
    );
  } else if (prevRobot?.transferring !== nextRobot?.transferring) {
    changes.push(
      `robot transfer: ${prevRobot?.transferring ? 'yes' : 'no'} → ${nextRobot?.transferring ? 'yes' : 'no'}`,
    );
  }

  const prevDb = prev.db?.row;
  const nextDb = next.db?.row;
  if (prevDb && nextDb) {
    for (let i = 1; i <= 5; i++) {
      const pKey = `pos${i}_item_present`;
      if (prevDb[pKey] !== nextDb[pKey]) {
        const label = i === 5 ? 'pos5 (holding)' : `pos${i}`;
        changes.push(`${label}_present: ${prevDb[pKey]} → ${nextDb[pKey]}`);
      }
      if (i < 5) {
        const sKey = `pos${i}_item_status`;
        if (String(prevDb[sKey] ?? '') !== String(nextDb[sKey] ?? '')) {
          changes.push(
            `pos${i}_status: "${prevDb[sKey] ?? ''}" → "${nextDb[sKey] ?? ''}"`,
          );
        }
      } else if (
        String(prevDb.pos5_item_status ?? '') !==
        String(nextDb.pos5_item_status ?? '')
      ) {
        changes.push(
          `pos5_status: "${prevDb.pos5_item_status ?? ''}" → "${nextDb.pos5_item_status ?? ''}"`,
        );
      }
    }
    const fmtJoints = (a) => `[${(a ?? []).join(',')}]`;
    if (fmtJoints(prevDb.robot_joints) !== fmtJoints(nextDb.robot_joints)) {
      changes.push(
        `robot_joints: ${fmtJoints(prevDb.robot_joints)} → ${fmtJoints(nextDb.robot_joints)}`,
      );
    }
    if (prevDb.robot_curr_pos !== nextDb.robot_curr_pos) {
      changes.push(
        `robot_curr_pos: ${prevDb.robot_curr_pos ?? '—'} → ${nextDb.robot_curr_pos ?? '—'}`,
      );
    }
    if (prevDb.robot_next_pos !== nextDb.robot_next_pos) {
      changes.push(
        `robot_next_pos: ${prevDb.robot_next_pos ?? '—'} → ${nextDb.robot_next_pos ?? '—'}`,
      );
    }
    if (String(prevDb.robot_pose ?? '') !== String(nextDb.robot_pose ?? '')) {
      changes.push(
        `robot_pose: "${prevDb.robot_pose ?? ''}" → "${nextDb.robot_pose ?? ''}"`,
      );
    }
  }

  return changes.length ? changes : [];
}

export function formatTimeAgo(iso) {
  if (!iso) return '—';
  const sec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 1) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  return `${Math.floor(sec / 60)}m ago`;
}

export function formatClock(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString();
}
