/**
 * 第二幕：晾片（/places/[id]，设计规范第 8.2 节）。从样片 docs/design/prototypes/darkroom-line.html 改写，
 * 位置、尺寸、灯光、动画照搬，数据换成真实景点（lib/scene3d/data.ts 的 LineData）。
 *
 * - 暗红色的墙前一根晾片绳，全部景点的白边照片用木夹子夹成一排，选中的在正中、更大、原色，夹子是红的。
 * - 有封面照片就用照片；没有（公开模式）就是空白相纸，打字机字写景点名，铅笔蓝灰色写"照片待补"。
 * - 桌上一个不锈钢显影盘，里面四张主题卡，卡上写主题名和这张纸的状态（和普通版的章一致）。
 * - 换景点：场景先滑过去，再由网页（app/places/LineStage.tsx）改地址、取新景点的资料。
 * - 点主题卡：镜头推近这张卡，然后去 /places/[id]/[主题]；点胶卷罐回胶卷幕。
 */
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { COLORS, MONO, NOTE, SERIF, TYPE, add, contact, damp, disposeTree, ensureFonts, loadPhotoTexture, makeCanister, makeTable, materials, pad, rnd, reseed, sh, tex, textureToCanvas } from "../common";
import type { LineData, LinePrint, LineTopic } from "../data";
import { addLights, applyShadowQuality } from "../engine";
import type { Act, ActEnv } from "../engine";
import type { StageCommand, StageRequest } from "../types";

const WALL_Z = -1.5,
  ROPE_Y = 5.15,
  LINE_Z = WALL_Z + 0.5,
  SP = 2.05;
const PH_W = 1.3,
  PH_H = 1.5;
const STATUS_TEXT = { verified: "已核实", pending: "待确认", expired: "已过期" } as const;
const STATUS_COLOR = { verified: COLORS.green, pending: COLORS.pencil, expired: COLORS.oxblood } as const;

function coverCrop(t: THREE.Texture, aspect: number) {
  const img = t.image as { width: number; height: number };
  const ia = img.width / img.height;
  if (ia > aspect) {
    t.repeat.set(aspect / ia, 1);
    t.offset.set((1 - aspect / ia) / 2, 0);
  } else {
    t.repeat.set(1, ia / aspect);
    t.offset.set(0, (1 - ia / aspect) / 2);
  }
  // 只改裁切（repeat、offset），不用 needsUpdate：那会让显卡把整张图重新传一遍
}

/** 没有照片时的空白相纸（设计规范第 15 节第 3 条） */
function blankPrint(p: LinePrint) {
  const w = 520,
    h = Math.round((520 * PH_H) / PH_W);
  return tex(w, h, (g) => {
    g.fillStyle = "#e6dcc3";
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 900; i++) {
      g.fillStyle = `rgba(120,95,60,${Math.random() * 0.05})`;
      g.fillRect(Math.random() * w, Math.random() * h, 2 + Math.random() * 24, 1);
    }
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillStyle = COLORS.ink;
    let size = 92;
    g.font = `700 ${size}px ${TYPE}`;
    while (g.measureText(p.name).width > w - 60 && size > 30) g.font = `700 ${(size -= 2)}px ${TYPE}`;
    g.fillText(p.name, w / 2, h / 2 - 40);
    g.save();
    g.translate(w / 2, h / 2 + 60);
    g.rotate(-0.03);
    g.fillStyle = COLORS.pencil;
    g.font = `58px ${NOTE}`;
    g.fillText("照片待补", 0, 0);
    g.restore();
  });
}

function cardTexture(k: number, topic: LineTopic) {
  return tex(640, 448, (g, w, h) => {
    g.fillStyle = COLORS.paper;
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 900; i++) {
      g.fillStyle = `rgba(120,95,60,${Math.random() * 0.05})`;
      g.fillRect(Math.random() * w, Math.random() * h, 2 + Math.random() * 30, 1);
    }
    g.strokeStyle = "rgba(42,36,32,.55)";
    g.lineWidth = 2;
    g.strokeRect(22, 22, w - 44, h - 44);
    g.fillStyle = COLORS.oxblood;
    g.font = `34px ${MONO}`;
    g.fillText(pad(k + 1), 48, 86);
    g.fillStyle = "rgba(42,36,32,.35)";
    g.fillRect(48, 112, w - 96, 2);
    g.fillStyle = COLORS.ink;
    g.font = `600 104px ${SERIF}`;
    g.textAlign = "center";
    g.fillText(topic.name, w / 2, 262);
    // 这张纸的状态，和普通版信纸右下角的章一致
    const c = STATUS_COLOR[topic.status];
    g.save();
    g.translate(w / 2, 362);
    g.rotate(-0.05);
    g.strokeStyle = c;
    g.fillStyle = c;
    g.lineWidth = 4;
    g.strokeRect(-78, -30, 156, 60);
    g.font = `600 34px ${SERIF}`;
    g.textBaseline = "middle";
    g.fillText(STATUS_TEXT[topic.status], 0, 2);
    g.restore();
  });
}

export function createLine(env: ActEnv, req0: StageRequest): Act {
  let data = (req0 as StageRequest<LineData>).data;
  const prints0 = data.prints;
  const N = prints0.length;
  const M = materials();
  const owned: THREE.Texture[] = [];

  const scene = new THREE.Scene();
  scene.environment = env.environment;
  scene.environmentIntensity = 0.1;
  const { lamp } = addLights(scene, { lampPos: [-2.5, 10.5, 8.5], lampTarget: [0, 2.6, 0], lampPower: 9, lampAngle: 0.85 });

  const camera = new THREE.PerspectiveCamera(52, env.width() / env.height(), 0.1, 120);
  const camZ = () => Math.min(16, Math.max(10.5, 10.5 * (1.7 / (env.width() / env.height()))));
  const fitFog = () => {
    const f = scene.fog as THREE.Fog;
    f.near = camZ() + 15;
    f.far = camZ() + 39;
  };
  const CAM = new THREE.Vector3(0, 5.4, camZ()),
    LOOK = new THREE.Vector3(0, 2.9, 0);
  const camPos = CAM.clone(),
    camLook = LOOK.clone(),
    lookNow = LOOK.clone();
  camera.position.copy(CAM);
  fitFog();

  scene.add(makeTable());

  /* ---------- 墙和晾片绳 ---------- */
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(70, 26), new THREE.MeshStandardMaterial({ color: 0x4a140d, roughness: 0.95 }));
  wall.position.set(0, 13, WALL_Z);
  wall.receiveShadow = true;
  scene.add(wall);
  const rope = add(scene, new THREE.CylinderGeometry(0.022, 0.022, 60, 8), new THREE.MeshStandardMaterial({ color: 0xcdbf9f, roughness: 0.9 }), 0, ROPE_Y, LINE_Z);
  rope.rotation.z = Math.PI / 2;

  /* ---------- 照片：每个景点一张，夹在绳子上 ---------- */
  interface Print {
    p: LinePrint;
    i: number;
    g: THREE.Group;
    pm: THREE.MeshStandardMaterial;
    pegMat: THREE.MeshStandardMaterial;
    meshes: THREE.Mesh[];
    hv: number;
    sv: number;
    phase: number;
    tilt: number;
    drop: number;
    photo: "none" | "loading" | "done";
    /** 空白相纸的贴图（没有照片时用） */
    blank: THREE.Texture;
  }
  reseed(42);
  const prints: Print[] = prints0.map((p, i) => {
    const g = new THREE.Group();
    const paper = add(g, new THREE.BoxGeometry(1.5, 1.86, 0.014), M.paper, 0, -1.0, 0);
    const t0 = blankPrint(p);
    owned.push(t0);
    const pm = new THREE.MeshStandardMaterial({ map: t0, emissiveMap: t0, emissive: 0xffffff, emissiveIntensity: 0.12, roughness: 0.55 });
    const ph = new THREE.Mesh(new THREE.PlaneGeometry(PH_W, PH_H), pm);
    ph.position.set(0, -0.93, 0.009);
    g.add(ph);
    const pegMat = new THREE.MeshStandardMaterial({ color: 0xb8794a, roughness: 0.7 });
    const peg = add(g, new THREE.BoxGeometry(0.13, 0.4, 0.13), pegMat, 0, -0.06, 0.02);
    add(g, new THREE.BoxGeometry(0.15, 0.03, 0.15), M.steel, 0, 0.02, 0.02);
    for (const m of [paper, ph, peg]) m.userData.print = i;
    scene.add(g);
    return { p, i, g, pm, pegMat, meshes: [paper, ph, peg], hv: 0, sv: 0, phase: rnd() * 6.28, tilt: (rnd() - 0.5) * 0.09, drop: 0, photo: p.photoUrl ? "none" : "done", blank: t0 };
  });
  const printMeshes = prints.flatMap((p) => p.meshes);

  function loadPhoto(pr: Print): Promise<void> {
    if (pr.photo !== "none" || !pr.p.photoUrl) return Promise.resolve();
    pr.photo = "loading";
    return loadPhotoTexture(pr.p.photoUrl, env.renderer, { fallbackUrl: pr.p.photoFull }).then(
      (t) => {
        coverCrop(t, PH_W / PH_H);
        owned.push(t);
        pr.pm.map = t;
        pr.pm.emissiveMap = t;
        pr.photo = "done";
      },
      () => {
        pr.photo = "done";
      }
    );
  }

  /* ---------- 显影盘和四张主题卡 ---------- */
  const TRAY = new THREE.Vector3(-0.3, 0, 2.6),
    TW = 8.6,
    TD = 2.6;
  const tray = new THREE.Group();
  tray.position.copy(TRAY);
  scene.add(tray);
  contact(tray, TW + 2.4, TD + 2.2);
  add(tray, new RoundedBoxGeometry(TW, 0.1, TD, 4, 0.04), M.steel, 0, 0.05, 0);
  for (const sd of [-1, 1]) {
    add(tray, new RoundedBoxGeometry(TW, 0.44, 0.16, 4, 0.07), M.steel, 0, 0.27, sd * (TD / 2 - 0.08));
    add(tray, new RoundedBoxGeometry(0.16, 0.44, TD, 4, 0.07), M.steel, sd * (TW / 2 - 0.08), 0.27, 0);
  }
  const liquid = new THREE.Mesh(
    new THREE.PlaneGeometry(TW - 0.3, TD - 0.3),
    new THREE.MeshPhysicalMaterial({ color: 0x3a0f08, roughness: 0.06, metalness: 0, transparent: true, opacity: 0.55, envMapIntensity: 5 })
  );
  liquid.rotation.x = -Math.PI / 2;
  liquid.position.y = 0.2;
  liquid.receiveShadow = true;
  tray.add(liquid);

  interface Card {
    k: number;
    topic: LineTopic;
    g: THREE.Group;
    face: THREE.Mesh;
    mat: THREE.MeshStandardMaterial;
    base: THREE.Vector3;
    rz: number;
    hv: number;
  }
  const RZ = [-0.07, 0.05, -0.03, 0.08];
  const cards: Card[] = data.topics.map((topic, k) => {
    const t = cardTexture(k, topic);
    owned.push(t);
    const g = new THREE.Group();
    const mat = new THREE.MeshStandardMaterial({ map: t, roughness: 0.8, color: 0x9a8a80 });
    const face = sh(new THREE.Mesh(new THREE.BoxGeometry(1.75, 1.22, 0.02), [M.paper, M.paper, M.paper, M.paper, mat, M.paper]));
    face.rotation.x = -Math.PI / 2;
    face.userData.card = k;
    g.add(face);
    g.position.set(-2.95 + k * 1.97, 0.24, 0.05);
    tray.add(g);
    return { k, topic, g, face, mat, base: g.position.clone(), rz: RZ[k % 4], hv: 0 };
  });
  /** 换景点时主题卡上的状态跟着换 */
  function redrawCards() {
    cards.forEach((c, k) => {
      const topic = data.topics[k];
      if (!topic || topic.status === c.topic.status) return;
      c.topic = topic;
      const t = cardTexture(k, topic);
      owned.push(t);
      c.mat.map = t;
      env.renderer.initTexture(t); // 先传到显卡，不在下一帧里现传
    });
  }

  /* 竹夹和右下角的胶卷罐（回到胶卷幕） */
  const tong = new THREE.Group();
  tong.position.set(TRAY.x + 4.4, 0.5, TRAY.z + 0.9);
  scene.add(tong);
  for (const sd of [-1, 1]) {
    const b = add(tong, new THREE.BoxGeometry(2.6, 0.05, 0.16), M.bamboo, 0, sd * 0.04, 0);
    b.rotation.z = sd * 0.02;
  }
  tong.rotation.set(0.05, 0.5, -0.1);
  const canParts = makeCanister("武汉", `WUHAN MEMORY · ${pad(N)} EXP`);
  const can = canParts.group;
  can.scale.setScalar(0.6);
  can.position.set(6.0, 0, 1.2);
  can.rotation.y = -0.25;
  scene.add(can);
  const canMeshes = can.children.filter((c): c is THREE.Mesh => (c as THREE.Mesh).isMesh && (c as THREE.Mesh).geometry.type === "CylinderGeometry");
  let canHv = 0;

  /* ---------- 状态 ---------- */
  const idx = (id: string) => prints.findIndex((p) => p.p.id === id);
  let sel = Math.max(0, idx(data.sel));
  let cur = sel,
    t = 0,
    entered: Card | null = null,
    focus: { type: "print"; i: number } | { type: "card"; k: number } | { type: "can" } | null = null,
    hovered: { type: "print"; i: number } | { type: "card"; k: number } | { type: "can" } | null = null,
    wheelAcc = 0,
    wheelLock = 0,
    lampFollow = true,
    /** 用户上一次在场景里换景点的时间。刚换过时不让地址里的旧景点把照片拉回去 */
    localAt = -Infinity,
    moving = false,
    /** 转场时正飞过来的那张照片：落地以前藏着，不参加"从上方落下" */
    arriving = -1;
  const ray = new THREE.Raycaster();

  function emit() {
    env.emit({ kind: "line", sel, id: prints[sel]?.p.id ?? null, n: N, entering: !!entered, moving, card: entered?.k ?? (hovered?.type === "card" ? hovered.k : focus?.type === "card" ? focus.k : -1) });
  }
  function loadAround() {
    for (const p of prints) if (Math.abs(p.i - sel) <= 3) void loadPhoto(p);
  }
  function select(i: number, local = true) {
    i = THREE.MathUtils.clamp(i, 0, N - 1);
    if (local) localAt = performance.now();
    if (i === sel) return;
    sel = i;
    loadAround();
    emit();
  }
  /** 进场：照片从上方落到绳子上，离选中的越远落得越晚 */
  function dropIn() {
    for (const p of prints) p.drop = 1 + Math.abs(p.i - sel) * 0.35;
  }
  function enterCard(c: Card) {
    if (entered) return;
    entered = c;
    emit();
    const href = `/places/${prints[sel].p.id}/${c.topic.id}`;
    // 镜头推近以后，把这张主题卡交给转场的替身（G4：它会翻过来变成信纸）
    window.setTimeout(() => {
      if (entered !== c || !env.active()) return;
      const r = screenRect(c.g, CARD_CORNERS);
      const image = textureToCanvas(c.mat.map);
      env.navigate(href, image ? { handoff: { kind: "card", id: prints[sel].p.id, topic: c.topic.id, rect: { x: r.x + 6, y: r.y + 6, w: r.w - 12, h: r.h - 12 }, image } } : undefined);
    }, 1000);
  }

  const onWheel = (e: WheelEvent) => {
    if (!env.active() || entered) return;
    const now = performance.now();
    if (now < wheelLock) return;
    wheelAcc += e.deltaY + e.deltaX;
    if (Math.abs(wheelAcc) > 50) {
      select(sel + Math.sign(wheelAcc));
      wheelAcc = 0;
      wheelLock = now + 280;
    }
  };
  const onClick = (e: MouseEvent) => {
    if (!env.active() || entered || e.button !== 0 || e.target !== env.renderer.domElement) return;
    if (!hovered) return;
    if (hovered.type === "print") select(hovered.i);
    else if (hovered.type === "card") enterCard(cards[hovered.k]);
    else env.navigate(`/places?at=${encodeURIComponent(prints[sel].p.id)}`);
  };
  window.addEventListener("wheel", onWheel, { passive: true });
  window.addEventListener("click", onClick);

  function pick() {
    hovered = null;
    if (entered || env.ndc.x > 2) return;
    ray.setFromCamera(env.ndc, camera);
    const hit = ray.intersectObjects([...printMeshes.filter((m) => m.parent!.visible), ...cards.map((c) => c.face), ...canMeshes], false)[0];
    if (!hit) return;
    const u = hit.object.userData;
    hovered = u.print !== undefined ? { type: "print", i: u.print as number } : u.card !== undefined ? { type: "card", k: u.card as number } : { type: "can" };
  }

  /* ---------- 投到屏幕上：黄铜框和名字 ---------- */
  const v = new THREE.Vector3();
  function screenRect(obj: THREE.Object3D, pts: Array<[number, number, number]>) {
    let x0 = Infinity,
      y0 = Infinity,
      x1 = -Infinity,
      y1 = -Infinity;
    for (const p of pts) {
      v.set(...p);
      obj.localToWorld(v).project(camera);
      const px = (v.x * 0.5 + 0.5) * env.width(),
        py = (-v.y * 0.5 + 0.5) * env.height();
      x0 = Math.min(x0, px);
      y0 = Math.min(y0, py);
      x1 = Math.max(x1, px);
      y1 = Math.max(y1, py);
    }
    return { x: x0 - 6, y: y0 - 6, w: x1 - x0 + 12, h: y1 - y0 + 12 };
  }
  const PRINT_CORNERS: Array<[number, number, number]> = [
    [-0.75, -1.93, 0],
    [0.75, -1.93, 0],
    [-0.75, 0.2, 0],
    [0.75, 0.2, 0]
  ];
  const CARD_CORNERS: Array<[number, number, number]> = [
    [-0.875, 0, -0.61],
    [0.875, 0, -0.61],
    [-0.875, 0, 0.61],
    [0.875, 0, 0.61]
  ];

  /* ---------- 每一帧 ---------- */
  let lastHoverKey = "";
  function step(dt: number) {
    t += dt;
    cur = dt === 0 ? sel : damp(cur, sel, 4.5, dt);
    // 照片滑到位了没有：网页等滑完再换地址（换页面那一下主线程要忙几十毫秒，放在滑动中间会卡一下）
    const nowMoving = Math.abs(cur - sel) > 0.05;
    if (nowMoving !== moving) {
      moving = nowMoving;
      emit();
    }
    pick();
    env.renderer.domElement.style.cursor = hovered ? "pointer" : "default";
    const hoverKey = hovered ? `${hovered.type}${"i" in hovered ? hovered.i : "k" in hovered ? hovered.k : ""}` : "";
    if (hoverKey !== lastHoverKey) {
      lastHoverKey = hoverKey;
      emit();
    }
    // 键盘聚焦的物件和鼠标悬停的物件一样有反应
    const act = hovered ?? focus;

    // 照片：选中的更大、原色、向前、夹子变红；其余罩着暗房红，轻轻摆动
    for (const p of prints) {
      const d = p.i - cur;
      p.g.visible = Math.abs(d) < 6.2 && p.i !== arriving;
      if (!p.g.visible) continue;
      p.sv = dt === 0 ? (p.i === sel ? 1 : 0) : damp(p.sv, p.i === sel ? 1 : 0, 6, dt);
      p.hv = damp(p.hv, act?.type === "print" && act.i === p.i ? 1 : 0, 9, dt);
      p.drop = damp(p.drop, 0, 2.2, dt);
      const S = p.sv,
        H = p.hv * (1 - S);
      p.g.position.set(d * SP + THREE.MathUtils.clamp(d, -1, 1) * 0.5, ROPE_Y + p.drop * 3.5, LINE_Z + S * 0.75 + H * 0.5);
      p.g.scale.setScalar(1 + S * 0.42 + H * 0.16);
      p.g.rotation.x = Math.sin(t * 0.9 + p.phase) * 0.035 * (1 - S * 0.7) + p.drop * Math.sin(t * 5 + p.phase) * 0.5 - H * 0.12;
      p.g.rotation.z = p.tilt * (1 - S) * (1 - H);
      const lit = Math.max(S, H);
      p.pm.color.setRGB(1, 0.4 + lit * 0.6, 0.28 + lit * 0.72);
      // 空白相纸自己是浅色的，再发光字就看不清了，所以发光弱一些
      const blank = p.pm.map === p.blank;
      p.pm.emissiveIntensity = blank ? 0.04 + lit * 0.1 : 0.1 + lit * 0.45;
      p.pegMat.color.setRGB(0.72 + S * 0.05, 0.47 - S * 0.34, 0.29 - S * 0.19);
    }

    // 主题卡：抬起、转向镜头、放大、被照亮；其余变暗
    const onCard = (c: Card) => (act?.type === "card" && act.k === c.k) || entered === c;
    const anyCard = cards.some(onCard);
    for (const c of cards) {
      const on = onCard(c);
      c.hv = damp(c.hv, on ? 1 : 0, 8, dt);
      const H = c.hv;
      c.g.position.set(c.base.x, c.base.y + H * 1.15 + Math.sin(t * 1.3 + c.k) * 0.012, c.base.z + H * 0.35);
      c.g.rotation.set(H * 0.82, 0, c.rz * (1 - H));
      c.g.scale.setScalar(1 + H * 0.26);
      const b = 0.6 + H * 0.4 - (anyCard && !on ? 0.16 : 0);
      c.mat.color.setRGB(b, b * 0.95, b * 0.9);
    }
    const hc = cards.find(onCard);
    tong.position.x = damp(tong.position.x, hc ? TRAY.x + hc.base.x + 1.25 : TRAY.x + 4.4, 5, dt);

    canHv = damp(canHv, act?.type === "can" ? 1 : 0, 8, dt);
    can.position.y = canHv * 0.18;
    can.rotation.y = -0.25 + canHv * 0.2;

    // 悬停在别的照片上时，在它下方显示序号和景点名
    const hp = act?.type === "print" && act.i !== sel ? prints[act.i] : null;
    if (hp && !entered) {
      v.set(0, -2.05, 0);
      hp.g.localToWorld(v).project(camera);
      env.tag({ text: `${pad(hp.p.no)} · ${hp.p.name}`, x: (v.x * 0.5 + 0.5) * env.width(), y: (-v.y * 0.5 + 0.5) * env.height() + 10 });
    } else if (act?.type === "can" && !entered) {
      v.set(0, 0, 1.4);
      can.localToWorld(v).project(camera);
      env.tag({ text: "回到胶卷", x: (v.x * 0.5 + 0.5) * env.width(), y: (-v.y * 0.5 + 0.5) * env.height() + 10 });
    } else env.tag(null);

    // 键盘聚焦时的黄铜框
    if (focus && !entered) {
      if (focus.type === "print") env.ring(screenRect(prints[focus.i].g, PRINT_CORNERS));
      else if (focus.type === "card") env.ring(screenRect(cards[focus.k].g, CARD_CORNERS));
      else env.ring(null);
    } else env.ring(null);

    // 镜头
    const m = env.ndc.x < 2 ? env.mouse : { x: 0, y: 0 };
    if (entered) {
      camPos.set(TRAY.x + entered.base.x, 4.4, TRAY.z + 4.4);
      camLook.set(TRAY.x + entered.base.x, 1.4, TRAY.z);
    } else {
      camPos.set(CAM.x + m.x * 0.55, CAM.y - m.y * 0.3, CAM.z);
      camLook.copy(LOOK);
    }
    const cs = entered ? 2.4 : 3.2;
    if (dt === 0) {
      camera.position.copy(camPos);
      lookNow.copy(camLook);
    } else {
      camera.position.set(damp(camera.position.x, camPos.x, cs, dt), damp(camera.position.y, camPos.y, cs, dt), damp(camera.position.z, camPos.z, cs, dt));
      lookNow.set(damp(lookNow.x, camLook.x, cs, dt), damp(lookNow.y, camLook.y, cs, dt), damp(lookNow.z, camLook.z, cs, dt));
    }
    camera.lookAt(lookNow);
    lamp.position.x = damp(lamp.position.x, -2.5 + (lampFollow ? m.x * 2.2 : 0), 2, dt);
  }

  const ready = (async () => {
    await ensureFonts(prints0.map((p) => p.name).join("") + data.topics.map((tp) => tp.name).join("") + "照片待补已核实待确认已过期0123456789WUHANMEMORYEXP·");
    // 字体到了以后重画用到字的贴图
    for (const p of prints) {
      if (p.photo === "done" && p.p.photoUrl) continue;
      const t2 = blankPrint(p.p);
      owned.push(t2);
      p.blank = t2;
      p.pm.map = t2;
      p.pm.emissiveMap = t2;
    }
    cards.forEach((c, k) => {
      const t2 = cardTexture(k, c.topic);
      owned.push(t2);
      c.mat.map = t2;
    });
    dropIn();
    emit();
    await Promise.all(prints.filter((p) => Math.abs(p.i - sel) <= 2).map(loadPhoto));
  })();
  // 准备好以后，其余照片一张一张在后台取（有照片的不该一直显示"照片待补"）
  void ready.then(async () => {
    for (const p of prints) await loadPhoto(p);
  });

  return {
    scene,
    camera,
    ready,
    update(next) {
      const d = (next as StageRequest<LineData>).data;
      // 景点清单变了（例如资料改过）：重建
      if (d.prints.length !== N || d.prints.some((p, i) => p.id !== prints[i].p.id)) return false;
      const fromOtherAct = !env.active();
      data = d;
      entered = null;
      focus = null;
      // 地址里的景点：刚在场景里换过（地址还没跟上）时不理它，其余情况（前进后退、从别的幕回来）照它
      if (fromOtherAct || performance.now() - localAt > 2500) select(Math.max(0, idx(d.sel)), false);
      redrawCards();
      if (fromOtherAct) {
        cur = sel;
        dropIn();
      }
      emit();
      return true;
    },
    step,
    resize(w, h) {
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      CAM.z = camZ();
      fitFog();
    },
    setQuality(level) {
      applyShadowQuality(lamp, level);
      lampFollow = level === 0;
    },
    query(q: StageCommand) {
      // 转场：选中的照片落稳以后在屏幕上的位置（相纸外框）、样子、白边比例和歪斜角度
      if (q.type !== "arrival") return null;
      const p = prints[sel];
      if (!p) return null;
      const pose = new THREE.Object3D();
      pose.position.set(0, ROPE_Y, LINE_Z + 0.75);
      pose.scale.setScalar(1.42);
      scene.add(pose);
      pose.updateMatrixWorld();
      const r = screenRect(pose, PRINT_CORNERS);
      scene.remove(pose);
      // 相纸 1.5 × 1.86，照片 1.3 × 1.5，照片偏上：上边 0.11、左右 0.1、下边 0.25（按相纸宽度的比例）
      return {
        rect: { x: r.x + 6, y: r.y + 6, w: r.w - 12, h: r.h - 12 },
        image: textureToCanvas(p.pm.map),
        pad: { top: 0.11 / 1.5, side: 0.1 / 1.5, bottom: 0.25 / 1.5 },
        rotate: 0
      };
    },
    command(cmd: StageCommand) {
      switch (cmd.type) {
        case "arrive": {
          const i = idx(String(cmd.id));
          if (i >= 0) {
            arriving = i;
            prints[i].drop = 0;
            prints[i].sv = 1;
          }
          break;
        }
        case "landed":
          arriving = -1;
          break;
        case "step":
          if (!entered) select(sel + (Number(cmd.dir) || 0));
          break;
        case "select": {
          const i = idx(String(cmd.id));
          if (i >= 0 && !entered) select(i);
          break;
        }
        case "focus-print": {
          const i = idx(String(cmd.id));
          focus = i >= 0 ? { type: "print", i } : null;
          break;
        }
        case "focus-topic": {
          const k = cards.findIndex((c) => c.topic.id === cmd.id);
          focus = k >= 0 ? { type: "card", k } : null;
          emit();
          break;
        }
        case "blur":
          focus = null;
          emit();
          break;
        case "enter-topic": {
          const c = cards.find((cc) => cc.topic.id === cmd.id);
          if (c) enterCard(c);
          break;
        }
      }
    },
    dispose() {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("click", onClick);
      for (const tx of owned) tx.dispose();
      disposeTree(scene);
    }
  };
}
