/* 设计样片的共用部分：景点示例清单、贴图、材质、舞台搭建。不是网站代码。 */
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

/* 示例清单：只用来演示效果，正式的景点由 Cecilia 确定 */
export const SPOTS = ['黄鹤楼', '户部巷', '昙华林', '武昌起义纪念馆', '湖北省博物馆', '东湖', '武汉大学', '楚河汉街', '武汉长江大桥',
  '晴川阁', '古琴台', '归元寺', '汉口江滩', '江汉关', '江汉路', '黎黄陂路', '古德寺', '吉庆街'];
export const TOPICS = ['景点概览', '游玩建议', '景点图册', '周边美食'];
export const pad = n => String(n).padStart(2, '0');
export const damp = (cur, to, speed, dt) => cur + (to - cur) * (1 - Math.exp(-speed * dt));
export const SERIF = '"Songti SC","Noto Serif SC","STSong",serif';
export const MONO = '"IBM Plex Mono",Menlo,monospace';

let seed = 7;
export const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
export const reseed = s => { seed = s; };

let maxAniso = 8;
export function tex(w, h, draw, srgb = true) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = maxAniso;
  return t;
}

/* 画面颗粒：页面里放一个 <canvas class="grain" id="grain" width="256" height="256"> */
export function grain() {
  const c = document.getElementById('grain'); if (!c) return;
  const g = c.getContext('2d'), d = g.createImageData(256, 256);
  for (let i = 0; i < d.data.length; i += 4) { const v = Math.random() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
  g.putImageData(d, 0, 0); c.style.width = '200%'; c.style.height = '200%'; c.style.imageRendering = 'pixelated';
}

/* 舞台：渲染器、场景、环境反射、主灯和暗房红的补光 */
export function createStage({ fov = 30, lampPos = [-3, 10, 10], lampTarget = [0.4, 1.4, 0], lampPower = 7.4, lampAngle = 0.66 } = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  document.body.prepend(renderer.domElement);
  maxAniso = renderer.capabilities.getMaxAnisotropy();

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x070504);
  scene.fog = new THREE.Fog(0x070504, 26, 50);
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.1;

  const camera = new THREE.PerspectiveCamera(fov, innerWidth / innerHeight, 0.1, 120);
  scene.add(new THREE.HemisphereLight(0xffb48a, 0x1a0806, 0.1));
  const lamp = new THREE.SpotLight(0xffd6a0, lampPower, 0, lampAngle, 0.9, 0);
  lamp.position.set(...lampPos); lamp.target.position.set(...lampTarget);
  lamp.castShadow = true; lamp.shadow.mapSize.set(4096, 4096);
  lamp.shadow.bias = -0.00025; lamp.shadow.normalBias = 0.02; lamp.shadow.radius = 8;
  scene.add(lamp, lamp.target);
  const safelight = new THREE.PointLight(0xff3b1e, 1.0, 0, 0); safelight.position.set(11, 4.5, 4); scene.add(safelight);

  addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
  return { renderer, scene, camera, lamp, safelight };
}

/* ---------- 木桌 ---------- */
function grainLines(g, w, h, dark, light, n) {
  for (let i = 0; i < n; i++) {
    const y = rnd() * h, len = 200 + rnd() * 1100, x = rnd() * w - 300;
    g.strokeStyle = rnd() > 0.45 ? dark(rnd()) : light(rnd());
    g.lineWidth = 0.5 + rnd() * 2.4;
    g.beginPath(); g.moveTo(x, y);
    g.bezierCurveTo(x + len * 0.3, y + (rnd() - 0.5) * 10, x + len * 0.6, y + (rnd() - 0.5) * 10, x + len, y + (rnd() - 0.5) * 8);
    g.stroke();
  }
}
export function makeTable(scene) {
  reseed(7);
  const woodTex = tex(2048, 2048, (g, w, h) => {
    g.fillStyle = '#6a2015'; g.fillRect(0, 0, w, h);
    for (let p = 0; p < 6; p++) { g.fillStyle = `rgba(${p % 2 ? 40 : 120},${p % 2 ? 8 : 40},${p % 2 ? 4 : 24},.10)`; g.fillRect(0, (h / 6) * p, w, h / 6); }
    grainLines(g, w, h, a => `rgba(20,4,2,${0.05 + a * 0.16})`, a => `rgba(214,96,60,${0.02 + a * 0.07})`, 5200);
    for (let k = 0; k < 14; k++) {
      const x = rnd() * w, y = rnd() * h, r = 14 + rnd() * 30;
      for (let q = 0; q < 7; q++) { g.strokeStyle = `rgba(18,4,2,${0.10 + q * 0.02})`; g.lineWidth = 1.2; g.beginPath(); g.ellipse(x, y, r * (1 + q * 0.5), r * 0.32 * (1 + q * 0.45), 0, 0, 7); g.stroke(); }
    }
    for (let p = 1; p < 6; p++) { g.fillStyle = 'rgba(10,2,1,.7)'; g.fillRect(0, (h / 6) * p - 1, w, 3); g.fillStyle = 'rgba(255,150,110,.08)'; g.fillRect(0, (h / 6) * p + 2, w, 1); }
  });
  reseed(7);
  const woodBump = tex(2048, 2048, (g, w, h) => {
    g.fillStyle = '#808080'; g.fillRect(0, 0, w, h);
    grainLines(g, w, h, a => `rgba(0,0,0,${0.10 + a * 0.25})`, a => `rgba(255,255,255,${0.05 + a * 0.12})`, 5200);
    for (let p = 1; p < 6; p++) { g.fillStyle = '#000'; g.fillRect(0, (h / 6) * p - 1, w, 4); }
  }, false);
  for (const t of [woodTex, woodBump]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2.4, 2.4); }
  const table = new THREE.Mesh(new THREE.PlaneGeometry(70, 44),
    new THREE.MeshPhysicalMaterial({ map: woodTex, bumpMap: woodBump, bumpScale: 0.9, roughness: 0.42, clearcoat: 0.35, clearcoatRoughness: 0.35 }));
  table.rotation.x = -Math.PI / 2; table.receiveShadow = true; scene.add(table);
  return table;
}

/* ---------- 示意照片：渐变天空 + 剪影 + 胶片颗粒。正式版换成真实照片 ---------- */
const PAL = [
  ['#1c2a4a', '#e8a35a', '#f6d79a'], ['#2a1830', '#d9603c', '#f2b05e'], ['#16323c', '#7fb7b0', '#f1e2b8'],
  ['#0b1024', '#31406e', '#c98b5a'], ['#243a2c', '#9cc0a0', '#f3e7c4'], ['#3a2418', '#c98a4a', '#f4dfae'],
  ['#2b2140', '#b0688e', '#f0c79a'], ['#10242e', '#4f7f8c', '#e6d6a8'],
];
const photoCache = [];
export function photo(i) {
  if (photoCache[i]) return photoCache[i];
  return (photoCache[i] = tex(640, 640, (g, w, h) => {
    const [a, b, c] = PAL[i % PAL.length];
    const sky = g.createLinearGradient(0, 0, 0, h * 0.72);
    sky.addColorStop(0, a); sky.addColorStop(0.7, b); sky.addColorStop(1, c);
    g.fillStyle = sky; g.fillRect(0, 0, w, h);
    reseed(100 + i * 31);
    for (let k = 0; k < 5; k++) {
      const cx = rnd() * w, cy = h * (0.12 + rnd() * 0.3), cw = 90 + rnd() * 160;
      const cg = g.createRadialGradient(cx, 0, 0, cx, 0, cw); cg.addColorStop(0, 'rgba(255,235,205,.28)'); cg.addColorStop(1, 'rgba(255,235,205,0)');
      g.fillStyle = cg; g.save(); g.translate(0, cy); g.scale(1, 0.35); g.fillRect(cx - cw, -cw, cw * 2, cw * 2); g.restore();
    }
    const sx = w * (0.22 + rnd() * 0.5), sg = g.createRadialGradient(sx, h * 0.55, 0, sx, h * 0.55, 120);
    sg.addColorStop(0, 'rgba(255,244,214,.95)'); sg.addColorStop(0.16, 'rgba(255,230,180,.6)'); sg.addColorStop(1, 'rgba(255,220,160,0)');
    g.fillStyle = sg; g.fillRect(0, 0, w, h);
    g.fillStyle = 'rgba(14,11,16,.94)';
    const kind = i % 4;
    if (kind === 0) {
      g.beginPath(); g.moveTo(0, h * 0.74);
      for (let x = 0; x <= w; x += 32) g.lineTo(x, h * (0.64 + rnd() * 0.09));
      g.lineTo(w, h); g.lineTo(0, h); g.fill();
      const bx = w * (0.4 + rnd() * 0.25);
      for (let t = 0; t < 5; t++) { const tw = 170 - t * 28, ty = h * 0.68 - t * 40; g.beginPath(); g.moveTo(bx - tw / 2 - 14, ty + 12); g.quadraticCurveTo(bx, ty - 8, bx + tw / 2 + 14, ty + 12); g.lineTo(bx + tw / 2, ty + 14); g.lineTo(bx - tw / 2, ty + 14); g.fill(); g.fillRect(bx - tw / 2 + 16, ty + 14, tw - 32, 26); }
      g.fillRect(bx - 2, h * 0.68 - 200, 4, 30);
    } else if (kind === 1) {
      for (let x = 0; x < w; x += 20 + rnd() * 28) { const bh = h * (0.1 + rnd() * 0.34); g.fillRect(x, h * 0.74 - bh, 16 + rnd() * 24, bh); }
      g.fillRect(0, h * 0.74, w, h);
      for (let k = 0; k < 160; k++) { g.fillStyle = `rgba(255,${190 + rnd() * 50},${110 + rnd() * 60},${0.5 + rnd() * 0.5})`; g.fillRect(rnd() * w, h * (0.44 + rnd() * 0.29), 2, 2 + rnd() * 2); }
    } else if (kind === 2) {
      g.fillRect(0, h * 0.72, w, h); g.fillRect(0, h * 0.6, w, 9); g.fillRect(0, h * 0.635, w, 4);
      for (let x = 30; x < w; x += 150) { g.fillRect(x, h * 0.44, 14, h * 0.28); g.fillRect(x - 6, h * 0.44, 26, 8); }
      g.strokeStyle = 'rgba(14,11,16,.94)'; g.lineWidth = 2;
      for (let x = 30; x < w; x += 15) { g.beginPath(); g.moveTo(x, h * 0.6); g.lineTo(x + 7, h * 0.635); g.lineTo(x + 15, h * 0.6); g.stroke(); }
    } else {
      g.beginPath(); g.moveTo(0, h * 0.3); g.lineTo(w * 0.36, h * 0.58); g.lineTo(w * 0.36, h); g.lineTo(0, h); g.fill();
      g.beginPath(); g.moveTo(w, h * 0.24); g.lineTo(w * 0.62, h * 0.58); g.lineTo(w * 0.62, h); g.lineTo(w, h); g.fill();
      g.fillRect(0, h * 0.82, w, h);
      for (let k = 0; k < 26; k++) { g.fillStyle = `rgba(255,${180 + rnd() * 50},110,${0.5 + rnd() * 0.4})`; const left = rnd() > 0.5; g.fillRect(left ? rnd() * w * 0.32 : w * (0.66 + rnd() * 0.32), h * (0.42 + rnd() * 0.36), 8, 12); }
    }
    const water = g.createLinearGradient(0, h * 0.74, 0, h); water.addColorStop(0, 'rgba(255,200,140,.2)'); water.addColorStop(1, 'rgba(0,0,0,.55)');
    g.fillStyle = water; g.fillRect(0, h * 0.74, w, h * 0.26);
    const vg = g.createRadialGradient(w / 2, h / 2, w * 0.3, w / 2, h / 2, w * 0.75); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.45)');
    g.fillStyle = vg; g.fillRect(0, 0, w, h);
    const d = g.getImageData(0, 0, w, h);
    for (let p = 0; p < d.data.length; p += 4) { const n = (Math.random() - 0.5) * 26; d.data[p] += n; d.data[p + 1] += n; d.data[p + 2] += n; }
    g.putImageData(d, 0, 0);
    g.fillStyle = 'rgba(233,223,198,.5)'; g.font = '18px monospace'; g.fillText('示意图', 16, h - 16);
  }));
}

/* ---------- 材质 ---------- */
let _M;
export function materials() {
  if (_M) return _M;
  reseed(3);
  const brushed = tex(512, 512, (g, w, h) => {
    g.fillStyle = '#6a6a6a'; g.fillRect(0, 0, w, h);
    for (let i = 0; i < 3000; i++) { const v = rnd() > .5 ? 255 : 0; g.fillStyle = `rgba(${v},${v},${v},.06)`; g.fillRect(0, rnd() * h, w, 1); }
  }, false);
  brushed.wrapS = brushed.wrapT = THREE.RepeatWrapping;
  return (_M = {
    green: new THREE.MeshPhysicalMaterial({ color: 0x143026, roughness: 0.36, metalness: 0.1, clearcoat: 0.7, clearcoatRoughness: 0.28 }),
    brass: new THREE.MeshStandardMaterial({ color: 0xd0a85c, roughness: 0.26, metalness: 1, roughnessMap: brushed, envMapIntensity: 2.2 }),
    brassDark: new THREE.MeshStandardMaterial({ color: 0x8a6830, roughness: 0.36, metalness: 1, roughnessMap: brushed, envMapIntensity: 1.8 }),
    steel: new THREE.MeshStandardMaterial({ color: 0xb9b4aa, roughness: 0.34, metalness: 1, roughnessMap: brushed, envMapIntensity: 2.4 }),
    black: new THREE.MeshStandardMaterial({ color: 0x100d0b, roughness: 0.75 }),
    felt: new THREE.MeshStandardMaterial({ color: 0x050404, roughness: 1 }),
    paper: new THREE.MeshStandardMaterial({ color: 0xe9dfc6, roughness: 0.85 }),
    wood: new THREE.MeshStandardMaterial({ color: 0xb8794a, roughness: 0.7 }),
    bamboo: new THREE.MeshStandardMaterial({ color: 0xc9a06a, roughness: 0.55 }),
  });
}
export const sh = m => { m.castShadow = true; m.receiveShadow = true; return m; };
export const add = (parent, geo, mat, x = 0, y = 0, z = 0) => { const m = sh(new THREE.Mesh(geo, mat)); m.position.set(x, y, z); parent.add(m); return m; };

/* 物件底下的接触阴影 */
let aoTex;
export function contact(parent, w, d) {
  aoTex ??= tex(256, 256, (g, s) => { const r = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2); r.addColorStop(0, 'rgba(0,0,0,.85)'); r.addColorStop(0.55, 'rgba(0,0,0,.4)'); r.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = r; g.fillRect(0, 0, s, s); });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshBasicMaterial({ map: aoTex, transparent: true, depthWrite: false }));
  m.rotation.x = -Math.PI / 2; m.position.y = 0.012; parent.add(m); return m;
}

/* ---------- 胶卷罐 ---------- */
export function makeCanister(chars, sub) {
  const M = materials(), can = new THREE.Group();
  contact(can, 4.6, 4.6);
  const labelTex = tex(2048, 835, (g, w, h) => {
    g.fillStyle = '#143026'; g.fillRect(0, 0, w, h);
    const x0 = w * 0.25;
    g.fillStyle = '#e9dfc6'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.font = `600 250px ${SERIF}`;
    g.fillText(chars[0], x0 - 40, h * 0.33); g.fillText(chars[1], x0 - 40, h * 0.67);
    g.save(); g.translate(x0 + 170, h * 0.5); g.rotate(Math.PI / 2);
    g.font = `34px ${MONO}`; g.fillStyle = '#c9a45c'; g.fillText(sub, 0, 0); g.restore();
    g.strokeStyle = '#c9a45c'; g.lineWidth = 3; g.strokeRect(x0 - 250, 40, 520, h - 80);
  });
  const body = add(can, new THREE.CylinderGeometry(1.25, 1.25, 3.1, 96),
    new THREE.MeshPhysicalMaterial({ map: labelTex, roughness: 0.36, metalness: 0.1, clearcoat: 0.7, clearcoatRoughness: 0.28 }), 0, 1.9, 0);
  body.rotation.y = -Math.PI / 2;
  add(can, new THREE.CylinderGeometry(1.36, 1.38, 0.3, 96), M.brassDark, 0, 0.15, 0);
  add(can, new THREE.TorusGeometry(1.3, 0.05, 16, 96), M.brass, 0, 0.36, 0).rotation.x = Math.PI / 2;
  add(can, new THREE.TorusGeometry(1.3, 0.05, 16, 96), M.brass, 0, 3.44, 0).rotation.x = Math.PI / 2;
  add(can, new THREE.CylinderGeometry(1.38, 1.36, 0.32, 96), M.brassDark, 0, 3.62, 0);
  add(can, new THREE.CylinderGeometry(1.2, 1.3, 0.06, 96), M.brass, 0, 3.81, 0);
  can.userData.spool = add(can, new THREE.CylinderGeometry(0.3, 0.3, 0.7, 24), M.black, 0, 4.15, 0);
  add(can, new THREE.CylinderGeometry(0.34, 0.34, 0.1, 12), M.brass, 0, 4.55, 0);
  return can;
}
