import * as THREE from 'three';

export const BOX_COLOR = {
  normal: 0xc9d1d9,
  approved: 0x3fb950,
  halted: 0x8b949e,
  faultyRed: 0xe53935,
  faultyTop: 0x161b22,
};

/** Match DB / line item status strings (incl. FAULTY). */
export function isFaultyStatus(status) {
  const s = String(status ?? '').toLowerCase().trim();
  return s.includes('faulty') || s.includes('fail');
}

let faultyMaterials = null;

/** Six-face materials: red sides, black top (+Y). */
export function faultyBoxMaterials() {
  if (faultyMaterials) return faultyMaterials;
  const red = new THREE.MeshStandardMaterial({
    color: BOX_COLOR.faultyRed,
    metalness: 0.12,
    roughness: 0.55,
  });
  const black = new THREE.MeshStandardMaterial({
    color: BOX_COLOR.faultyTop,
    metalness: 0.2,
    roughness: 0.45,
  });
  faultyMaterials = [red, red, black, red, red, red];
  return faultyMaterials;
}

/**
 * @param {THREE.Mesh} mesh
 * @param {{ faulty?: boolean, approved?: boolean, halted?: boolean }} opts
 */
export function applyBoxAppearance(mesh, opts) {
  const { faulty, approved, halted } = opts;

  if (faulty) {
    mesh.material = faultyBoxMaterials();
    return;
  }

  const color = halted
    ? BOX_COLOR.halted
    : approved
      ? BOX_COLOR.approved
      : BOX_COLOR.normal;

  if (Array.isArray(mesh.material)) {
    mesh.material = new THREE.MeshStandardMaterial({ color });
  } else {
    mesh.material.color.setHex(color);
  }
}

export function boxAppearanceFromState(state, halted) {
  const onLine = state.boxes?.find((b) => b.onLine);
  const faulty =
    state.boxes?.some((b) => b.faulty) ||
    state.holding?.some((h) => h.occupied && h.faulty) ||
    state.reject?.some((r) => r.occupied && r.faulty);
  const approved =
    onLine?.humanApproved || state.boxes?.some((b) => b.humanApproved);
  return { faulty, approved, halted };
}
