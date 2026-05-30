import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { ProductionLine } from './ProductionLine.js';

export class SceneManager {
  #canvas;
  #renderer;
  #scene;
  #camera;
  #controls;
  #productionLine;
  #state = null;
  #clock = new THREE.Clock();

  constructor(canvas) {
    this.#canvas = canvas;
    this.#scene = new THREE.Scene();
    this.#scene.background = new THREE.Color(0x0d1117);
    this.#scene.fog = new THREE.Fog(0x0d1117, 12, 28);

    this.#camera = new THREE.PerspectiveCamera(
      50,
      window.innerWidth / window.innerHeight,
      0.1,
      100,
    );
    this.#camera.position.set(4, 6.5, 8);
    this.#camera.lookAt(-0.5, 0, -0.6);

    this.#renderer = new THREE.WebGLRenderer({
      canvas: this.#canvas,
      antialias: true,
    });
    this.#renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.#renderer.setSize(window.innerWidth, window.innerHeight);
    this.#renderer.shadowMap.enabled = true;

    this.#controls = new OrbitControls(this.#camera, this.#canvas);
    this.#controls.enableDamping = true;
    this.#controls.target.set(-0.5, 0.45, -0.55);
    this.#controls.maxPolarAngle = Math.PI / 2.1;

    const ambient = new THREE.AmbientLight(0xffffff, 0.45);
    const dir = new THREE.DirectionalLight(0xffffff, 1.1);
    dir.position.set(6, 10, 4);
    dir.castShadow = true;
    dir.shadow.mapSize.set(1024, 1024);
    this.#scene.add(ambient, dir);

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(24, 14),
      new THREE.MeshStandardMaterial({ color: 0x1a1f26 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = 0.28;
    ground.receiveShadow = true;
    this.#scene.add(ground);

    this.#productionLine = new ProductionLine();
    this.#scene.add(this.#productionLine.group);

    window.addEventListener('resize', () => this.#onResize());
    this.#renderer.setAnimationLoop(() => this.#animate());
  }

  setState(state) {
    this.#state = state;
  }

  #onResize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.#camera.aspect = w / h;
    this.#camera.updateProjectionMatrix();
    this.#renderer.setSize(w, h);
  }

  #animate() {
    const delta = this.#clock.getDelta();
    this.#controls.update();
    if (this.#state) {
      this.#productionLine.update(this.#state, delta);
    }
    this.#renderer.render(this.#scene, this.#camera);
  }
}
