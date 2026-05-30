import * as THREE from 'three';

/**
 * Low-pass filter on IK targets — stops frame-to-frame IK flipping.
 * @param {THREE.Vector3} raw
 * @param {THREE.Vector3} filtered — persistent smoothed value (mutated)
 * @param {{ init: boolean }} state
 * @param {number} alpha — 0..1, higher = snappier
 */
export function smoothAimPoint(raw, filtered, state, alpha = 0.22) {
  if (!state.init) {
    filtered.copy(raw);
    state.init = true;
    return filtered;
  }
  const distSq = filtered.distanceToSquared(raw);
  if (distSq < 1e-8) {
    return filtered;
  }
  filtered.lerp(raw, alpha);
  return filtered;
}

export function resetAimSmoothing(filtered, point) {
  filtered.copy(point);
}
