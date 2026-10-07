// The 3D LightGearLab logo in the menu badge (model: tools/build_bulb.py → bulb.glb). The gear turns, the filament
// glows. Loaded the first time the menu opens; renders only while the menu is open. Needs the page's importmap for "three".

const MODEL = new URL('../bulb.glb', import.meta.url).href;
let state = null;

export async function startBulb(canvas, { stage, tilt: tiltEl, hover }) {
  if (state) { state.running = true; return state; }
  state = { running: true };
  try {
    const THREE = await import('three');
    const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
    const { DRACOLoader } = await import('three/addons/loaders/DRACOLoader.js');
    const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));   // (it's a big canvas)
    renderer.toneMapping = THREE.NoToneMapping;               // flat colours: the drawing should match the panel exactly
    const scene = new THREE.Scene();
    scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.9;
    const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(2, 3, 4); scene.add(key);
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
    camera.position.set(1.1, 0.4, 7.0); camera.lookAt(0, -0.25, 0.25);    // nearly front-on, like the logo   // three-quarter: the holder and base show

    // line drawing, like the box in Lines mode: parts filled with the panel colour, feature edges + silhouettes in ink
    const { LineSegments2 } = await import('three/addons/lines/LineSegments2.js');
    const { LineSegmentsGeometry } = await import('three/addons/lines/LineSegmentsGeometry.js');
    const { LineMaterial } = await import('three/addons/lines/LineMaterial.js');
    const INK = 0x1d1c1a, PAPER = 0xf6f3ee;
    const fill = new THREE.MeshBasicMaterial({ color: PAPER, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    const edgeMat = new LineMaterial({ color: INK, linewidth: 1.6 });          // px
    const outlineWidth = { value: 0.005 };
    const hullMat = new THREE.MeshBasicMaterial({ color: INK, side: THREE.BackSide });
    hullMat.onBeforeCompile = (sh) => {
      sh.uniforms.outlineWidth = outlineWidth;
      sh.vertexShader = 'uniform float outlineWidth;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\ntransformed += normalize(normal) * outlineWidth;');
    };
    // glass: only its rim, where the surface turns away from the eye (a curved outline you can see through)
    const glassMat = new THREE.ShaderMaterial({
      uniforms: { uInk: { value: new THREE.Color(INK) } },
      vertexShader: `varying vec3 vN; varying vec3 vV; varying float vZ;
        void main() { vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz);
          vZ = position.z; gl_Position = projectionMatrix * mv; }`,
      // only the dome in front of the gear (local z > 0); the neck behind it would draw a dark band
      fragmentShader: `uniform vec3 uInk; varying vec3 vN; varying vec3 vV; varying float vZ;
        void main() { if (vZ < 0.02) discard;
          float f = abs(dot(normalize(vN), normalize(vV))); float a = (1.0 - smoothstep(0.1, 0.3, f)) * 0.85;
          if (a < 0.01) discard; gl_FragColor = vec4(uInk, a); }`,
      transparent: true, depthWrite: false,
    });
    const M = {
      Bulb_Filament: new THREE.MeshBasicMaterial({ color: 0xffb627 }),   // the one thing in colour: the glowing wire
      Bulb_Wires: new THREE.MeshBasicMaterial({ color: INK }),          // thin wires read as lines on their own
      Bulb_Glass: glassMat,
    };
    const loader = new GLTFLoader().setDRACOLoader(new DRACOLoader().setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/'));
    const gltf = await loader.loadAsync(MODEL);
    // turn about the middle of the whole object (gear at the front, base at the back), not the gear's own centre
    const root = new THREE.Group(); root.add(gltf.scene); scene.add(root);
    root.position.set(0, -0.25, 0.25); gltf.scene.position.set(0, 0.25, -0.25);  // pivot mid-depth (bulb in front, holder behind)
    const meshes = [];
    gltf.scene.traverse((o) => { if (o.isMesh) meshes.push(o); });
    meshes.forEach((o) => {
      if (M[o.name]) { o.material = M[o.name]; return; }
      o.material = fill;
      const g = new LineSegmentsGeometry().fromEdgesGeometry(new THREE.EdgesGeometry(o.geometry, 28));
      o.add(new LineSegments2(g, edgeMat));
      // (no silhouette shell on the hollow holder: seen through the glass, its inside would fill the bulb with ink)
      if (o.name !== 'Bulb_Holder') o.add(new THREE.Mesh(o.geometry, hullMat));
    });
    const glass = gltf.scene.getObjectByName('Bulb_Glass'); if (glass) glass.renderOrder = 5;
    const gear = gltf.scene.getObjectByName('Bulb_Gear');
    // the glow: a warm halo around the filament and a small light inside the holder
    const fil = gltf.scene.getObjectByName('Bulb_Filament');
    const cv = document.createElement('canvas'); cv.width = cv.height = 256;
    const g = cv.getContext('2d'), gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    gr.addColorStop(0, 'rgba(255,214,110,0.55)'); gr.addColorStop(0.35, 'rgba(255,196,80,0.2)'); gr.addColorStop(1, 'rgba(255,190,70,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
    const haloMat = new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true });
    const halo = new THREE.Sprite(haloMat); halo.scale.set(1.5, 1.1, 1); halo.renderOrder = 6;
    if (fil) { fil.geometry.computeBoundingBox(); fil.geometry.boundingBox.getCenter(halo.position); }
    gltf.scene.add(halo);
    const lamp = new THREE.PointLight(0xffc35a, 1.6, 2.5, 1.5); lamp.position.copy(halo.position); gltf.scene.add(lamp);

    const resize = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
      edgeMat.resolution.set(w, h);
      outlineWidth.value = 2.2 / (h / 3.75);        // silhouettes ~2px wide (the view is 3.75 units tall)
    };
    new ResizeObserver(resize).observe(canvas);
    resize();
    // pointer: the logo leans towards the cursor; hovering spins the gear faster
    let speed = 0.5, target = 0.5;
    hover.addEventListener('pointerenter', () => { target = 2.2; });   // the call to action spins the gear up
    hover.addEventListener('pointerleave', () => { target = 0.5; });
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let last = performance.now(), t = 0;
    const tick = (now) => {
      requestAnimationFrame(tick);
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      if (!state.running) return;
      t += dt;
      speed += (target - speed) * Math.min(1, dt * 4);
      if (!reduce) gear.rotation.z -= speed * dt;
      root.rotation.set(0, -0.18, 0);                     // the bulb holds still; only its gear turns
      const flick = 0.85 + 0.15 * Math.sin(t * 2.3) + 0.04 * Math.sin(t * 17);
      haloMat.opacity = flick; lamp.intensity = 1.6 * flick;
      renderer.render(scene, camera);
    };
    requestAnimationFrame(tick);
    stage.classList.add('is-3d');
  } catch (err) {
    console.warn('3D logo unavailable, keeping the flat one', err);
  }
  return state;
}
export function stopBulb() { if (state) state.running = false; }
