import {
  parseRobotJoints,
  parseRobotSlot,
  robotRouteLabel,
} from './positions.js';
import { matchPoseFromDb } from './robot-pose-sequence.js';

function inferAction(poseRaw, transferring, atSlot) {
  if (poseRaw.includes('lower') && poseRaw.includes('gripper_closed')) {
    return 'pick';
  }
  if (poseRaw.includes('pick')) return 'pick';
  if (poseRaw.includes('place')) return 'place';
  if (
    transferring ||
    poseRaw.includes('transfer') ||
    poseRaw.includes('move')
  ) {
    return 'transfer';
  }
  if (atSlot != null) return 'idle';
  return 'idle';
}

function isHomePose(poseRaw) {
  return (
    poseRaw.includes('home') ||
    poseRaw.includes('idle') ||
    poseRaw === ''
  );
}

/** Map DB robot_* fields → twin robot state for scene + HUD. */
export function robotFromDbRow(row) {
  const currSlot = parseRobotSlot(row?.robot_curr_pos);
  const nextSlot = parseRobotSlot(row?.robot_next_pos);
  const poseRaw = String(row?.robot_pose ?? '')
    .trim()
    .toLowerCase();
  const joints =
    parseRobotJoints(row?.robot_joints) ?? matchPoseFromDb(poseRaw);

  const transferring =
    nextSlot != null &&
    (currSlot !== nextSlot || (currSlot == null && nextSlot != null));

  const atSlot = currSlot ?? nextSlot;

  const action = inferAction(poseRaw, transferring, atSlot);

  const carrying =
    poseRaw.includes('part_true') ||
    (transferring &&
      !isHomePose(poseRaw) &&
      (poseRaw.includes('carry') ||
        poseRaw.includes('lower') ||
        (poseRaw.includes('place') && !poseRaw.includes('part_false'))));

  return {
    currSlot,
    nextSlot,
    joints,
    targetJoints: null,
    jointMode: false,
    pose: poseRaw || null,
    action: transferring && action === 'idle' ? 'transfer' : action,
    transferring,
    carrying,
    routeLabel: robotRouteLabel(currSlot, nextSlot, transferring),
  };
}

export const DEFAULT_ROBOT = robotFromDbRow({});
