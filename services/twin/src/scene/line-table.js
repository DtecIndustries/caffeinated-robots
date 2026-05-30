import * as THREE from 'three';
import { LINE_LAYOUT, STATION_LABELS } from './line-layout.js';

const TAPE = 0xe6edf3;
const TABLE = 0x2d333b;

/**
 * Tabletop + masking-tape grid matching the physical line.
 * @returns {THREE.Group}
 */
export function createLineTable() {
  const root = new THREE.Group();
  const { padSize, stationX, mainRowZ, holding, reject, table } = LINE_LAYOUT;
  const half = padSize / 2;

  const top = new THREE.Mesh(
    new THREE.BoxGeometry(table.width, 0.06, table.depth),
    new THREE.MeshStandardMaterial({ color: TABLE, roughness: 0.85 }),
  );
  top.position.set(0, table.y, -0.55);
  top.receiveShadow = true;
  root.add(top);

  const tapeMat = new THREE.LineBasicMaterial({ color: TAPE });
  const y = table.y + 0.031;

  const addRect = (cx, cz) => {
    const pts = [
      new THREE.Vector3(cx - half, y, cz - half),
      new THREE.Vector3(cx + half, y, cz - half),
      new THREE.Vector3(cx + half, y, cz + half),
      new THREE.Vector3(cx - half, y, cz + half),
      new THREE.Vector3(cx - half, y, cz - half),
    ];
    root.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), tapeMat));
  };

  for (const x of stationX) addRect(x, mainRowZ);
  addRect(holding.x, holding.z);
  addRect(reject.x, reject.z);

  const label = (text, x, z) => {
    const canvas = document.createElement('canvas');
    canvas.width = 160;
    canvas.height = 36;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#8b949e';
    ctx.font = 'bold 13px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText(text, 80, 24);
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: new THREE.CanvasTexture(canvas),
        transparent: true,
      }),
    );
    sprite.scale.set(1.35, 0.32, 1);
    sprite.position.set(x, 0.88, z);
    root.add(sprite);
  };

  STATION_LABELS.forEach((name, i) => label(name, stationX[i], mainRowZ));
  label('Holding', holding.x, holding.z);
  label('Reject', reject.x, reject.z);

  return root;
}
