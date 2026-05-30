import { robotFromDbRow } from '../src/data/robot-state.js';
import { slotToStationId } from '../src/data/positions.js';
import { isNoGoStatus } from '../src/data/item-status.js';
import { beltNormalizedForSlot } from '../src/scene/line-layout.js';
import { isFaultyStatus } from '../src/scene/box-visual.js';

const STATION_DEFS = [
  { id: 'cnc', label: 'CNC (Laser)', pos: 1 },
  { id: 'assembly', label: 'Assembly', pos: 2 },
  { id: 'qc', label: 'Quality Control', pos: 3 },
  { id: 'packaging', label: 'Packaging', pos: 4 },
];

function mapPosStatus(itemPresent, itemStatus) {
  const raw = String(itemStatus ?? '').toLowerCase().trim();
  if (raw.includes('halt')) return 'halted';
  if (isFaultyStatus(raw)) return 'fail';
  if (raw.includes('pass') || raw === 'ok') return 'pass';
  if (itemPresent) return raw ? 'busy' : 'busy';
  return 'idle';
}

function processSlotsFromLine(line) {
  if (!line) {
    return [
      { present: false, status: '' },
      { present: false, status: '' },
      { present: false, status: '' },
      { present: false, status: '' },
    ];
  }
  return [
    { present: !!line.pos1_item_present, status: line.pos1_item_status ?? '' },
    { present: !!line.pos2_item_present, status: line.pos2_item_status ?? '' },
    { present: !!line.pos3_item_present, status: line.pos3_item_status ?? '' },
    { present: !!line.pos4_item_present, status: line.pos4_item_status ?? '' },
  ];
}

/** Reject bay only — after human/PLC sends holding → reject (no-go on pos5 or pos6). */
function rejectOccupancyFromRow(row) {
  if (!row) return { present: false, status: '' };
  if (row.pos6_item_present) {
    return { present: true, status: String(row.pos6_item_status ?? '') };
  }
  if (row.pos5_item_present && isNoGoStatus(row.pos5_item_status)) {
    return { present: true, status: String(row.pos5_item_status ?? '') };
  }
  return { present: false, status: '' };
}

function holdingFromLine(row, robot) {
  const status = String(row?.pos5_item_status ?? '');
  const occupied = !!row?.pos5_item_present && !isNoGoStatus(status);
  const hideItem = robot.carrying && robot.currSlot === 5;
  const faulty = isFaultyStatus(status) && !isNoGoStatus(status);
  return [
    {
      id: 'holding',
      label: 'Holding',
      occupied,
      itemId: occupied ? `hold-${row?.id ?? '0'}` : null,
      awaitingReview: occupied,
      faulty,
      hideItem,
    },
  ];
}

function rejectFromLine(row, robot) {
  const { present, status } = rejectOccupancyFromRow(row);
  const hideItem = robot.carrying && robot.currSlot === 6;
  return [
    {
      id: 'reject',
      label: 'Reject',
      occupied: present,
      itemId: present ? `reject-${row?.id ?? '0'}` : null,
      noGo: present,
      faulty: present,
      hideItem,
    },
  ];
}

function buildBoxFromProcessSlots(slots, lineId, robot) {
  let activeIndex = -1;
  for (let i = slots.length - 1; i >= 0; i--) {
    if (slots[i].present) {
      activeIndex = i;
      break;
    }
  }
  if (activeIndex < 0) return [];

  const station = STATION_DEFS[activeIndex];
  const itemStatus = String(slots[activeIndex].status ?? '');
  const itemStatusLower = itemStatus.toLowerCase();

  return [
    {
      id: lineId ? `db-line-${lineId}` : 'db-line',
      position: beltNormalizedForSlot(activeIndex + 1),
      stationId: station.id,
      onLine: true,
      qcHandled:
        activeIndex > 2 ||
        itemStatusLower.includes('pass') ||
        itemStatusLower.includes('fail') ||
        itemStatusLower === 'ok',
      humanApproved: false,
      faulty: isFaultyStatus(slots[activeIndex].status),
    },
  ];
}

function qcFromPos3(slots) {
  if (!slots[2].present) return null;
  const s = String(slots[2].status ?? '').toLowerCase();
  if (isFaultyStatus(s)) return 'fail';
  if (s.includes('pass') || s === 'ok') return 'pass';
  return null;
}

function lineMeta(slots, row, robot) {
  if (slots.some((s) => mapPosStatus(s.present, s.status) === 'halted')) {
    return { status: 'halted', reason: 'Line halted (production_line status)' };
  }

  const holding = holdingFromLine(row, robot);
  if (holding[0].occupied) {
    const hStatus = String(row?.pos5_item_status ?? '').toLowerCase();
    if (hStatus.includes('halt')) {
      return { status: 'halted', reason: 'Holding full / line halted' };
    }
  }

  return { status: 'running', reason: null };
}

function dbRowSnapshot(row) {
  if (!row) return null;
  return {
    id: row.id,
    pos1_item_present: row.pos1_item_present,
    pos1_item_status: row.pos1_item_status ?? '',
    pos2_item_present: row.pos2_item_present,
    pos2_item_status: row.pos2_item_status ?? '',
    pos3_item_present: row.pos3_item_present,
    pos3_item_status: row.pos3_item_status ?? '',
    pos4_item_present: row.pos4_item_present,
    pos4_item_status: row.pos4_item_status ?? '',
    pos5_item_present: row.pos5_item_present,
    pos5_item_status: row.pos5_item_status ?? '',
    pos6_item_present: row.pos6_item_present ?? null,
    pos6_item_status: row.pos6_item_status ?? '',
    robot_pose: row.robot_pose ?? '',
    robot_joints: row.robot_joints ?? [],
    robot_curr_pos: row.robot_curr_pos ?? null,
    robot_next_pos: row.robot_next_pos ?? null,
    created_at: row.created_at,
  };
}

/** Map production_line row → twin world state */
export function mapProductionLineToWorldState(row) {
  const slots = processSlotsFromLine(row);
  const robot = robotFromDbRow(row);
  const holding = holdingFromLine(row, robot);
  const reject = rejectFromLine(row, robot);

  const stations = STATION_DEFS.map((def, i) => ({
    id: def.id,
    label: def.label,
    status: mapPosStatus(slots[i].present, slots[i].status),
  }));

  const transfer =
    robot.currSlot != null &&
    robot.nextSlot != null &&
    robot.currSlot !== robot.nextSlot
      ? {
          fromSlot: robot.currSlot,
          toSlot: robot.nextSlot,
          fromStationId: slotToStationId(robot.currSlot),
          toStationId: slotToStationId(robot.nextSlot),
        }
      : null;

  return {
    timestamp: row?.created_at
      ? new Date(row.created_at).toISOString()
      : new Date().toISOString(),
    source: 'database',
    readOnly: true,
    line: lineMeta(slots, row, robot),
    stations,
    holding,
    reject,
    packagingQueue: [],
    scrapped: [],
    boxes: buildBoxFromProcessSlots(slots, row?.id, robot),
    robot,
    transfer,
    qc: { lastResult: qcFromPos3(slots) },
    db: {
      table: 'production_line',
      row: dbRowSnapshot(row),
    },
  };
}
