/**
 * 首页的桌面（/，设计规范第 9.4 节）。从样片 docs/design/prototypes/darkroom-desk.html 和 kit.js 改写。
 *
 * - 开场：全黑，一盏灯亮起，照出整张桌子（G6，只在这次访问的第一个页面，点一下可以跳过）。
 * - 桌上四件物件，各通往一个页面：胶卷罐 → 地点档案，灯箱 → 地图工作台，两台打字机 → 模型对比，笔记本 → 我的行程。
 * - 镜头有五个停靠点：全景和四件物件。滚轮、方向键、网页上的按钮一站一站走。
 *
 * 样片里的示例行程、画出来的地图（江、路、区名）、印样照片都不带进来（设计规范第 15 节第 7 条）：
 * 灯箱里只按景点的真实坐标摆图钉，标"示意：景点的相对位置"；打字机的纸上只写"千问""豆包"；笔记本合着，封面写"我的行程"。
 */
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { COLORS, MONO, SERIF, TYPE, add, contact, damp, disposeTree, ensureFonts, makeCanister, makeTable, materials, sh, tex } from "../common";
import type { DeskData } from "../data";
import { addLights, applyShadowQuality } from "../engine";
import type { Act, ActEnv } from "../engine";
import type { StageCommand, StageRequest } from "../types";

/* ---------- 纸 ---------- */
function paperBg(g: CanvasRenderingContext2D, w: number, h: number, color: string = COLORS.paper) {
  g.fillStyle = color;
  g.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) {
    g.fillStyle = `rgba(120,95,60,${Math.random() * 0.05})`;
    g.fillRect(Math.random() * w, Math.random() * h, 2 + Math.random() * 30, 1);
  }
  const e = g.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.35, w / 2, h / 2, Math.max(w, h) * 0.75);
  e.addColorStop(0, "rgba(0,0,0,0)");
  e.addColorStop(1, "rgba(90,60,30,.18)");
  g.fillStyle = e;
  g.fillRect(0, 0, w, h);
}

/** 一张纸（平放或竖着），owned 收集贴图，最后一起释放 */
function sheet(w: number, h: number, draw: (g: CanvasRenderingContext2D, W: number, H: number) => void, owned: THREE.Texture[], lie = true) {
  const k = Math.min(220, 2048 / Math.max(w, h));
  const T = tex(Math.round(w * k), Math.round(h * k), draw);
  owned.push(T);
  const M = materials();
  const face = new THREE.MeshStandardMaterial({ map: T, roughness: 0.85 });
  const mesh = sh(new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.02), [M.paper, M.paper, M.paper, M.paper, face, M.paper]));
  if (lie) mesh.rotation.x = -Math.PI / 2;
  const g = new THREE.Group();
  g.add(mesh);
  return g;
}

/* ---------- 灯箱：黄铜边框，里面是自己发光的"地图" ---------- */
function makeLightbox(w: number, d: number, owned: THREE.Texture[]) {
  const M = materials(),
    g = new THREE.Group(),
    bar = 0.3;
  contact(g, w + 3.4, d + 3.4);
  add(g, new RoundedBoxGeometry(w + 0.5, 0.46, d + 0.5, 4, 0.08), M.brassDark, 0, 0.23, 0);
  for (const s of [-1, 1]) {
    add(g, new RoundedBoxGeometry(w + bar * 2, 0.18, bar, 3, 0.06), M.brass, 0, 0.53, s * (d / 2 + bar / 2 - 0.02));
    add(g, new RoundedBoxGeometry(bar, 0.18, d, 3, 0.06), M.brass, s * (w / 2 + bar / 2 - 0.02), 0.53, 0);
    for (const q of [-1, 1]) add(g, new THREE.CylinderGeometry(0.07, 0.07, 0.05, 16), M.brassDark, s * (w / 2 + bar / 2 - 0.02), 0.63, q * (d / 2 + bar / 2 - 0.02));
  }
  // 灯箱里不画江、路、区名（没有可靠的地理数据就不画），只有很淡的格子和一行说明
  const T = tex(1536, Math.round((1536 * d) / w), (c, W, H) => {
    c.fillStyle = "#2b2018";
    c.fillRect(0, 0, W, H);
    c.strokeStyle = "rgba(170,130,85,.16)";
    c.lineWidth = 2;
    for (let x = W / 12; x < W; x += W / 12) {
      c.beginPath();
      c.moveTo(x, 0);
      c.lineTo(x, H);
      c.stroke();
    }
    for (let y = H / 8; y < H; y += H / 8) {
      c.beginPath();
      c.moveTo(0, y);
      c.lineTo(W, y);
      c.stroke();
    }
    c.fillStyle = "rgba(233,223,198,.55)";
    c.font = `${W / 52}px ${MONO}`;
    c.fillText("示意：景点的相对位置", W * 0.025, H * 0.95);
  });
  owned.push(T);
  const sm = new THREE.MeshStandardMaterial({ color: 0x000000, emissiveMap: T, emissive: 0xffffff, emissiveIntensity: 1.0, roughness: 0.9 });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(w, d), sm);
  screen.rotation.x = -Math.PI / 2;
  screen.position.y = 0.47;
  g.add(screen);
  const glow = new THREE.PointLight(0xffd9a8, 0.5, 9, 1.5);
  glow.position.y = 1.2;
  g.add(glow);
  return g;
}
function makePin(color: number) {
  const M = materials(),
    g = new THREE.Group();
  add(g, new THREE.CylinderGeometry(0.022, 0.012, 0.5, 8), M.steel, 0, 0.25, 0);
  add(g, new THREE.SphereGeometry(0.14, 24, 16), new THREE.MeshPhysicalMaterial({ color, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.1 }), 0, 0.56, 0);
  return g;
}

/* ---------- 打字机：墨绿机身、黑色压纸辊、黄铜旋钮，卷着一张只写了模型名的纸 ---------- */
function makeTypewriter(label: string, owned: THREE.Texture[]) {
  const M = materials(),
    g = new THREE.Group();
  contact(g, 7, 5.4);
  add(g, new RoundedBoxGeometry(4.8, 0.9, 2.9, 6, 0.24), M.green, 0, 0.45, 0.55);
  add(g, new RoundedBoxGeometry(5.0, 0.7, 1.3, 5, 0.2), M.green, 0, 1.0, -0.6);
  add(g, new THREE.CylinderGeometry(0.36, 0.36, 4.5, 40), M.black, 0, 1.5, -0.6).rotation.z = Math.PI / 2;
  for (const s of [-1, 1]) add(g, new THREE.CylinderGeometry(0.44, 0.44, 0.24, 40), M.brass, s * 2.42, 1.5, -0.6).rotation.z = Math.PI / 2;
  add(g, new THREE.CylinderGeometry(0.035, 0.035, 4.1, 12), M.brass, 0, 1.93, -0.42).rotation.z = Math.PI / 2;
  for (let r = 0; r < 3; r++)
    for (let c = 0; c < 10; c++) {
      const x = -1.8 + c * 0.4 + (r % 2) * 0.2,
        z = 0.75 + r * 0.42,
        y = 0.98 - r * 0.03;
      add(g, new THREE.CylinderGeometry(0.15, 0.15, 0.05, 20), M.brassDark, x, y, z);
      add(g, new THREE.CylinderGeometry(0.125, 0.125, 0.09, 20), M.black, x, y + 0.05, z);
    }
  add(g, new RoundedBoxGeometry(2.6, 0.1, 0.3, 3, 0.04), M.brassDark, 0, 0.92, 1.92);
  const plateT = tex(512, 128, (c, w, h) => {
    const bg = c.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, "#e2c27e");
    bg.addColorStop(0.5, "#c9a45c");
    bg.addColorStop(1, "#a8833f");
    c.fillStyle = bg;
    c.fillRect(0, 0, w, h);
    c.strokeStyle = "#6e5326";
    c.lineWidth = 4;
    c.strokeRect(8, 8, w - 16, h - 16);
    c.fillStyle = COLORS.ink;
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.font = `600 62px ${SERIF}`;
    c.fillText(label.split("").join(" "), w / 2, h / 2 + 3);
  });
  owned.push(plateT);
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 0.375), new THREE.MeshStandardMaterial({ map: plateT, roughness: 0.32, metalness: 0.85, envMapIntensity: 1.6 }));
  plate.position.set(0, 0.42, 2.005);
  g.add(plate);
  // 纸上只写模型名，不写示例行程
  const paper = sheet(
    3.3,
    4.7,
    (c, w, h) => {
      paperBg(c, w, h);
      c.fillStyle = COLORS.soft;
      c.font = `24px ${MONO}`;
      c.fillText(label, 60, 80);
      c.fillStyle = "rgba(107,94,76,.25)";
      for (let y = 140; y < h - 40; y += 92) c.fillRect(40, y, w - 80, 2);
    },
    owned,
    false
  );
  paper.position.set(0, 1.5 + 2.2, -1.12);
  paper.rotation.x = -0.22;
  g.add(paper);
  return g;
}

/* ---------- 合着的笔记本：墨绿封皮、黄铜包角、一根松紧带，封面贴着写"我的行程"的标签 ---------- */
function makeNotebook(owned: THREE.Texture[]) {
  const M = materials(),
    g = new THREE.Group();
  contact(g, 8.4, 10.2);
  add(g, new RoundedBoxGeometry(6.0, 0.62, 8.0, 4, 0.08), M.green, 0, 0.31, 0);
  add(g, new THREE.BoxGeometry(5.8, 0.5, 7.8), M.paper, 0.08, 0.31, 0);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) add(g, new THREE.BoxGeometry(0.5, 0.66, 0.5), M.brass, sx * 2.78, 0.31, sz * 3.78);
  add(g, new THREE.BoxGeometry(0.18, 0.66, 8.04), M.black, 2.2, 0.31, 0);
  const label = sheet(
    3.2,
    1.5,
    (c, w, h) => {
      paperBg(c, w, h);
      c.strokeStyle = COLORS.ink;
      c.lineWidth = 3;
      c.strokeRect(14, 14, w - 28, h - 28);
      c.fillStyle = COLORS.ink;
      c.textAlign = "center";
      c.textBaseline = "middle";
      c.font = `600 ${Math.round(h * 0.34)}px ${SERIF}`;
      c.fillText("我的行程", w / 2, h * 0.52);
    },
    owned
  );
  label.position.set(-0.4, 0.635, -1.6);
  g.add(label);
  return g;
}

function makePen() {
  const M = materials(),
    o = new THREE.Group(),
    g = new THREE.Group();
  add(g, new THREE.CylinderGeometry(0.11, 0.1, 2.5, 24), M.green);
  add(g, new THREE.CylinderGeometry(0.125, 0.125, 0.95, 24), M.brassDark, 0, 0.95, 0);
  add(g, new THREE.CylinderGeometry(0.13, 0.13, 0.06, 24), M.brass, 0, 0.47, 0);
  add(g, new THREE.ConeGeometry(0.1, 0.5, 24), M.brass, 0, -1.5, 0).rotation.x = Math.PI;
  g.rotation.z = Math.PI / 2;
  g.position.y = 0.13;
  o.add(g);
  contact(o, 3.6, 1.0);
  return o;
}
function makeTicket(owned: THREE.Texture[]) {
  return sheet(
    2.3,
    1.15,
    (g, W, H) => {
      g.fillStyle = "#f4eedd";
      g.fillRect(0, 0, W, H);
      g.fillStyle = "#143026";
      g.fillRect(14, 14, W - 28, H - 28);
      g.fillStyle = COLORS.brass;
      g.font = `${H * 0.11}px ${MONO}`;
      g.fillText("METRO · 单程票", 36, H * 0.27);
      g.fillStyle = COLORS.paper;
      g.font = `600 ${H * 0.3}px ${SERIF}`;
      g.fillText("武汉地铁", 36, H * 0.63);
      for (let x = 36; x < W - 36; x += 9) g.fillRect(x, H * 0.76, 3, H * 0.1);
    },
    owned
  );
}

type V3 = [number, number, number];

export function createDesk(env: ActEnv, req0: StageRequest): Act {
  let data = (req0 as StageRequest<DeskData>).data;
  const owned: THREE.Texture[] = [];

  const scene = new THREE.Scene();
  scene.environment = env.environment;
  scene.environmentIntensity = 0.1;
  const { lamp } = addLights(scene, { lampPos: [-3, 13, 11], lampTarget: [0.4, 0.8, 0], lampPower: 0, lampAngle: 0.8 });
  scene.add(makeTable());
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(90, 24), new THREE.MeshStandardMaterial({ color: 0x120504, roughness: 1 }));
  wall.position.set(0, 12, -7);
  wall.receiveShadow = true;
  scene.add(wall);

  const camera = new THREE.PerspectiveCamera(30, env.width() / env.height(), 0.1, 120);

  /* ---------- 桌上的四件物件和点缀 ---------- */
  // 带字的物件（灯箱、打字机、笔记本、地铁票）要等字体加载好再搭，见下面的 ready
  const can = makeCanister("武汉", "WUHAN MEMORY").group;
  can.scale.setScalar(0.92);
  can.position.set(-7.4, 0, -0.6);
  scene.add(can);
  const pen = makePen();
  pen.scale.setScalar(0.8);
  pen.position.set(2.6, 0, 1.6);
  pen.rotation.y = 0.5;
  scene.add(pen);

  const BOX_W = 4.9,
    BOX_D = 3.3;
  function buildTexty() {
    const box = makeLightbox(BOX_W, BOX_D, owned);
    box.position.set(-2.5, 0, 1.5);
    box.rotation.y = 0.14;
    const pair = new THREE.Group();
    pair.position.set(3.9, 0, -1.8);
    ["千问", "豆包"].forEach((label, k) => {
      const tw = makeTypewriter(label, owned);
      tw.scale.setScalar(0.56);
      tw.position.set(k ? 1.65 : -1.65, 0, k ? 0.25 : 0);
      tw.rotation.y = k ? -0.14 : 0.1;
      pair.add(tw);
    });
    const book = makeNotebook(owned);
    book.scale.setScalar(0.5);
    book.position.set(7.0, 0, 2.2);
    book.rotation.y = -0.2;
    const metro = makeTicket(owned);
    metro.scale.setScalar(0.8);
    metro.position.set(-5.9, 0.03, 2.6);
    metro.rotation.y = -0.3;
    scene.add(box, pair, book, metro);
    return { box, pair, book };
  }

  /* 灯箱里的图钉：按真实坐标（GCJ-02）摆，范围外留一点边。坐标从网站自己的接口取，取不到就没有图钉 */
  const pins = new THREE.Group();
  async function loadPins() {
    try {
      const res = await fetch("/api/pois");
      if (!res.ok) return;
      const body = (await res.json()) as { pois: Array<{ location: { lng: number; lat: number } }> };
      const pts = body.pois.map((p) => p.location).filter((l) => Number.isFinite(l?.lng) && Number.isFinite(l?.lat));
      if (!pts.length) return;
      const lng0 = Math.min(...pts.map((p) => p.lng)),
        lng1 = Math.max(...pts.map((p) => p.lng)),
        lat0 = Math.min(...pts.map((p) => p.lat)),
        lat1 = Math.max(...pts.map((p) => p.lat));
      // 经纬度按武汉的纬度换成近似的东西、南北距离，保持比例，放进灯箱里（四周留 12%）
      const kx = Math.cos((((lat0 + lat1) / 2) * Math.PI) / 180);
      const spanX = Math.max(1e-6, (lng1 - lng0) * kx),
        spanY = Math.max(1e-6, lat1 - lat0);
      const scale = Math.min((BOX_W * 0.76) / spanX, (BOX_D * 0.76) / spanY);
      const cx = (lng0 + lng1) / 2,
        cy = (lat0 + lat1) / 2;
      for (const p of pts) {
        const pin = makePin(0xe2c27e);
        pin.scale.setScalar(0.55);
        pin.position.set((p.lng - cx) * kx * scale, 0.47, -(p.lat - cy) * scale);
        pins.add(pin);
      }
    } catch {
      // 后端连不上：灯箱里没有图钉，不影响别的
    }
  }

  /* ---------- 镜头的五个停靠点：全景，然后四件物件 ---------- */
  const WIDE = { pos: [0.4, 9.2, 20.5] as V3, look: [0.4, 2.7, 0] as V3 };
  const near = (ox: number, oz: number, side: number, h = 6.0, d = 13) => ({ pos: [ox + side * 2.5, h, oz + d] as V3, look: [ox + side * 2.5, 1.5, oz] as V3 });
  const objs: THREE.Object3D[] = [can];
  const VIEWS = [WIDE, near(-7.4, -0.6, 1), near(-2.5, 1.5, -1, 7.4, 11), near(3.9, -1.8, 1, 6.2, 13.5), near(7.0, 2.2, -1, 8.2, 9.5)];
  let y0: number[] = [];
  let hv: number[] = [];
  let meshesOf: THREE.Mesh[][] = [];
  function registerObjects() {
    y0 = objs.map((o) => o.position.y);
    hv = objs.map(() => 0);
    meshesOf = objs.map((o) => {
      const ms: THREE.Mesh[] = [];
      o.traverse((m) => {
        const mesh = m as THREE.Mesh;
        if (mesh.isMesh && !(mesh.material as THREE.Material).transparent) ms.push(mesh);
      });
      return ms;
    });
  }

  /* 镜头：窄屏时沿视线往后退，好装下物件；平时轻微跟着鼠标 */
  const P = new THREE.Vector3(),
    L = new THREE.Vector3(),
    lookNow = new THREE.Vector3();
  const place = (p: V3, l: V3) => {
    const lv = new THREE.Vector3(...l);
    return lv.clone().add(new THREE.Vector3(...p).sub(lv).multiplyScalar(Math.max(1, 1.7 / (env.width() / env.height()))));
  };

  let at = Math.min(VIEWS.length - 1, Math.max(0, data.at ?? 0)),
    lit = data.intro ? 0 : 1,
    hovered = -1,
    focused = -1,
    wheelAcc = 0,
    wheelLock = 0,
    lampFollow = true,
    leaving = false;
  const ray = new THREE.Raycaster();

  function emit() {
    env.emit({ kind: "desk", at, n: VIEWS.length, intro: lit < 0.98 });
  }
  function show(i: number) {
    const next = Math.max(0, Math.min(VIEWS.length - 1, i));
    if (next === at) return;
    at = next;
    emit();
  }
  function enter(k: number) {
    const href = data.stops[k]?.href;
    if (!href || leaving) return;
    leaving = true;
    env.navigate(href);
  }

  const onWheel = (e: WheelEvent) => {
    if (!env.active() || leaving) return;
    const now = performance.now();
    if (now < wheelLock) return;
    wheelAcc += e.deltaY;
    if (Math.abs(wheelAcc) > 60) {
      lit = Math.max(lit, 0.98); // 滚动时开场直接结束
      show(at + Math.sign(wheelAcc));
      wheelAcc = 0;
      wheelLock = now + 700;
    }
  };
  const onClick = (e: MouseEvent) => {
    if (!env.active() || leaving || e.button !== 0 || e.target !== env.renderer.domElement) return;
    if (lit < 0.98) {
      lit = 0.98; // 开场时点一下跳过
      emit();
      return;
    }
    if (hovered >= 0) enter(hovered);
  };
  window.addEventListener("wheel", onWheel, { passive: true });
  window.addEventListener("click", onClick);

  /** 物件在屏幕上的外框（键盘聚焦时的黄铜框） */
  const bb = new THREE.Box3(),
    v = new THREE.Vector3();
  function objRect(k: number) {
    // 只算看得见的实体（不算桌上的接触阴影和灯光），框才贴着物件
    bb.makeEmpty();
    for (const m of meshesOf[k]) bb.expandByObject(m);
    let x0 = Infinity,
      y0r = Infinity,
      x1 = -Infinity,
      y1 = -Infinity;
    for (const x of [bb.min.x, bb.max.x])
      for (const y of [bb.min.y, bb.max.y])
        for (const z of [bb.min.z, bb.max.z]) {
          v.set(x, y, z).project(camera);
          const px = (v.x * 0.5 + 0.5) * env.width(),
            py = (-v.y * 0.5 + 0.5) * env.height();
          x0 = Math.min(x0, px);
          y0r = Math.min(y0r, py);
          x1 = Math.max(x1, px);
          y1 = Math.max(y1, py);
        }
    return { x: x0 - 8, y: y0r - 8, w: x1 - x0 + 16, h: y1 - y0r + 16 };
  }

  /* ---------- 每一帧 ---------- */
  let wasIntro = lit < 0.98;
  function step(dt: number) {
    // 开场：灯慢慢亮起（G6），不超过 2 秒
    lit = dt === 0 ? lit : damp(lit, 1, 2.2, dt);
    lamp.intensity = 8.2 * lit;
    if (wasIntro && lit >= 0.98) {
      wasIntro = false;
      emit();
    }

    hovered = -1;
    if (env.ndc.x < 2 && lit > 0.6 && !leaving) {
      ray.setFromCamera(env.ndc, camera);
      const hit = ray.intersectObjects(meshesOf.flat(), false)[0];
      if (hit) hovered = meshesOf.findIndex((ms) => ms.includes(hit.object as THREE.Mesh));
    }
    env.renderer.domElement.style.cursor = hovered >= 0 ? "pointer" : "default";
    objs.forEach((o, k) => {
      hv[k] = damp(hv[k], hovered === k || focused === k ? 1 : 0, 8, dt);
      const H = Math.max(hv[k], at === k + 1 ? 0.35 : 0);
      o.position.y = damp(o.position.y, y0[k] + H * 0.22, 6, dt);
    });
    if (hovered >= 0) {
      v.copy(objs[hovered].position);
      v.y += 0.4;
      v.project(camera);
      env.tag({ text: `${data.stops[hovered]?.label ?? ""}`, x: (v.x * 0.5 + 0.5) * env.width(), y: (-v.y * 0.5 + 0.5) * env.height() + 40 });
    } else env.tag(null);
    env.ring(focused >= 0 && !leaving ? objRect(focused) : null);

    // 镜头去当前停靠点；点了物件以后推近
    const view = VIEWS[at];
    const goal = place(view.pos, view.look);
    const m = env.ndc.x < 2 ? env.mouse : { x: 0, y: 0 };
    goal.x += m.x * 0.6;
    goal.y -= m.y * 0.3;
    if (leaving) goal.lerp(new THREE.Vector3(...view.look), 0.35);
    L.set(...view.look);
    if (dt === 0) {
      camera.position.copy(goal);
      lookNow.copy(L);
    } else {
      const s = 2.2;
      P.copy(camera.position);
      camera.position.set(damp(P.x, goal.x, s, dt), damp(P.y, goal.y, s, dt), damp(P.z, goal.z, s, dt));
      lookNow.set(damp(lookNow.x, L.x, s, dt), damp(lookNow.y, L.y, s, dt), damp(lookNow.z, L.z, s, dt));
    }
    camera.lookAt(lookNow);
    const lx = view.look[0];
    lamp.position.x = damp(lamp.position.x, lx - 3 + (lampFollow ? m.x * 2.4 : 0), 2, dt);
    lamp.target.position.x = damp(lamp.target.position.x, lx, 2, dt);
  }

  const ready = (async () => {
    await ensureFonts("武汉千问豆包我的行程地铁单程票示意：景点的相对位置WUHANMEMORYMETRO·");
    const { box, pair, book } = buildTexty();
    box.add(pins);
    objs.push(box, pair, book);
    registerObjects();
    await loadPins();
    emit();
  })();

  return {
    scene,
    camera,
    ready,
    update(next) {
      data = (next as StageRequest<DeskData>).data;
      leaving = false;
      emit();
      return true;
    },
    step,
    resize(w, h) {
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    },
    setQuality(level) {
      applyShadowQuality(lamp, level);
      lampFollow = level === 0;
    },
    command(cmd: StageCommand) {
      switch (cmd.type) {
        case "show":
          lit = Math.max(lit, 0.98);
          show(Number(cmd.at) || 0);
          break;
        case "step":
          lit = Math.max(lit, 0.98);
          show(at + (Number(cmd.dir) || 0));
          break;
        case "focus": {
          const k = Number(cmd.k);
          focused = k >= 0 && k < objs.length ? k : -1;
          if (focused >= 0) {
            lit = Math.max(lit, 0.98);
            show(focused + 1);
          }
          break;
        }
        case "blur":
          focused = -1;
          break;
        case "enter":
          enter(Number(cmd.k));
          break;
        case "skip-intro":
          lit = Math.max(lit, 0.98);
          emit();
          break;
      }
    },
    dispose() {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("click", onClick);
      for (const t of owned) t.dispose();
      disposeTree(scene);
    }
  };
}
