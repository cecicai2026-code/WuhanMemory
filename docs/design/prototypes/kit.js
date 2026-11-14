/* 设计样片的共用部分（第二批）：纸张和文字贴图、悬停拾取、镜头、灯箱、打字机、笔记本。不是网站代码。 */
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { tex, materials, add, sh, contact, damp, photo, SERIF, MONO } from './common.js';

export { THREE, RoundedBoxGeometry };
export const TYPE = '"Courier Prime","LXGW WenKai TC","Kaiti SC","STKaiti",serif';
export const HAND = '"Caveat","Ma Shan Zheng","Kaiti SC",cursive';
export const INK = '#2a2420', SOFT = '#6b5e4c', RED = '#a8321f', GREEN = '#2f6b4f', BLUE = '#44607a';

/* ---------- 会重画的贴图：字体加载完后重画一遍，保证用上网页字体 ---------- */
const live = [];
export function ktex(w, h, draw) {
  const t = tex(w, h, draw);
  t.userData.redraw = () => { const c = t.image, g = c.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, c.width, c.height); draw(g, c.width, c.height); t.needsUpdate = true; };
  live.push(t); return t;
}
export async function settleFonts(sample = '') {
  const fams = ['"Courier Prime"', '"LXGW WenKai TC"', 'Caveat', '"Ma Shan Zheng"', '"Cormorant Garamond"', '"IBM Plex Mono"'];
  const wait = Promise.all(fams.map(f => document.fonts.load(`24px ${f}`, sample + 'Aa0').catch(() => {})));
  await Promise.race([wait, new Promise(r => setTimeout(r, 3000))]);
  live.forEach(t => t.userData.redraw());
}

/* ---------- 纸上的画法 ---------- */
export function paperBg(g, w, h, color = '#e9dfc6') {
  g.fillStyle = color; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(120,95,60,${Math.random() * 0.05})`; g.fillRect(Math.random() * w, Math.random() * h, 2 + Math.random() * 30, 1); }
  const e = g.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.35, w / 2, h / 2, Math.max(w, h) * 0.75);
  e.addColorStop(0, 'rgba(0,0,0,0)'); e.addColorStop(1, 'rgba(90,60,30,.18)');
  g.fillStyle = e; g.fillRect(0, 0, w, h);
}
export function ruled(g, w, h, top, gap, color = 'rgba(107,94,76,.3)') {
  g.fillStyle = color; for (let y = top; y < h - 20; y += gap) g.fillRect(40, y, w - 80, 2);
}
export function wrap(g, text, x, y, maxW, lh) {
  let line = '';
  for (const ch of text) {
    if (ch === '\n') { g.fillText(line, x, y); line = ''; y += lh; continue; }
    if (g.measureText(line + ch).width > maxW) { g.fillText(line, x, y); line = ch; y += lh; } else line += ch;
  }
  if (line) { g.fillText(line, x, y); y += lh; }
  return y;
}
/* 印章（实线框）和铅笔批注（虚线框） */
export function stamp(g, text, x, y, color, rot = -0.07, size = 30, dashed = false) {
  g.save(); g.translate(x, y); g.rotate(rot);
  g.font = `${size}px ${TYPE}`; const w = g.measureText(text).width + size * 0.9;
  g.strokeStyle = color; g.lineWidth = dashed ? 2.5 : 4; g.setLineDash(dashed ? [10, 7] : []);
  g.beginPath(); g.roundRect(-w / 2, -size * 0.8, w, size * 1.6, dashed ? 0 : 6); g.stroke();
  g.fillStyle = color; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, 0, 2);
  g.restore();
}

/* 一张纸。lie: 平放在桌上（字的上方朝远处）；否则竖着 */
export function sheet(w, h, draw, { lie = true, px = 220, t = 0.02 } = {}) {
  const k = Math.min(px, 2048 / Math.max(w, h));
  const T = ktex(Math.round(w * k), Math.round(h * k), draw), M = materials();
  const face = new THREE.MeshStandardMaterial({ map: T, roughness: 0.85 });
  const mesh = sh(new THREE.Mesh(new THREE.BoxGeometry(w, h, t), [M.paper, M.paper, M.paper, M.paper, face, M.paper]));
  if (lie) mesh.rotation.x = -Math.PI / 2;
  const g = new THREE.Group(); g.add(mesh);
  g.userData = { face, tex: T, mesh, w, h };
  return g;
}

/* ---------- 镜头：窄屏时自动拉远，平时轻微跟随鼠标 ---------- */
export function rig(stage, { pos, look, aspect = 1.7, sway = [0.55, 0.3] }) {
  const P = new THREE.Vector3(...pos), L = new THREE.Vector3(...look), tp = P.clone(), tl = L.clone(), ln = L.clone();
  const place = (p, l) => l.clone().add(p.clone().sub(l).multiplyScalar(Math.max(1, aspect / (innerWidth / innerHeight))));
  stage.camera.position.copy(place(P, L)); stage.camera.lookAt(L);
  return {
    to(p, l) { tp.set(...p); tl.set(...l); }, home() { tp.copy(P); tl.copy(L); },
    update(dt, mouse, s = 3) {
      const goal = place(tp, tl), c = stage.camera.position;
      goal.x += mouse.x * sway[0]; goal.y -= mouse.y * sway[1];
      c.set(damp(c.x, goal.x, s, dt), damp(c.y, goal.y, s, dt), damp(c.z, goal.z, s, dt));
      ln.set(damp(ln.x, tl.x, s, dt), damp(ln.y, tl.y, s, dt), damp(ln.z, tl.z, s, dt));
      stage.camera.lookAt(ln);
    },
  };
}

/* ---------- 悬停和点击：登记物件，每帧得到 hv（0 到 1 的悬停程度） ---------- */
export function interact(stage) {
  const items = [], ray = new THREE.Raycaster(), ndc = new THREE.Vector2(9, 9), mouse = new THREE.Vector2();
  let hovered = null;
  const pick = () => {
    ray.setFromCamera(ndc, stage.camera);
    const hit = ray.intersectObjects(items.flatMap(i => i.meshes), false)[0];
    hovered = hit ? items.find(i => i.meshes.includes(hit.object)) : null;
  };
  addEventListener('pointermove', e => { mouse.set((e.clientX / innerWidth) * 2 - 1, (e.clientY / innerHeight) * 2 - 1); ndc.set(mouse.x, -mouse.y); });
  stage.renderer.domElement.addEventListener('click', e => {
    ndc.set((e.clientX / innerWidth) * 2 - 1, -((e.clientY / innerHeight) * 2 - 1)); pick();
    if (hovered?.onClick) hovered.onClick(hovered);
  });
  return {
    mouse, items, get hovered() { return hovered; },
    add(obj, opts = {}) {
      const meshes = []; obj.traverse(o => { if (o.isMesh && !o.material.transparent) meshes.push(o); });
      const it = { obj, meshes, hv: 0, ...opts }; items.push(it); return it;
    },
    update(dt) {
      pick(); stage.renderer.domElement.style.cursor = hovered ? 'pointer' : 'default';
      for (const it of items) it.hv = damp(it.hv, it === hovered ? 1 : 0, 8, dt);
    },
  };
}
export function project(v, camera) { const p = v.clone().project(camera); return [(p.x * 0.5 + 0.5) * innerWidth, (-p.y * 0.5 + 0.5) * innerHeight]; }
export function go(url) { document.body.classList.add('leaving'); setTimeout(() => { location.href = url; }, 520); }
export function run(step) {
  const clock = new THREE.Clock();
  const frame = () => { step(Math.min(clock.getDelta(), 0.05)); requestAnimationFrame(frame); };
  window.__advance = s => { for (let i = 0; i < s * 60; i++) step(1 / 60); };   /* 调试用：页面在后台时手动推进 */
  frame(); requestAnimationFrame(() => document.body.classList.add('ready'));
  addEventListener('pageshow', e => { if (e.persisted) document.body.classList.remove('leaving'); });
}

/* ---------- 地图示意：正式版是高德地图。坐标是 0 到 1 的示意位置，不是真实经纬度 ---------- */
export const DAYCOL = ['#e2c27e', '#7fb7b0'];
export const STOPS = [
  { name: '黄鹤楼', x: 0.565, y: 0.64, day: 0, n: 1 }, { name: '户部巷', x: 0.525, y: 0.73, day: 0, n: 2 }, { name: '昙华林', x: 0.64, y: 0.575, day: 0, n: 3 },
  { name: '湖北省博物馆', x: 0.745, y: 0.49, day: 1, n: 1 }, { name: '东湖', x: 0.87, y: 0.43, day: 1, n: 2 }, { name: '汉口江滩', x: 0.57, y: 0.4, day: 1, n: 3 },
];
export function drawMap(g, w, h, day = -1) {
  g.fillStyle = '#2b2018'; g.fillRect(0, 0, w, h);
  g.strokeStyle = 'rgba(120,90,60,.35)'; g.lineWidth = w / 600;
  let s = 11; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 46; i++) { const a = r() * Math.PI, x = r() * w, y = r() * h, l = w * (0.2 + r() * 0.6); g.beginPath(); g.moveTo(x - Math.cos(a) * l, y - Math.sin(a) * l); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke(); }
  g.strokeStyle = 'rgba(170,130,85,.5)'; g.lineWidth = w / 300;
  for (const [a, b, c, d] of [[0, 0.22, 1, 0.78], [0.1, 0, 0.5, 1], [0, 0.84, 1, 0.58], [0.7, 0, 0.78, 1], [0.3, 0.1, 1, 0.34]]) { g.beginPath(); g.moveTo(a * w, b * h); g.lineTo(c * w, d * h); g.stroke(); }
  g.lineCap = 'round'; g.strokeStyle = '#3f5c66';
  g.lineWidth = w * 0.055; g.beginPath(); g.moveTo(0.15 * w, 1.05 * h); g.bezierCurveTo(0.34 * w, 0.84 * h, 0.42 * w, 0.68 * h, 0.52 * w, 0.57 * h); g.bezierCurveTo(0.64 * w, 0.44 * h, 0.82 * w, 0.26 * h, 1.03 * w, 0.14 * h); g.stroke();
  g.lineWidth = w * 0.02; g.beginPath(); g.moveTo(-0.02 * w, 0.47 * h); g.bezierCurveTo(0.15 * w, 0.5 * h, 0.3 * w, 0.55 * h, 0.47 * w, 0.61 * h); g.stroke();
  g.fillStyle = '#36515a'; g.beginPath(); g.ellipse(0.885 * w, 0.4 * h, 0.095 * w, 0.085 * h, -0.4, 0, 7); g.fill();
  g.strokeStyle = '#8a6830'; g.lineWidth = w / 130; g.beginPath(); g.moveTo(0.43 * w, 0.71 * h); g.lineTo(0.56 * w, 0.645 * h); g.stroke();
  g.fillStyle = 'rgba(233,223,198,.4)'; g.textAlign = 'center'; g.font = `600 ${w / 26}px ${SERIF}`;
  g.fillText('汉 口', 0.33 * w, 0.3 * h); g.fillText('汉 阳', 0.26 * w, 0.74 * h); g.fillText('武 昌', 0.72 * w, 0.8 * h);
  g.font = `${w / 60}px ${MONO}`; g.fillStyle = 'rgba(160,200,210,.6)'; g.fillText('长 江', 0.8 * w, 0.215 * h); g.fillText('东 湖', 0.89 * w, 0.405 * h);
  for (const d of [0, 1]) {
    const pts = STOPS.filter(p => p.day === d), on = day < 0 || day === d;
    g.globalAlpha = on ? 1 : 0.28; g.strokeStyle = DAYCOL[d]; g.lineWidth = w / 190; g.lineJoin = 'round'; g.setLineDash(d ? [w / 60, w / 90] : []);
    g.beginPath(); pts.forEach((p, i) => g[i ? 'lineTo' : 'moveTo'](p.x * w, p.y * h)); g.stroke(); g.setLineDash([]);
    for (const p of pts) { g.fillStyle = '#2b2018'; g.beginPath(); g.arc(p.x * w, p.y * h, w / 95, 0, 7); g.fill(); g.lineWidth = w / 300; g.stroke(); }
    g.globalAlpha = 1;
  }
  g.fillStyle = 'rgba(233,223,198,.55)'; g.textAlign = 'left'; g.font = `${w / 64}px ${MONO}`; g.fillText('地图示意 · 正式版为高德地图', w * 0.025, h * 0.955);
}

/* ---------- 灯箱：黄铜边框，里面是自己发光的地图 ---------- */
export function makeLightbox(w, d, draw) {
  const M = materials(), g = new THREE.Group(), bar = 0.3;
  contact(g, w + 3.4, d + 3.4);
  add(g, new RoundedBoxGeometry(w + 0.5, 0.46, d + 0.5, 4, 0.08), M.brassDark, 0, 0.23, 0);
  for (const s of [-1, 1]) {
    add(g, new RoundedBoxGeometry(w + bar * 2, 0.18, bar, 3, 0.06), M.brass, 0, 0.53, s * (d / 2 + bar / 2 - 0.02));
    add(g, new RoundedBoxGeometry(bar, 0.18, d, 3, 0.06), M.brass, s * (w / 2 + bar / 2 - 0.02), 0.53, 0);
    for (const q of [-1, 1]) add(g, new THREE.CylinderGeometry(0.07, 0.07, 0.05, 16), M.brassDark, s * (w / 2 + bar / 2 - 0.02), 0.63, q * (d / 2 + bar / 2 - 0.02));
  }
  const T = ktex(1536, Math.round(1536 * d / w), draw);
  const sm = new THREE.MeshStandardMaterial({ color: 0x000000, emissiveMap: T, emissive: 0xffffff, emissiveIntensity: 1.0, roughness: 0.9 });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(w, d), sm); screen.rotation.x = -Math.PI / 2; screen.position.y = 0.47; g.add(screen);
  const glow = new THREE.PointLight(0xffd9a8, 0.5, 9, 1.5); glow.position.y = 1.2; g.add(glow);
  g.userData = { screen, sm, tex: T, top: 0.47, w, d };
  return g;
}
export function makePin(color) {
  const M = materials(), g = new THREE.Group();
  add(g, new THREE.CylinderGeometry(0.022, 0.012, 0.5, 8), M.steel, 0, 0.25, 0);
  const head = add(g, new THREE.SphereGeometry(0.14, 24, 16), new THREE.MeshPhysicalMaterial({ color, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.1 }), 0, 0.56, 0);
  g.userData.head = head; return g;
}

/* ---------- 打字机：墨绿机身、黑色压纸辊、黄铜旋钮，上面卷着一张纸 ---------- */
export function makeTypewriter(label, draw) {
  const M = materials(), g = new THREE.Group();
  contact(g, 7, 5.4);
  add(g, new RoundedBoxGeometry(4.8, 0.9, 2.9, 6, 0.24), M.green, 0, 0.45, 0.55);
  add(g, new RoundedBoxGeometry(5.0, 0.7, 1.3, 5, 0.2), M.green, 0, 1.0, -0.6);
  const roll = add(g, new THREE.CylinderGeometry(0.36, 0.36, 4.5, 40), M.black, 0, 1.5, -0.6); roll.rotation.z = Math.PI / 2;
  for (const s of [-1, 1]) { const k = add(g, new THREE.CylinderGeometry(0.44, 0.44, 0.24, 40), M.brass, s * 2.42, 1.5, -0.6); k.rotation.z = Math.PI / 2; }
  const bail = add(g, new THREE.CylinderGeometry(0.035, 0.035, 4.1, 12), M.brass, 0, 1.93, -0.42); bail.rotation.z = Math.PI / 2;
  for (let r = 0; r < 3; r++) for (let c = 0; c < 10; c++) {
    const x = -1.8 + c * 0.4 + (r % 2) * 0.2, z = 0.75 + r * 0.42, y = 0.98 - r * 0.03;
    add(g, new THREE.CylinderGeometry(0.15, 0.15, 0.05, 20), M.brassDark, x, y, z);
    add(g, new THREE.CylinderGeometry(0.125, 0.125, 0.09, 20), M.black, x, y + 0.05, z);
  }
  add(g, new RoundedBoxGeometry(2.6, 0.1, 0.3, 3, 0.04), M.brassDark, 0, 0.92, 1.92);   /* 空格键 */
  const plateT = ktex(512, 128, (c, w, h) => {
    const bg = c.createLinearGradient(0, 0, 0, h); bg.addColorStop(0, '#e2c27e'); bg.addColorStop(0.5, '#c9a45c'); bg.addColorStop(1, '#a8833f');
    c.fillStyle = bg; c.fillRect(0, 0, w, h); c.strokeStyle = '#6e5326'; c.lineWidth = 4; c.strokeRect(8, 8, w - 16, h - 16);
    c.fillStyle = INK; c.textAlign = 'center'; c.textBaseline = 'middle'; c.font = `600 62px ${SERIF}`; c.fillText(label.split('').join(' '), w / 2, h / 2 + 3);
  });
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 0.375), new THREE.MeshStandardMaterial({ map: plateT, roughness: 0.32, metalness: 0.85, envMapIntensity: 1.6 }));
  plate.position.set(0, 0.42, 2.005); g.add(plate);
  const paper = sheet(3.3, 4.7, draw, { lie: false });
  paper.position.set(0, 1.5 + 2.2, -1.12); paper.rotation.x = -0.22; g.add(paper);
  g.userData = { paper, roll };
  return g;
}

/* ---------- 笔记本：墨绿封皮，两页纸，中间一排黄铜环 ---------- */
export function makeNotebook(drawL, drawR) {
  const M = materials(), g = new THREE.Group();
  contact(g, 13.4, 9.6);
  add(g, new RoundedBoxGeometry(10.5, 0.16, 7.0, 4, 0.06), M.green, 0, 0.08, 0);
  const pages = [-1, 1].map((s, i) => {
    add(g, new THREE.BoxGeometry(4.9, 0.16, 6.6), M.paper, s * 2.52, 0.24, 0);
    const p = sheet(4.9, 6.6, i ? drawR : drawL); p.position.set(s * 2.52, 0.335, 0); g.add(p); return p;
  });
  for (let k = 0; k < 11; k++) add(g, new THREE.TorusGeometry(0.2, 0.028, 10, 28), M.brass, 0, 0.3, -3 + k * 0.6);
  g.userData.pages = pages; return g;
}
/* 印样：一条黑色底片，上面几格照片（罩着暗房红，悬停时显出原色） */
export function makeStrip(idx, w = 4.2) {
  const M = materials(), g = new THREE.Group(), n = idx.length, fw = (w - 0.2) / n - 0.06, h = fw * 0.8 + 0.22;
  g.add(sh(new THREE.Mesh(new THREE.BoxGeometry(w, 0.03, h), M.black)));
  g.userData.frames = idx.map((i, k) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(fw, h - 0.22), new THREE.MeshStandardMaterial({ map: photo(i), emissiveMap: photo(i), emissive: 0xffffff, emissiveIntensity: 0.15, roughness: 0.5, color: 0xff7755 }));
    m.rotation.x = -Math.PI / 2; m.position.set(-w / 2 + 0.13 + fw / 2 + k * (fw + 0.06), 0.017, 0); g.add(m); return m;
  });
  g.userData.h = h; return g;
}
export function litStrip(strip, L) { for (const f of strip.userData.frames) { f.material.color.setRGB(1, 0.47 + L * 0.53, 0.33 + L * 0.67); f.material.emissiveIntensity = 0.15 + L * 0.45; } }

/* ---------- 钢笔和票根 ---------- */
export function makePen() {
  const M = materials(), o = new THREE.Group(), g = new THREE.Group();
  add(g, new THREE.CylinderGeometry(0.11, 0.1, 2.5, 24), M.green);
  add(g, new THREE.CylinderGeometry(0.125, 0.125, 0.95, 24), M.brassDark, 0, 0.95, 0);
  add(g, new THREE.CylinderGeometry(0.13, 0.13, 0.06, 24), M.brass, 0, 0.47, 0);
  const nib = add(g, new THREE.ConeGeometry(0.1, 0.5, 24), M.brass, 0, -1.5, 0); nib.rotation.x = Math.PI;
  g.rotation.z = Math.PI / 2; g.position.y = 0.13; o.add(g); contact(o, 3.6, 1.0);
  return o;
}
export function makeTicket(title, sub, w = 2.3, h = 1.15) {
  return sheet(w, h, (g, W, H) => {
    g.fillStyle = '#f4eedd'; g.fillRect(0, 0, W, H);
    g.fillStyle = '#143026'; g.fillRect(14, 14, W - 28, H - 28);
    g.fillStyle = '#c9a45c'; g.font = `${H * 0.11}px ${MONO}`; g.textAlign = 'left'; g.fillText(sub, 36, H * 0.27);
    g.fillStyle = '#e9dfc6'; g.font = `600 ${H * 0.3}px ${SERIF}`; g.fillText(title, 36, H * 0.63);
    for (let x = 36; x < W - 36; x += 9) g.fillRect(x, H * 0.76, 3, H * 0.1);
  });
}
