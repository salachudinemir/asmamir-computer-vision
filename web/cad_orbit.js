import * as THREE from "three";

/** Same default as three.js OrbitControls.rotateSpeed. Airbus and Deagle share this. */
export const ORBIT_ROTATE_SPEED = 1.0;

const PHI_EPS = 1e-6;
const offset = new THREE.Vector3();
const spherical = new THREE.Spherical();

/**
 * OrbitControls mouse rotate: unlimited yaw (θ), polar φ in (0, π) — full tumble
 * with only the gimbal epsilon. dx/dy are normalized 0–1 landmark deltas.
 * Pixel mapping matches handleMouseMoveRotate: 2π * pixelDelta / clientHeight.
 */
export function applySphericalOrbit(camera, target, dx, dy, viewport, speed = ORBIT_ROTATE_SPEED) {
  const w = Math.max(1, viewport.clientWidth || innerWidth);
  const h = Math.max(1, viewport.clientHeight || innerHeight);
  offset.copy(camera.position).sub(target);
  spherical.setFromVector3(offset);
  spherical.theta -= ((2 * Math.PI * (dx * w)) / h) * speed;
  spherical.phi -= 2 * Math.PI * dy * speed;
  spherical.phi = Math.max(PHI_EPS, Math.min(Math.PI - PHI_EPS, spherical.phi));
  spherical.makeSafe();
  offset.setFromSpherical(spherical);
  camera.position.copy(target).add(offset);
  camera.lookAt(target);
}

export function unlockOrbit(orbit) {
  orbit.minAzimuthAngle = -Infinity;
  orbit.maxAzimuthAngle = Infinity;
  orbit.minPolarAngle = 0;
  orbit.maxPolarAngle = Math.PI;
  orbit.rotateSpeed = ORBIT_ROTATE_SPEED;
}
