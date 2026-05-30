import * as THREE from 'three';
import { LINE_LAYOUT } from './line-layout.js';
import { ROBOT_LINE_GAZE, ROBOT_ROW_YAW } from './crane-line.js';
import {
  ARM,
  CARRIED_BOX_LOCAL,
  CLAW_MOUNT_ROT_X,
  expandJoints6,
  HOOK_LOCAL,
  POSE_SIZE,
  ROBOT_SCALE,
} from './robot-arm-constants.js';
import { CLAW_APPROACH_Y } from './line-layout.js';
import {
  solveHookIK,
  solveHookIKAdaptive,
  solveHookIKStable,
} from './robot-kinematics.js';
import { resetAimSmoothing, smoothAimPoint } from './aim-smoothing.js';

const S = ROBOT_SCALE;
const BASE_YAW_LERP = 10;
const GRIP_INDEX = 6;
const WRIST_EXT_MAX = 1.95;

const FALLBACK = [ROBOT_ROW_YAW, -0.55, -0.38, -0.75, 0.35, 0, 0.88];

export const ROBOT_POSES = {
  idle: FALLBACK,
  pick: [ROBOT_ROW_YAW, -0.72, -0.48, -1.05, 0.55, 0.05, 0.12],
  place: [ROBOT_ROW_YAW, -0.68, -0.45, -0.98, 0.52, -0.04, 0.75],
  transfer: [ROBOT_ROW_YAW, -0.7, -0.46, -1.02, 0.5, 0.03, 0.15],
};

export { ROBOT_SCALE };
export const ROBOT_BASE_POSITION = { ...LINE_LAYOUT.robot };

const LERP = 14;
const LERP_LOW = 22;
const LERP_CARRY = 9;
const WRIST_EXT_LERP = 16;
const WRIST_EXT_LERP_LOW = 24;
const WRIST_EXT_LERP_CARRY = 10;

function lerpAngle(current, target, t) {
  let d = target - current;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return current + d * t;
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

/** Twin side-plate rails like the physical arm. */
function addSegmentRails(parent, length, armMat, width = ARM.width) {
  const gap = width * 0.38;
  const railW = width * 0.32;
  const railD = width * 0.72;
  for (const side of [-1, 1]) {
    const rail = new THREE.Mesh(
      new THREE.BoxGeometry(railW, length, railD),
      armMat,
    );
    rail.position.set(side * gap, length / 2, 0);
    rail.castShadow = true;
    parent.add(rail);
  }
}

export class RobotModel {
  group = new THREE.Group();
  #base;
  #shoulder;
  #midBoom;
  #elbow;
  #wristLink;
  #gripper;
  #clawMount;
  #fingerL;
  #fingerR;
  #ring;
  #pose = [...ROBOT_POSES.idle];
  #idlePose = [...ROBOT_POSES.idle];
  #wristScale = 1;
  #targetWristScale = 1;
  #wristBeam;
  #wristSleeve;
  #foreRails;
  #gripperWorld = new THREE.Vector3();
  #hookLocal = new THREE.Vector3(HOOK_LOCAL.x, HOOK_LOCAL.y, HOOK_LOCAL.z);
  #ikTarget = [...FALLBACK];
  #aimFiltered = new THREE.Vector3();
  #aimSmooth = { init: false };
  #transferStartPose = null;
  #transferStartWrist = 1;
  #wasTransferActive = false;
  #baseYaw = ROBOT_ROW_YAW;
  #baseYawTarget = ROBOT_ROW_YAW;

  constructor() {
    this.group.position.set(
      ROBOT_BASE_POSITION.x,
      ROBOT_BASE_POSITION.y,
      ROBOT_BASE_POSITION.z,
    );

    const jointMat = new THREE.MeshStandardMaterial({
      color: 0x1a1a1a,
      metalness: 0.35,
      roughness: 0.55,
    });
    const armMat = new THREE.MeshStandardMaterial({
      color: 0x2a2a2a,
      metalness: 0.5,
      roughness: 0.45,
    });
    const accentMat = new THREE.MeshStandardMaterial({
      color: 0x404040,
      metalness: 0.65,
      roughness: 0.35,
    });

    this.#base = new THREE.Group();
    this.group.add(this.#base);

    const pedestal = new THREE.Mesh(
      new THREE.CylinderGeometry(0.34 * S, 0.4 * S, 0.2 * S, 20),
      jointMat,
    );
    pedestal.position.y = 0.11 * S;
    pedestal.castShadow = true;
    this.#base.add(pedestal);

    this.#ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.32 * S, 0.035 * S, 12, 32),
      new THREE.MeshStandardMaterial({
        color: 0x58a6ff,
        emissive: 0x58a6ff,
        emissiveIntensity: 0.6,
      }),
    );
    this.#ring.rotation.x = Math.PI / 2;
    this.#ring.position.y = 0.24 * S;
    this.#base.add(this.#ring);

    this.#shoulder = new THREE.Group();
    this.#shoulder.position.y = 0.24 * S;
    this.#base.add(this.#shoulder);

    const hub = new THREE.Mesh(
      new THREE.BoxGeometry(0.38 * S, ARM.hub, 0.38 * S),
      jointMat,
    );
    hub.position.y = ARM.hub / 2;
    hub.castShadow = true;
    this.#shoulder.add(hub);

    const lowerMount = new THREE.Group();
    lowerMount.position.y = ARM.hub;
    this.#shoulder.add(lowerMount);
    addSegmentRails(lowerMount, ARM.boomLower, armMat);

    const lowerJoint = new THREE.Mesh(
      new THREE.SphereGeometry(0.12 * S, 12, 12),
      accentMat,
    );
    lowerJoint.position.y = ARM.boomLower;
    lowerMount.add(lowerJoint);

    this.#midBoom = new THREE.Group();
    this.#midBoom.position.y = ARM.hub + ARM.boomLower;
    this.#shoulder.add(this.#midBoom);

    const upperMount = new THREE.Group();
    this.#midBoom.add(upperMount);
    addSegmentRails(upperMount, ARM.boomUpper, armMat);

    const upperJoint = new THREE.Mesh(
      new THREE.SphereGeometry(0.11 * S, 12, 12),
      accentMat,
    );
    upperJoint.position.y = ARM.boomUpper;
    upperMount.add(upperJoint);

    this.#elbow = new THREE.Group();
    this.#elbow.position.y = ARM.boomUpper;
    this.#midBoom.add(this.#elbow);

    this.#elbow.add(
      new THREE.Mesh(new THREE.SphereGeometry(0.1 * S, 10, 10), accentMat),
    );

    const upperMount2 = new THREE.Group();
    this.#elbow.add(upperMount2);
    addSegmentRails(upperMount2, ARM.middle, armMat);

    this.#wristLink = new THREE.Group();
    this.#wristLink.position.y = ARM.middle;
    this.#elbow.add(this.#wristLink);

    this.#wristLink.add(
      new THREE.Mesh(new THREE.SphereGeometry(0.09 * S, 10, 10), accentMat),
    );

    this.#wristSleeve = new THREE.Mesh(
      new THREE.BoxGeometry(ARM.width * 0.5, ARM.wristLink * 0.22, ARM.width * 0.45),
      jointMat,
    );
    this.#wristSleeve.position.y = ARM.wristLink * 0.11;
    this.#wristLink.add(this.#wristSleeve);

    const foreMount = new THREE.Group();
    this.#wristLink.add(foreMount);

    this.#wristBeam = new THREE.Mesh(
      new THREE.BoxGeometry(ARM.width * 0.35, ARM.wristLink, ARM.width * 0.35),
      armMat,
    );
    this.#wristBeam.position.y = ARM.wristLink / 2;
    foreMount.add(this.#wristBeam);

    const foreRails = new THREE.Group();
    foreMount.add(foreRails);
    addSegmentRails(foreRails, ARM.wristLink, armMat, ARM.width * 0.85);
    this.#foreRails = foreRails;

    this.#gripper = new THREE.Group();
    this.#gripper.position.y = ARM.wristLink;
    this.#wristLink.add(this.#gripper);

    this.#clawMount = new THREE.Group();
    this.#clawMount.rotation.x = CLAW_MOUNT_ROT_X;
    this.#gripper.add(this.#clawMount);

    const palm = new THREE.Mesh(
      new THREE.BoxGeometry(0.14 * S, 0.05 * S, 0.12 * S),
      jointMat,
    );
    palm.position.y = 0.02 * S;
    palm.castShadow = true;
    this.#clawMount.add(palm);

    const lens = new THREE.Mesh(
      new THREE.CylinderGeometry(0.045 * S, 0.05 * S, 0.04 * S, 16),
      new THREE.MeshStandardMaterial({
        color: 0x0a0a0a,
        metalness: 0.8,
        roughness: 0.2,
      }),
    );
    lens.rotation.x = Math.PI / 2;
    lens.position.set(0, 0.08 * S, 0);
    this.#clawMount.add(lens);

    const fingerMat = new THREE.MeshStandardMaterial({
      color: 0x1a1a1a,
      metalness: 0.45,
      roughness: 0.48,
    });
    const fingerShape = new THREE.BoxGeometry(0.035 * S, 0.11 * S, 0.055 * S);

    this.#fingerL = new THREE.Mesh(fingerShape, fingerMat);
    this.#fingerL.position.set(-0.075 * S, -0.02 * S, 0);
    this.#fingerL.castShadow = true;
    this.#clawMount.add(this.#fingerL);

    this.#fingerR = new THREE.Mesh(fingerShape, fingerMat);
    this.#fingerR.position.set(0.075 * S, -0.02 * S, 0);
    this.#fingerR.castShadow = true;
    this.#clawMount.add(this.#fingerR);

    for (const finger of [this.#fingerL, this.#fingerR]) {
      for (let i = 0; i < 4; i++) {
        const tooth = new THREE.Mesh(
          new THREE.BoxGeometry(0.008 * S, 0.02 * S, 0.04 * S),
          fingerMat,
        );
        tooth.position.set(0, -0.03 * S - i * 0.022 * S, 0.028 * S);
        finger.add(tooth);
      }
    }

    resetAimSmoothing(this.#aimFiltered, ROBOT_LINE_GAZE);
    this.#aimSmooth.init = true;
    this.#idlePose = [...this.#solveReach(ROBOT_LINE_GAZE.clone(), false)];
    this.#pose = [...this.#idlePose];
    this.#applyPose(this.#pose);
  }

  #solveReach(worldTarget, gripping, { stable = false, transfer = false } = {}) {
    const low = worldTarget.y < CLAW_APPROACH_Y + 0.12;
    const solver =
      transfer || stable
        ? solveHookIKStable
        : low
          ? solveHookIK
          : solveHookIKAdaptive;
    const { pose, wristScale } = solver(
      worldTarget,
      this.group.position,
      this.#baseYaw,
      this.#ikTarget,
      this.#targetWristScale,
    );
    const blend = transfer ? 0.82 : 0.5;
    this.#targetWristScale +=
      (wristScale - this.#targetWristScale) * blend;
    pose[0] = this.#baseYaw;
    pose[GRIP_INDEX] = gripping ? 0.12 : 0.82;
    return pose;
  }

  #applyWristExtension(scale) {
    const s = clamp(scale, 1, WRIST_EXT_MAX);
    const len = ARM.wristLink * s;
    this.#wristBeam.scale.set(1, s, 1);
    this.#wristBeam.position.y = len / 2;
    this.#foreRails.scale.set(1, s, 1);
    this.#foreRails.position.y = 0;
    this.#gripper.position.y = len;
  }

  #applyPose(pose, wristScale = this.#wristScale) {
    const [, shoulder, midBoom, elbow, wrist, roll, gripper] = pose;
    this.#base.rotation.y = this.#baseYaw;
    this.#shoulder.rotation.set(shoulder, 0, 0);
    this.#midBoom.rotation.set(midBoom, 0, 0);
    this.#elbow.rotation.x = elbow;
    this.#elbow.rotation.z = 0;
    this.#wristLink.rotation.x = wrist;
    this.#wristLink.rotation.z = 0;
    this.#gripper.rotation.z = roll;
    this.#clawMount.rotation.x = CLAW_MOUNT_ROT_X;
    this.#applyWristExtension(wristScale);
    const open = gripper * 0.1 * S;
    this.#fingerL.position.x = -0.075 * S - open;
    this.#fingerR.position.x = 0.075 * S + open;
  }

  get gripperMount() {
    return this.#clawMount;
  }

  get gripperOpen() {
    return this.#pose[GRIP_INDEX] ?? 0.88;
  }

  getGripperWorldPosition() {
    this.#gripperWorld.copy(this.#hookLocal);
    return this.#clawMount.localToWorld(this.#gripperWorld);
  }

  update(sceneHints, delta) {
    const transferActive = sceneHints.transferActive === true;

    this.#baseYawTarget = sceneHints.robotBaseYaw ?? ROBOT_ROW_YAW;
    const yawStep = Math.min(1, delta * BASE_YAW_LERP);
    this.#baseYaw = lerpAngle(this.#baseYaw, this.#baseYawTarget, yawStep);

    if (transferActive && !this.#wasTransferActive) {
      this.#transferStartPose = [...this.#pose];
      this.#transferStartWrist = this.#wristScale;
      this.#wasTransferActive = true;
    } else if (!transferActive) {
      this.#wasTransferActive = false;
      this.#transferStartPose = null;
    }

    const resolved = this.#resolvePose(sceneHints);
    const target = Array.isArray(resolved) ? resolved : resolved.pose;
    if (resolved.wristScale != null) {
      this.#targetWristScale = resolved.wristScale;
    } else if (!transferActive) {
      this.#targetWristScale = 1;
    }

    if (transferActive) {
      for (let i = 0; i < POSE_SIZE; i++) {
        this.#pose[i] = target[i] ?? this.#pose[i];
      }
      this.#pose[0] = this.#baseYaw;
      this.#wristScale = this.#targetWristScale;
    } else {
      const aim = sceneHints.robotAim;
      const carryArc = sceneHints.carryArc === true;
      const lowReach =
        !carryArc && aim != null && aim.y < CLAW_APPROACH_Y + 0.08;
      const t = Math.min(
        1,
        delta * (carryArc ? LERP_CARRY : lowReach ? LERP_LOW : LERP),
      );
      const te = Math.min(
        1,
        delta * (carryArc
          ? WRIST_EXT_LERP_CARRY
          : lowReach
            ? WRIST_EXT_LERP_LOW
            : WRIST_EXT_LERP),
      );

      for (let i = 1; i < POSE_SIZE; i++) {
        this.#pose[i] = lerpAngle(this.#pose[i], target[i] ?? this.#pose[i], t);
      }
      this.#pose[0] = this.#baseYaw;
      this.#wristScale += (this.#targetWristScale - this.#wristScale) * te;
    }

    this.#applyPose(this.#pose, this.#wristScale);
    this.#gripperWorld = this.getGripperWorldPosition();

    const action = sceneHints.robot?.action ?? 'idle';
    const accent =
      action === 'pick'
        ? 0x3fb950
        : action === 'place'
          ? 0xd29922
          : action === 'transfer'
            ? 0xa371f7
            : 0x58a6ff;
    this.#ring.material.color.setHex(accent);
    this.#ring.material.emissive.setHex(accent);

    if (!sceneHints.transferActive) {
      this.#aimSmooth.init = false;
      for (let i = 0; i < POSE_SIZE; i++) {
        this.#ikTarget[i] = this.#pose[i];
      }
    }
  }

  get gripperWorld() {
    return this.#gripperWorld;
  }

  #lerpJoints(from, to, t) {
    const a = expandJoints6(from) ?? this.#pose;
    const b = expandJoints6(to) ?? a;
    const out = [];
    for (let i = 0; i < POSE_SIZE; i++) {
      out[i] = lerpAngle(a[i] ?? 0, b[i] ?? 0, t);
    }
    out[0] = this.#baseYaw;
    return out;
  }

  #resolvePose(sceneHints) {
    const robot = sceneHints.robot ?? {};
    const transferT = sceneHints.transferT;
    const aim = sceneHints.robotAim;
    const gripping = sceneHints.robotGripping ?? false;
    const carryArc = sceneHints.carryArc === true;
    const transferActive = sceneHints.transferActive === true;

    if (aim && transferActive) {
      const alpha = carryArc ? 0.12 : 0.22;
      const filtered = smoothAimPoint(
        aim,
        this.#aimFiltered,
        this.#aimSmooth,
        alpha,
      );
      const stableIk = carryArc || filtered.y > CLAW_APPROACH_Y + 0.14;
      const solved = this.#solveReach(filtered, gripping, {
        stable: stableIk,
        transfer: true,
      });
      for (let i = 0; i < POSE_SIZE; i++) this.#ikTarget[i] = solved[i];

      const motionBlend = sceneHints.transferMotionBlend ?? 1;
      if (motionBlend < 1 && this.#transferStartPose) {
        const pose = this.#lerpJoints(
          this.#transferStartPose,
          this.#ikTarget,
          motionBlend,
        );
        const wrist =
          this.#transferStartWrist +
          (this.#targetWristScale - this.#transferStartWrist) * motionBlend;
        return { pose, wristScale: wrist };
      }

      return { pose: this.#ikTarget, wristScale: this.#targetWristScale };
    }

    if (
      robot.jointMode &&
      robot.joints?.length >= 6 &&
      robot.targetJoints?.length >= 6 &&
      transferT != null &&
      transferT < 1
    ) {
      const pose = this.#lerpJoints(robot.joints, robot.targetJoints, transferT);
      pose[0] = this.#baseYaw;
      pose[GRIP_INDEX] = gripping
        ? Math.min(pose[GRIP_INDEX], 0.15)
        : pose[GRIP_INDEX];
      return { pose, wristScale: this.#targetWristScale };
    }

    const action = robot.action ?? 'idle';
    const pose = [
      ...(action === 'idle'
        ? this.#idlePose
        : (ROBOT_POSES[action] ?? this.#idlePose)),
    ];
    pose[0] = this.#baseYaw;
    return { pose, wristScale: 1 };
  }
}
