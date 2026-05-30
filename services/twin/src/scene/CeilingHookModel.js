import * as THREE from 'three';
import { LINE_LAYOUT } from './line-layout.js';
import { CEILING_Y, hookHomeX } from './hook-visual.js';

const LERP = 4;
const BOX_HANG = 0.28;

export class CeilingHookModel {
  group = new THREE.Group();
  #carriage = new THREE.Group();
  #cable;
  #hook;
  #fingerL;
  #fingerR;
  #gripper;
  #gripperWorld = new THREE.Vector3();
  #display = {
    x: hookHomeX(),
    z: LINE_LAYOUT.mainRowZ,
    headY: CEILING_Y,
    gripping: false,
    clawOpen: 0,
  };

  constructor() {
    const railLen = LINE_LAYOUT.belt.length + 1.2;
    const rail = new THREE.Mesh(
      new THREE.BoxGeometry(railLen, 0.14, 0.22),
      new THREE.MeshStandardMaterial({
        color: 0x30363d,
        metalness: 0.5,
        roughness: 0.45,
      }),
    );
    rail.position.set(0, CEILING_Y, LINE_LAYOUT.mainRowZ);
    rail.castShadow = true;
    this.group.add(rail);

    for (const xOff of [-railLen / 2, railLen / 2]) {
      const post = new THREE.Mesh(
        new THREE.BoxGeometry(0.14, 0.5, 0.14),
        rail.material,
      );
      post.position.set(xOff, CEILING_Y + 0.25, LINE_LAYOUT.mainRowZ);
      this.group.add(post);
    }

    const carriageBody = new THREE.Mesh(
      new THREE.BoxGeometry(0.55, 0.2, 0.4),
      new THREE.MeshStandardMaterial({
        color: 0x58a6ff,
        metalness: 0.65,
        roughness: 0.3,
      }),
    );
    carriageBody.castShadow = true;
    this.#carriage.add(carriageBody);
    this.#carriage.position.y = CEILING_Y;
    this.group.add(this.#carriage);

    const cableMat = new THREE.MeshStandardMaterial({
      color: 0xd29922,
      metalness: 0.4,
      roughness: 0.5,
    });
    this.#cable = new THREE.Mesh(
      new THREE.CylinderGeometry(0.035, 0.04, 1, 10),
      cableMat,
    );
    this.#cable.position.y = -0.5;
    this.#carriage.add(this.#cable);

    this.#hook = new THREE.Group();
    this.#hook.position.y = -1;
    this.#carriage.add(this.#hook);

    const shank = new THREE.Mesh(
      new THREE.BoxGeometry(0.1, 0.14, 0.1),
      new THREE.MeshStandardMaterial({ color: 0x8b949e, metalness: 0.55 }),
    );
    shank.position.y = -0.07;
    this.#hook.add(shank);

    const fingerMat = new THREE.MeshStandardMaterial({
      color: 0xc9d1d9,
      metalness: 0.5,
    });
    const fingerGeo = new THREE.BoxGeometry(0.05, 0.22, 0.06);

    this.#fingerL = new THREE.Mesh(fingerGeo, fingerMat);
    this.#fingerL.position.set(-0.09, -0.2, 0);
    this.#fingerL.rotation.z = 0.35;
    this.#hook.add(this.#fingerL);

    this.#fingerR = new THREE.Mesh(fingerGeo, fingerMat);
    this.#fingerR.position.set(0.09, -0.2, 0);
    this.#fingerR.rotation.z = -0.35;
    this.#hook.add(this.#fingerR);

    this.#gripper = new THREE.Group();
    this.#gripper.position.y = -0.28;
    this.#hook.add(this.#gripper);

    this.#applyDisplay();
  }

  get gripperMount() {
    return this.#gripper;
  }

  get gripperWorld() {
    return this.#gripperWorld;
  }

  #applyDisplay() {
    const { x, z, headY, gripping, clawOpen = 0 } = this.#display;
    this.#carriage.position.set(x, CEILING_Y, z);

    const drop = CEILING_Y - headY;
    this.#cable.scale.y = Math.max(0.15, drop);
    this.#cable.position.y = -drop / 2;
    this.#hook.position.y = -drop;

    const spread = gripping ? 0.04 : 0.08 + clawOpen * 0.1;
    this.#fingerL.rotation.z = 0.35 + spread;
    this.#fingerR.rotation.z = -0.35 - spread;

    this.#gripper.getWorldPosition(this.#gripperWorld);
  }

  update(target, delta) {
    const t = Math.min(1, delta * LERP);
    this.#display.x += (target.x - this.#display.x) * t;
    this.#display.z += (target.z - this.#display.z) * t;
    this.#display.headY += (target.headY - this.#display.headY) * t;
    this.#display.gripping = target.gripping;
    this.#display.clawOpen = target.clawOpen ?? (target.gripping ? 0 : 1);
    this.#applyDisplay();
  }
}

export const HOOK_BOX_OFFSET = new THREE.Vector3(0, -BOX_HANG, 0);
