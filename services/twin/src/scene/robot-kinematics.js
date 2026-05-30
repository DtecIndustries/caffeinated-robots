import * as THREE from 'three';
import {
  ARM,
  CLAW_MOUNT_ROT_X,
  HOOK_LOCAL,
  L1,
  L2,
  SHOULDER_MOUNT_Y,
  WRIST_EXT_MAX,
  POSE_SIZE,
} from './robot-arm-constants.js';

const HOOK_OFFSET = new THREE.Vector3(HOOK_LOCAL.x, HOOK_LOCAL.y, HOOK_LOCAL.z);

const LIMITS = {
  shoulder: [-1.48, 0.22],
  midBoom: [-1.15, 0.75],
  elbow: [-2.35, 0.35],
  wrist: [-2.5, 0.35],
};

const JOINT_NODES = ['shoulder', 'midBoom', 'elbow', 'wrist'];

const SEED_TRIALS = [
  [0, 0, 0, 0],
  [-0.4, -0.2, -0.25, 0.12],
  [-0.85, -0.35, -0.55, 0.28],
  [-1.15, -0.5, -0.9, 0.42],
  [0.2, 0.1, 0.12, -0.08],
  [-0.55, -0.3, -1.15, 0.55],
  [-0.05, -0.1, -0.05, -0.65],
];

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

let chain;

function ensureChain() {
  if (chain) return chain;
  const root = new THREE.Group();
  const base = new THREE.Group();
  root.add(base);

  const shoulder = new THREE.Group();
  shoulder.position.y = SHOULDER_MOUNT_Y;
  base.add(shoulder);

  const midBoom = new THREE.Group();
  midBoom.position.y = ARM.hub + ARM.boomLower;
  shoulder.add(midBoom);

  const elbow = new THREE.Group();
  elbow.position.y = ARM.boomUpper;
  midBoom.add(elbow);

  const wrist = new THREE.Group();
  wrist.position.y = L2;
  elbow.add(wrist);

  const foreMount = new THREE.Group();
  wrist.add(foreMount);

  const wristBeam = new THREE.Group();
  foreMount.add(wristBeam);

  const gripper = new THREE.Group();
  wrist.add(gripper);

  const clawMount = new THREE.Group();
  clawMount.rotation.x = CLAW_MOUNT_ROT_X;
  gripper.add(clawMount);

  const hook = new THREE.Object3D();
  hook.position.copy(HOOK_OFFSET);
  clawMount.add(hook);

  chain = {
    root,
    base,
    shoulder,
    midBoom,
    elbow,
    wrist,
    foreMount,
    wristBeam,
    gripper,
    clawMount,
    hook,
  };
  return chain;
}

function applyPoseToChain(c, robotPosition, baseYaw, pose, wristScale) {
  const s = clamp(wristScale, 1, WRIST_EXT_MAX);
  const len = ARM.wristLink * s;
  c.root.position.copy(robotPosition);
  c.base.rotation.set(0, baseYaw, 0);
  c.shoulder.rotation.set(pose[1], 0, 0);
  c.midBoom.rotation.set(pose[2], 0, 0);
  c.elbow.rotation.set(pose[3], 0, 0);
  c.wrist.rotation.set(pose[4], 0, 0);
  c.wristBeam.scale.set(1, s, 1);
  c.wristBeam.position.y = len / 2;
  c.gripper.position.y = len;
  c.gripper.rotation.set(0, 0, pose[5] ?? 0);
  c.clawMount.rotation.x = CLAW_MOUNT_ROT_X;
  c.root.updateMatrixWorld(true);
}

export function fkHookWorld(robotPosition, baseYaw, pose, wristScale, out) {
  const c = ensureChain();
  applyPoseToChain(c, robotPosition, baseYaw, pose, wristScale);
  return c.hook.getWorldPosition(out);
}

const _hook = new THREE.Vector3();
const _axis = new THREE.Vector3();
const _a = new THREE.Vector3();
const _b = new THREE.Vector3();
const _cross = new THREE.Vector3();
const _joint = new THREE.Vector3();

function projectOnPlane(v, axis, out) {
  const k = v.dot(axis);
  return out.copy(v).addScaledVector(axis, -k);
}

function ccdStep(joint, jointKey, hook, target) {
  joint.getWorldPosition(_joint);
  hook.getWorldPosition(_hook);

  const toHook = _a.copy(_hook).sub(_joint);
  const toTarget = _b.copy(target).sub(_joint);
  if (toHook.lengthSq() < 1e-8 || toTarget.lengthSq() < 1e-8) return;

  _axis.setFromMatrixColumn(joint.matrixWorld, 0).normalize();
  projectOnPlane(toHook, _axis, _a);
  projectOnPlane(toTarget, _axis, _b);
  if (_a.lengthSq() < 1e-8 || _b.lengthSq() < 1e-8) return;

  _a.normalize();
  _b.normalize();
  _cross.crossVectors(_a, _b);
  const delta = Math.atan2(_cross.dot(_axis), _a.dot(_b));
  const [lo, hi] = LIMITS[jointKey];
  joint.rotation.x = clamp(joint.rotation.x + delta, lo, hi);
}

function syncPoseFromChain(c, pose) {
  pose[1] = c.shoulder.rotation.x;
  pose[2] = c.midBoom.rotation.x;
  pose[3] = c.elbow.rotation.x;
  pose[4] = c.wrist.rotation.x;
}

function runCcd(
  c,
  robotPosition,
  baseYaw,
  worldTarget,
  pose,
  wristScale,
  maxPasses = 32,
) {
  let scale = clamp(wristScale, 1, WRIST_EXT_MAX);
  applyPoseToChain(c, robotPosition, baseYaw, pose, scale);

  for (let pass = 0; pass < maxPasses; pass++) {
    for (const key of JOINT_NODES) {
      ccdStep(c[key], key, c.hook, worldTarget);
      syncPoseFromChain(c, pose);
    }
    applyPoseToChain(c, robotPosition, baseYaw, pose, scale);

    c.hook.getWorldPosition(_hook);
    const err = _hook.distanceTo(worldTarget);
    if (err < 0.022) break;

    if (err > 0.06 && scale < WRIST_EXT_MAX) {
      scale = Math.min(WRIST_EXT_MAX, scale + 0.04);
    }
  }

  return scale;
}

function scaleCandidates(worldTarget, robotPosition, seedScale) {
  const s = clamp(seedScale, 1, WRIST_EXT_MAX);
  const out = new Set([s]);
  const step = 0.12;
  if (s + step <= WRIST_EXT_MAX) out.add(s + step);
  if (s - step >= 1) out.add(s - step);
  const dist = robotPosition.distanceTo(worldTarget);
  if (dist > 3.4 && s < WRIST_EXT_MAX - 0.2) {
    out.add(WRIST_EXT_MAX);
  }
  return [...out];
}

function solveTrial(worldTarget, robotPosition, baseYaw, seedPose, seedScale) {
  const c = ensureChain();
  let best = null;

  for (const scale0 of scaleCandidates(worldTarget, robotPosition, seedScale)) {
    const pose = seedPose.slice(0, POSE_SIZE);
    const wristScale = runCcd(
      c,
      robotPosition,
      baseYaw,
      worldTarget,
      pose,
      scale0,
    );
    fkHookWorld(robotPosition, baseYaw, pose, wristScale, _hook);
    const err2 = _hook.distanceToSquared(worldTarget);
    if (!best || err2 < best.err2) {
      best = { pose: pose.slice(), wristScale, err2 };
    }
  }

  return best;
}

const _workPose = [0, 0, 0, 0, 0, 0, 0];

export function solveHookIKFast(
  worldTarget,
  robotPosition,
  baseYaw,
  seedPose,
  seedScale = 1,
) {
  const c = ensureChain();
  for (let i = 0; i < POSE_SIZE; i++) _workPose[i] = seedPose[i] ?? 0;

  const wristScale = runCcd(
    c,
    robotPosition,
    baseYaw,
    worldTarget,
    _workPose,
    seedScale,
    22,
  );
  return { pose: _workPose, wristScale };
}

function hookErrorSq(worldTarget, robotPosition, baseYaw, pose, wristScale) {
  fkHookWorld(robotPosition, baseYaw, pose, wristScale, _hook);
  return _hook.distanceToSquared(worldTarget);
}

export function solveHookIK(
  worldTarget,
  robotPosition,
  baseYaw,
  seedPose,
  seedScale = 1,
) {
  let best = solveTrial(worldTarget, robotPosition, baseYaw, seedPose, seedScale);

  for (const [ds, dm, de, dw] of SEED_TRIALS) {
    const trial = seedPose.slice(0, POSE_SIZE);
    trial[1] = clamp(trial[1] + ds, ...LIMITS.shoulder);
    trial[2] = clamp(trial[2] + dm, ...LIMITS.midBoom);
    trial[3] = clamp(trial[3] + de, ...LIMITS.elbow);
    trial[4] = clamp(trial[4] + dw, ...LIMITS.wrist);
    const r = solveTrial(worldTarget, robotPosition, baseYaw, trial, seedScale);
    if (r.err2 < best.err2) best = r;
  }

  return { pose: best.pose, wristScale: best.wristScale };
}

/** Fast IK only — for carry / animation frames (avoids fast↔full flicker). */
export function solveHookIKStable(
  worldTarget,
  robotPosition,
  baseYaw,
  seedPose,
  seedScale = 1,
) {
  return solveHookIKFast(
    worldTarget,
    robotPosition,
    baseYaw,
    seedPose,
    seedScale,
    30,
  );
}

let lastFullSolveAt = 0;

export function solveHookIKAdaptive(
  worldTarget,
  robotPosition,
  baseYaw,
  seedPose,
  seedScale = 1,
) {
  const fast = solveHookIKFast(
    worldTarget,
    robotPosition,
    baseYaw,
    seedPose,
    seedScale,
  );
  const errSq = hookErrorSq(
    worldTarget,
    robotPosition,
    baseYaw,
    fast.pose,
    fast.wristScale,
  );
  if (errSq < 0.025) {
    return fast;
  }
  const now = performance.now();
  if (now - lastFullSolveAt < 120) {
    return fast;
  }
  const full = solveHookIK(
    worldTarget,
    robotPosition,
    baseYaw,
    seedPose,
    seedScale,
  );
  lastFullSolveAt = now;
  if (
    errSq <=
    hookErrorSq(
      worldTarget,
      robotPosition,
      baseYaw,
      full.pose,
      full.wristScale,
    )
  ) {
    return fast;
  }
  return full;
}

export { HOOK_OFFSET as HOOK_LOCAL, WRIST_EXT_MAX as KINEMATICS_WRIST_EXT_MAX };
