/** Shared arm dimensions — keep RobotModel and robot-kinematics in sync. */
export const ROBOT_SCALE = 2.35;

const S = ROBOT_SCALE;

export const ARM = {
  hub: 0.18 * S,
  /** Lower boom — proximal segment from shoulder. */
  boomLower: 0.42 * 0.9 * S,
  /** Upper boom — distal segment before elbow. */
  boomUpper: 0.58 * 0.9 * S,
  middle: 0.52 * S,
  wristLink: 0.4 * S,
  width: 0.2 * S,
};

export const SHOULDER_MOUNT_Y = 0.24 * S;
export const L1 = ARM.hub + ARM.boomLower + ARM.boomUpper;
export const L2 = ARM.middle;
export const WRIST_EXT_MAX = 1.95;

/** Claw mount: rotate so fingers open around the box from above. */
export const CLAW_MOUNT_ROT_X = -Math.PI / 2;

/** Pinch center on claw (between finger tips). */
export const HOOK_LOCAL = { x: 0, y: -0.04 * S, z: 0.03 * S };

/** Carried box center in claw mount space (sits under the open claw). */
export const CARRIED_BOX_LOCAL = { x: 0, y: -0.2, z: 0 };

/** [baseY, shoulder, midBoom, elbow, wrist, roll, gripper] */
export const POSE_SIZE = 7;

/** Map legacy 6-joint DB telemetry into the 7-joint visual rig. */
export function expandJoints6(joints) {
  if (!joints?.length) return null;
  if (joints.length >= POSE_SIZE) return joints.slice(0, POSE_SIZE);
  const [base, shoulder, elbow, wrist, roll = 0, grip = 0.88] = joints;
  const midBoom = shoulder * 0.42 + elbow * 0.12;
  return [base, shoulder, midBoom, elbow, wrist, roll, grip];
}
