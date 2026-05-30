import * as THREE from 'three';
import { RobotModel } from './RobotModel.js';
import { CARRIED_BOX_LOCAL } from './robot-arm-constants.js';
import { BOX_CENTER_Y, worldPointForPick } from './workspace-positions.js';
import { boxDisplay } from './pick-visual.js';
import { craneBaseYaw } from './crane-base-yaw.js';
import { carryArcActive, craneAim } from './crane-aim.js';
import { transferMotionBlend } from './transfer-controller.js';
import {
  TIMING,
  TransferController,
  presenceSlotFromState,
} from './transfer-controller.js';
import { slotFromStationId } from '../data/positions.js';
import {
  beltXForSlot,
  beltXFromPosition,
  holdingVector,
  rejectVector,
  LINE_LAYOUT,
} from './line-layout.js';
import { createLineTable } from './line-table.js';
import {
  applyBoxAppearance,
  boxAppearanceFromState,
} from './box-visual.js';

const GRIP_LOCAL = new THREE.Vector3(
  CARRIED_BOX_LOCAL.x,
  CARRIED_BOX_LOCAL.y,
  CARRIED_BOX_LOCAL.z,
);

const STATUS_COLOR = {
  idle: 0x484f58,
  busy: 0xd29922,
  pass: 0x3fb950,
  fail: 0xf85149,
  halted: 0x6e7681,
};

const HOLDING_POSITION = holdingVector();
const REJECT_POSITION = rejectVector();

export class ProductionLine {
  group = new THREE.Group();
  #stations = [];
  #sideBayMeshes = new Map();
  #belt;
  #lineBox;
  #carriedBox;
  #robot;
  #transfer = new TransferController();
  #aimPoint = new THREE.Vector3();
  #worldScratch = new THREE.Vector3();
  #beltHalted = null;
  #stationStatus = [];

  constructor() {
    const { belt, stationX, mainRowZ, padSize, padY } = LINE_LAYOUT;

    this.group.add(createLineTable());

    this.#belt = new THREE.Mesh(
      new THREE.BoxGeometry(belt.length, 0.12, belt.width),
      new THREE.MeshStandardMaterial({ color: 0x21262d, metalness: 0.15 }),
    );
    this.#belt.position.set(0, belt.y, belt.z);
    this.#belt.castShadow = true;
    this.#belt.receiveShadow = true;
    this.group.add(this.#belt);

    const railMat = new THREE.MeshStandardMaterial({ color: 0x30363d });
    const railInset = belt.width / 2 + 0.06;
    for (const side of [-railInset, railInset]) {
      const rail = new THREE.Mesh(
        new THREE.BoxGeometry(belt.length, 0.2, 0.06),
        railMat,
      );
      rail.position.set(0, belt.y + 0.12, belt.z + side);
      this.group.add(rail);
    }

    for (let i = 0; i < stationX.length; i++) {
      const pad = new THREE.Mesh(
        new THREE.BoxGeometry(padSize, 0.06, padSize),
        new THREE.MeshStandardMaterial({
          color: STATUS_COLOR.idle,
          emissive: 0x000000,
          emissiveIntensity: 0.35,
          transparent: true,
          opacity: 0.85,
        }),
      );
      pad.position.set(stationX[i], padY, mainRowZ);
      pad.receiveShadow = true;
      this.group.add(pad);
      this.#stations.push({ mesh: pad });
    }

    this.#createSideBay('holding', HOLDING_POSITION, 0x484f58);
    this.#createSideBay('reject', REJECT_POSITION, 0x3d2020);

    this.#robot = new RobotModel();
    this.group.add(this.#robot.group);

    const { boxFootprint, boxHeight } = LINE_LAYOUT;
    this.#lineBox = new THREE.Mesh(
      new THREE.BoxGeometry(boxFootprint, boxHeight, boxFootprint),
      new THREE.MeshStandardMaterial({ color: 0xc9d1d9 }),
    );
    this.#lineBox.castShadow = true;
    this.group.add(this.#lineBox);

    this.#carriedBox = new THREE.Mesh(
      new THREE.BoxGeometry(boxFootprint * 0.92, boxHeight * 0.92, boxFootprint * 0.92),
      new THREE.MeshStandardMaterial({ color: 0xc9d1d9 }),
    );
    this.#carriedBox.castShadow = true;
    this.#carriedBox.visible = false;
    this.group.add(this.#carriedBox);
  }

  #createSideBay(id, position, idleColor) {
    const pad = new THREE.Mesh(
      new THREE.BoxGeometry(LINE_LAYOUT.padSize, 0.06, LINE_LAYOUT.padSize),
      new THREE.MeshStandardMaterial({
        color: idleColor,
        emissive: 0x000000,
        emissiveIntensity: 0.3,
      }),
    );
    pad.position.copy(position);
    pad.receiveShadow = true;
    this.group.add(pad);
    this.#sideBayMeshes.set(id, { pad, item: null });
  }

  #sideBayColor(slot) {
    if (slot.id === 'reject') {
      if (!slot.occupied) return 0x3d2020;
      return 0xf85149;
    }
    if (!slot.occupied) return 0x484f58;
    if (slot.awaitingReview) return 0xa371f7;
    return 0xd29922;
  }

  #sideBayItemPosition(id) {
    return id === 'reject' ? REJECT_POSITION : HOLDING_POSITION;
  }

  #ensureSideBayItem(id, pos) {
    const entry = this.#sideBayMeshes.get(id);
    if (!entry) return;

    if (!entry.item) {
      const fp = LINE_LAYOUT.boxFootprint * 0.92;
      const h = LINE_LAYOUT.boxHeight * 0.92;
      entry.item = new THREE.Mesh(
        new THREE.BoxGeometry(fp, h, fp),
        new THREE.MeshStandardMaterial({ color: 0xc9d1d9 }),
      );
      entry.item.castShadow = true;
      entry.item.position.set(pos.x, BOX_CENTER_Y, pos.z);
      this.group.add(entry.item);
    }
    entry.item.visible = true;
  }

  #hideSideBayItem(id) {
    const entry = this.#sideBayMeshes.get(id);
    if (entry?.item) entry.item.visible = false;
  }

  #syncSideBaySlots(slots, look) {
    for (const slot of slots ?? []) {
      const entry = this.#sideBayMeshes.get(slot.id);
      if (!entry) continue;
      const padColor = this.#sideBayColor(slot);
      entry.pad.material.color.setHex(padColor);
      entry.pad.material.emissive.setHex(padColor);
      if (slot.occupied && !slot.hideItem) {
        this.#ensureSideBayItem(slot.id, this.#sideBayItemPosition(slot.id));
        if (entry.item) {
          applyBoxAppearance(entry.item, {
            ...look,
            faulty: look.faulty || !!slot.faulty,
          });
        }
      } else {
        this.#hideSideBayItem(slot.id);
      }
    }
  }

  #localFromWorld(world) {
    this.#worldScratch.copy(world);
    this.group.worldToLocal(this.#worldScratch);
    return this.#worldScratch;
  }

  #attachCarriedToGripper() {
    const mount = this.#robot.gripperMount;
    if (this.#carriedBox.parent !== mount) {
      mount.add(this.#carriedBox);
    }
    this.#carriedBox.position.copy(GRIP_LOCAL);
    this.#carriedBox.rotation.set(0, 0, 0);
  }

  #detachCarriedToLine() {
    if (this.#carriedBox.parent !== this.group) {
      this.group.add(this.#carriedBox);
    }
  }

  #syncBoxes(state, tr, delta, halted) {
    const look = boxAppearanceFromState(state, halted);
    this.#lineBox.visible = false;
    this.#carriedBox.visible = false;
    this.#detachCarriedToLine();
    this.#hideSideBayItem('holding');
    this.#hideSideBayItem('reject');

    const show = boxDisplay(state, tr);

    if (show.type === 'belt') {
      const box = state.boxes.find((b) => b.onLine);
      if (!box) return;

      let targetX = beltXFromPosition(box.position);
      const slot = show.slot ?? slotFromStationId(box.stationId);
      if (slot >= 1 && slot <= 4) {
        targetX = beltXForSlot(slot);
      } else {
        const ps = presenceSlotFromState(state);
        if (ps >= 1 && ps <= 4) targetX = beltXForSlot(ps);
      }

      this.#lineBox.visible = true;
      if (tr.active) {
        this.#lineBox.position.x +=
          (targetX - this.#lineBox.position.x) * Math.min(1, delta * 8);
      } else {
        this.#lineBox.position.x = targetX;
      }
      this.#lineBox.position.y = BOX_CENTER_Y;
      this.#lineBox.position.z = LINE_LAYOUT.mainRowZ;
      applyBoxAppearance(this.#lineBox, {
        ...look,
        faulty: look.faulty || !!box.faulty,
      });
      return;
    }

    if (show.type === 'holding' || show.type === 'reject') {
      this.#syncSideBaySlots(
        show.type === 'holding' ? state.holding : state.reject,
        look,
      );
      return;
    }

    if (show.type === 'gripper') {
      applyBoxAppearance(this.#carriedBox, look);

      if (show.fromSlot === 5 && tr.elapsed >= TIMING.GRIP_CLOSE) {
        this.#hideSideBayItem('holding');
      }

      if (show.placeSlot != null && show.placeT != null && show.placeT > 0) {
        this.#detachCarriedToLine();
        const grip = this.#localFromWorld(this.#robot.gripperWorld);
        const dest = this.#localFromWorld(worldPointForPick(show.placeSlot));
        this.#carriedBox.visible = true;
        this.#carriedBox.position.lerpVectors(grip, dest, show.placeT);
        return;
      }

      this.#attachCarriedToGripper();
      this.#carriedBox.visible = true;
    }
  }

  update(state, delta) {
    const halted = state.line?.status === 'halted';
    const tr = this.#transfer.update(state, delta);
    const aim = craneAim(tr, this.#aimPoint);

    if (halted !== this.#beltHalted) {
      this.#beltHalted = halted;
      this.#belt.material.color.setHex(halted ? 0x490202 : 0x21262d);
      this.#belt.material.emissive.setHex(halted ? 0xda3633 : 0x000000);
      this.#belt.material.emissiveIntensity = halted ? 0.25 : 0;
    }

    state.stations.forEach((s, i) => {
      const entry = this.#stations[i];
      if (!entry) return;
      if (this.#stationStatus[i] === s.status) return;
      this.#stationStatus[i] = s.status;
      const c = STATUS_COLOR[s.status] ?? STATUS_COLOR.idle;
      entry.mesh.material.color.setHex(c);
      entry.mesh.material.emissive.setHex(c);
    });

    this.#syncSideBaySlots(state.holding, boxAppearanceFromState(state, halted));
    this.#syncSideBaySlots(state.reject, boxAppearanceFromState(state, halted));

    this.#syncBoxes(state, tr, delta, halted);

    this.#robot.update(
      {
        robot: state.robot,
        robotAim: aim,
        robotGripping: tr.gripping,
        transferActive: tr.active,
        transferMotionBlend: tr.active ? transferMotionBlend(tr.elapsed) : 1,
        robotBaseYaw: craneBaseYaw(tr),
        carryArc: carryArcActive(tr),
      },
      delta,
    );
  }
}
