/**
 * 第一幕：胶卷（/places，设计规范第 8.1 节）。从样片 docs/design/prototypes/darkroom-rolls.html 改写：
 * 位置、尺寸、灯光、动画的参数照搬，数据换成真实景点（lib/scene3d/data.ts 的 RollsData）。
 *
 * - 左边一个胶卷罐，一条胶片从罐里拉出来横贯画面，每一格是一个景点。
 * - 看片器骑在胶片上，鼠标指着当前组的哪一格就滑到哪一格，画框里是那个景点，铭牌刻着名字。
 * - 有封面照片（本机模式）就用照片；没有（公开模式隐藏了占位照片）就是没曝光的空白底片，印着景点名和区。
 * - 按组显示，每组 5 格；滚轮一格一格走，换组用网页上的黄铜按钮（StageCommand "page"）。
 * - 点一格或看片器：镜头推近，然后让网页跳到这个景点（/places/[id]）。
 *
 * 标题、刻度、按钮都是网页元素（app/places/RollsOverlay.tsx），这里只通过 emit 告诉网页选中了第几格。
 */
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { COLORS, MONO, SERIF, add, contact, damp, disposeTree, ensureFonts, makeCanister, makeTable, materials, pad, sh, tex } from "../common";
import { rollLabel } from "../data";
import type { RollsData, RollsFrame } from "../data";
import { addLights, applyShadowQuality } from "../engine";
import type { Act, ActEnv } from "../engine";
import type { StageCommand, StageRequest } from "../types";

const G = 5;
const CAN_X = -7.3;
const PITCH = 2.5,
  FW = 2.16,
  FH = 1.46,
  STRIP_H = 2.5,
  STRIP_Y = 1.9,
  STRIP_Z = -0.25,
  SLOT0 = -3.5;
const TILE = PITCH,
  STRIP_W = 50;
const STRIP_LEFT = CAN_X + 1.2;
const fz = (x: number) => STRIP_Z + 0.09 * Math.sin(x * 0.42 + 0.8);
const fry = (x: number) => -Math.atan(0.09 * 0.42 * Math.cos(x * 0.42 + 0.8));

/** 照片按比例裁成铺满（像 CSS 的 object-fit: cover） */
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
  t.needsUpdate = true;
}

/** 没有照片时：没曝光的空白底片，印着景点名和区（设计规范第 15 节第 3 条） */
function blankNegative(f: RollsFrame, square = false) {
  const w = 640,
    h = square ? 640 : Math.round((640 * FH) / FW);
  return tex(w, h, (g) => {
    const bg = g.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, "#5a2410");
    bg.addColorStop(0.5, "#6e2e14");
    bg.addColorStop(1, "#4a1d0c");
    g.fillStyle = bg;
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 2200; i++) {
      g.fillStyle = `rgba(255,190,140,${Math.random() * 0.05})`;
      g.fillRect(Math.random() * w, Math.random() * h, 1.5, 1.5);
    }
    const vg = g.createRadialGradient(w / 2, h / 2, w * 0.2, w / 2, h / 2, w * 0.7);
    vg.addColorStop(0, "rgba(0,0,0,0)");
    vg.addColorStop(1, "rgba(0,0,0,.35)");
    g.fillStyle = vg;
    g.fillRect(0, 0, w, h);
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillStyle = "rgba(240,200,150,.88)";
    let size = square ? 84 : 72;
    g.font = `600 ${size}px ${SERIF}`;
    while (g.measureText(f.name).width > w - 90 && size > 30) g.font = `600 ${(size -= 4)}px ${SERIF}`;
    g.fillText(f.name, w / 2, h / 2 - 14);
    g.font = `26px ${MONO}`;
    g.fillStyle = "rgba(240,200,150,.6)";
    g.fillText(`${f.district} · 照片待补`, w / 2, h / 2 + (square ? 70 : 52));
  });
}

export function createRolls(env: ActEnv, req0: StageRequest): Act {
  let req = req0 as StageRequest<RollsData>;
  let data = req.data;
  const frames0 = data.frames;
  const N = frames0.length;
  const GROUPS = Math.max(1, Math.ceil(N / G));
  const M = materials();

  const scene = new THREE.Scene();
  scene.environment = env.environment;
  scene.environmentIntensity = 0.1;
  const { lamp } = addLights(scene, { lampPos: [-3, 10, 10], lampTarget: [0.4, 1.4, 0], lampPower: 7.4, lampAngle: 0.66 });
  const rim = new THREE.PointLight(0xffc890, 0.3, 0, 0);
  rim.position.set(-9, 5, -2);
  scene.add(rim);

  const camera = new THREE.PerspectiveCamera(30, env.width() / env.height(), 0.1, 120);
  // 窗口越窄镜头退得越远，好装下整组胶片；竖着的平板上退到 34 为止（再远就进了雾里，画面全黑），两边会裁掉一点
  const camZ = () => Math.min(34, Math.max(21.5, 21.5 * (1.7 / (env.width() / env.height()))));
  const fitFog = () => {
    const f = scene.fog as THREE.Fog;
    f.near = camZ() + 4.5;
    f.far = camZ() + 28.5;
  };
  const CAM = new THREE.Vector3(0.2, 4.1, camZ()),
    LOOK = new THREE.Vector3(0.2, 2.75, 0);
  const camPos = CAM.clone(),
    camLook = LOOK.clone(),
    lookNow = LOOK.clone();
  camera.position.copy(CAM);
  fitFog();

  scene.add(makeTable());
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(70, 24), new THREE.MeshStandardMaterial({ color: 0x120504, roughness: 1 }));
  wall.position.set(0, 12, -5.5);
  wall.receiveShadow = true;
  scene.add(wall);

  /* ---------- 胶卷罐 ---------- */
  const canParts = makeCanister(data.district ? data.district.replace(/区$/, "") : "武汉", rollLabel(data));
  const can = canParts.group;
  can.position.set(CAN_X, 0, 0.35);
  scene.add(can);
  add(can, new THREE.BoxGeometry(0.34, 2.8, 0.5), M.felt, 1.2, 1.9, -0.35); // 出片口的绒布

  /* ---------- 胶片 ---------- */
  const stripTex = tex(512, 512, (g, w, h) => {
    g.fillStyle = "#a84a24";
    g.fillRect(0, 0, w, h);
    const sheen = g.createLinearGradient(0, 0, 0, h);
    sheen.addColorStop(0, "rgba(255,170,110,.22)");
    sheen.addColorStop(0.5, "rgba(0,0,0,0)");
    sheen.addColorStop(1, "rgba(0,0,0,.25)");
    g.fillStyle = sheen;
    g.fillRect(0, 0, w, h);
    g.fillStyle = "#1c0705";
    for (let x = 17; x < w; x += 64)
      for (const y of [30, h - 72]) {
        g.beginPath();
        g.roundRect(x, y, 30, 42, 6);
        g.fill();
      }
    g.fillStyle = "#2a0c08";
    g.beginPath();
    g.roundRect(w * 0.5 - (FW / TILE) * w * 0.5 - 6, h * 0.5 - (FH / STRIP_H) * h * 0.5 - 6, (FW / TILE) * w + 12, (FH / STRIP_H) * h + 12, 6);
    g.fill();
    g.fillStyle = "rgba(240,200,150,.75)";
    g.font = `18px ${MONO}`;
    g.fillText("WUHAN MEMORY", 150, 98);
    g.fillText("▸", w - 60, h - 82);
  });
  stripTex.wrapS = THREE.RepeatWrapping;
  stripTex.repeat.set(STRIP_W / TILE, 1);
  const stripGeo = new THREE.PlaneGeometry(STRIP_W, STRIP_H, 200, 1);
  {
    const p = stripGeo.attributes.position;
    for (let i = 0; i < p.count; i++) p.setZ(i, fz(p.getX(i) + STRIP_LEFT + STRIP_W / 2) - STRIP_Z);
    stripGeo.computeVertexNormals();
  }
  const strip = sh(
    new THREE.Mesh(
      stripGeo,
      new THREE.MeshPhysicalMaterial({ map: stripTex, roughness: 0.28, metalness: 0, clearcoat: 0.8, clearcoatRoughness: 0.2, side: THREE.DoubleSide, emissive: 0x3a1408, emissiveIntensity: 0.22 })
    )
  );
  strip.position.set(STRIP_LEFT + STRIP_W / 2, STRIP_Y, STRIP_Z);
  scene.add(strip);
  contact(scene, 44, 1.6).position.set(STRIP_LEFT + 20, 0.012, STRIP_Z);

  /* ---------- 每一格 ---------- */
  interface Slot {
    f: RollsFrame;
    i: number;
    mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshStandardMaterial>;
    num: THREE.Mesh;
    lift: number;
    /** 格里的贴图（照片或空白底片）和看片器里的方形版本 */
    frameTex: THREE.Texture;
    squareTex: THREE.Texture;
    photo: "none" | "loading" | "done";
  }
  const owned: THREE.Texture[] = [];
  const slots: Slot[] = frames0.map((f, i) => {
    const frameTex = blankNegative(f);
    const squareTex = blankNegative(f, true);
    owned.push(frameTex, squareTex);
    const mat = new THREE.MeshStandardMaterial({ map: frameTex, emissiveMap: frameTex, emissive: 0xffffff, emissiveIntensity: 0.2, roughness: 0.4, color: 0xff7755 });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(FW, FH), mat);
    mesh.userData.slot = i;
    scene.add(mesh);
    const t = tex(128, 48, (g, w) => {
      g.fillStyle = "rgba(240,200,150,.85)";
      g.font = `30px ${MONO}`;
      g.textAlign = "center";
      g.fillText(pad(f.no), w / 2, 34);
    });
    owned.push(t);
    const num = new THREE.Mesh(new THREE.PlaneGeometry(0.42, 0.16), new THREE.MeshBasicMaterial({ map: t, transparent: true }));
    scene.add(num);
    return { f, i, mesh, num, lift: 0, frameTex, squareTex, photo: f.photoUrl ? "none" : "done" };
  });

  /* ---------- 看片器 ---------- */
  const viewer = new THREE.Group();
  viewer.position.set(SLOT0, 0, 0.75);
  scene.add(viewer);
  const viewerAO = contact(viewer, 5.6, 3.6);
  add(viewer, new RoundedBoxGeometry(3.7, 0.26, 1.9, 4, 0.08), M.greenDark, 0, 0.13, 0);
  const box = add(viewer, new RoundedBoxGeometry(3.4, 3.7, 1.5, 10, 0.3), M.green, 0, 2.1, 0);
  add(viewer, new RoundedBoxGeometry(2.7, 0.07, 1.0, 2, 0.03), M.brass, 0, 3.96, 0);
  add(viewer, new THREE.TorusGeometry(0.5, 0.06, 16, 48, Math.PI), M.brass, 0, 3.98, 0);
  for (const sx of [-1, 1]) add(viewer, new THREE.BoxGeometry(0.1, 2.7, 0.5), M.felt, sx * 1.71, STRIP_Y + 0.02, -0.9);
  const frameOuter = add(viewer, new RoundedBoxGeometry(2.62, 2.62, 0.2, 6, 0.09), M.brass, 0, 2.42, 0.72);
  add(viewer, new RoundedBoxGeometry(2.3, 2.3, 0.06, 4, 0.05), M.brassDark, 0, 2.42, 0.81);
  const recess = new THREE.Mesh(new THREE.PlaneGeometry(2.16, 2.16), M.black);
  recess.position.set(0, 2.42, 0.842);
  viewer.add(recess);
  const screenMat = new THREE.MeshStandardMaterial({ color: 0x000000, emissiveMap: slots[0]?.squareTex ?? null, emissive: 0xffffff, emissiveIntensity: 1, roughness: 0.9 });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(2.0, 2.0), screenMat);
  screen.position.set(0, 2.42, 0.846);
  viewer.add(screen);
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(2.16, 2.16), M.glass);
  glass.position.set(0, 2.42, 0.86);
  viewer.add(glass);
  for (const sx of [-1, 1])
    for (const sy of [-1, 1]) {
      const s = add(viewer, new THREE.CylinderGeometry(0.055, 0.055, 0.05, 16), M.brassDark, sx * 1.2, 2.42 + sy * 1.2, 0.83);
      s.rotation.x = Math.PI / 2;
    }
  const plateTex = tex(640, 128, () => {});
  owned.push(plateTex);
  function drawPlate(name: string) {
    const c = plateTex.image as HTMLCanvasElement,
      g = c.getContext("2d")!;
    const bg = g.createLinearGradient(0, 0, 0, c.height);
    bg.addColorStop(0, "#e2c27e");
    bg.addColorStop(0.5, "#c9a45c");
    bg.addColorStop(1, "#a8833f");
    g.fillStyle = bg;
    g.fillRect(0, 0, c.width, c.height);
    g.strokeStyle = "#6e5326";
    g.lineWidth = 4;
    g.strokeRect(8, 8, c.width - 16, c.height - 16);
    g.fillStyle = "#6e5326";
    for (const x of [22, c.width - 22]) {
      g.beginPath();
      g.arc(x, c.height / 2, 6, 0, 7);
      g.fill();
    }
    g.fillStyle = COLORS.ink;
    g.textAlign = "center";
    g.textBaseline = "middle";
    let size = 54;
    g.font = `600 ${size}px ${SERIF}`;
    while (g.measureText(name).width > c.width - 110 && size > 26) g.font = `600 ${(size -= 2)}px ${SERIF}`;
    g.fillText(name, c.width / 2, c.height / 2 + 3);
    plateTex.needsUpdate = true;
  }
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 0.38), new THREE.MeshStandardMaterial({ map: plateTex, roughness: 0.32, metalness: 0.85, envMapIntensity: 1.6 }));
  plate.position.set(0, 0.72, 0.752);
  viewer.add(plate);
  const arm = add(viewer, new THREE.CylinderGeometry(0.06, 0.06, 0.5, 16), M.brassDark, 1.92, 3.0, 0.1);
  arm.rotation.z = Math.PI / 2;
  const knob = add(viewer, new THREE.SphereGeometry(0.27, 48, 32), M.cherry, 2.2, 3.0, 0.1);
  const viewerParts = [box, frameOuter, screen, glass];
  let viewerHover = 0;

  /* ---------- 照片：当前组和前后一组先取，其余走到附近再取 ---------- */
  const loader = new THREE.TextureLoader();
  function loadPhoto(s: Slot): Promise<void> {
    if (s.photo !== "none" || !s.f.photoUrl) return Promise.resolve();
    s.photo = "loading";
    return new Promise((resolve) => {
      const timer = window.setTimeout(resolve, 3000); // 太慢就先用空白底片，照片到了再换
      loader.load(
        s.f.photoUrl!,
        (t) => {
          window.clearTimeout(timer);
          t.colorSpace = THREE.SRGBColorSpace;
          t.anisotropy = env.renderer.capabilities.getMaxAnisotropy();
          coverCrop(t, FW / FH);
          const sq = t.clone();
          coverCrop(sq, 1);
          owned.push(t, sq);
          s.frameTex = t;
          s.squareTex = sq;
          s.mesh.material.map = t;
          s.mesh.material.emissiveMap = t;
          s.mesh.material.needsUpdate = true;
          if (s.i === sel) {
            screenMat.emissiveMap = sq;
            screenMat.needsUpdate = true;
            screenMat.emissiveIntensity = 0.04; // 像显影一样亮起来
          }
          s.photo = "done";
          resolve();
        },
        undefined,
        () => {
          window.clearTimeout(timer);
          s.photo = "done"; // 取不到就一直用空白底片
          resolve();
        }
      );
    });
  }
  function loadAround(g: number) {
    for (const s of slots) if (Math.abs(Math.floor(s.i / G) - g) <= 1) void loadPhoto(s);
  }

  /* ---------- 状态 ---------- */
  const startAt = Math.max(0, slots.findIndex((s) => s.f.id === data.at));
  let sel = -1,
    group = 0,
    filmX = 0,
    entering = false,
    focused = false,
    wheelAcc = 0,
    wheelLock = 0,
    lampFollow = true,
    t = 0;
  let hovered: Slot | "viewer" | null = null;
  const ray = new THREE.Raycaster();
  const filmTarget = () => group * G * PITCH;
  const slotX = (i: number) => SLOT0 + i * PITCH - filmX;

  function emit() {
    env.emit({ kind: "rolls", sel, group, groups: GROUPS, n: N, entering, id: slots[sel]?.f.id ?? null });
  }
  function select(i: number) {
    if (!N) return;
    i = THREE.MathUtils.clamp(i, 0, N - 1);
    const g = Math.floor(i / G);
    if (i === sel && g === group) return;
    const changedGroup = g !== group || sel < 0;
    group = g;
    if (i !== sel) {
      sel = i;
      const s = slots[i];
      screenMat.emissiveMap = s.squareTex;
      screenMat.needsUpdate = true;
      screenMat.emissiveIntensity = 0.04;
      drawPlate(s.f.name);
    }
    if (changedGroup) loadAround(group);
    emit();
  }
  function page(dir: number) {
    const g2 = THREE.MathUtils.clamp(group + dir, 0, GROUPS - 1);
    if (g2 !== group) select(Math.min(N - 1, g2 * G + (sel % G)));
  }
  function enter(i = sel) {
    if (entering || !slots[i]) return;
    select(i);
    entering = true;
    emit();
    const href = `/places/${slots[i].f.id}`;
    window.setTimeout(() => {
      if (entering && env.active()) env.navigate(href);
    }, 1300);
  }

  /* ---------- 鼠标和滚轮 ---------- */
  const onWheel = (e: WheelEvent) => {
    if (!env.active() || entering) return;
    const now = performance.now();
    if (now < wheelLock) return;
    wheelAcc += e.deltaY + e.deltaX;
    if (Math.abs(wheelAcc) > 50) {
      select(sel + Math.sign(wheelAcc));
      wheelAcc = 0;
      wheelLock = now + 260;
    }
  };
  const onClick = (e: MouseEvent) => {
    if (!env.active() || entering || e.button !== 0) return;
    // 只认画布上的点击，网页上的按钮、链接自己处理
    if (e.target !== env.renderer.domElement) return;
    if (!hovered) return;
    enter(hovered === "viewer" ? sel : hovered.i);
  };
  window.addEventListener("wheel", onWheel, { passive: true });
  window.addEventListener("click", onClick);

  /* ---------- 键盘聚焦时的黄铜框：围着看片器的画框 ---------- */
  const corner = new THREE.Vector3();
  function ringRect() {
    let x0 = Infinity,
      y0 = Infinity,
      x1 = -Infinity,
      y1 = -Infinity;
    for (const sx of [-1.31, 1.31])
      for (const sy of [-1.31, 1.31]) {
        corner.set(sx, 2.42 + sy, 0.82);
        viewer.localToWorld(corner).project(camera);
        const px = (corner.x * 0.5 + 0.5) * env.width(),
          py = (-corner.y * 0.5 + 0.5) * env.height();
        x0 = Math.min(x0, px);
        y0 = Math.min(y0, py);
        x1 = Math.max(x1, px);
        y1 = Math.max(y1, py);
      }
    return { x: x0 - 6, y: y0 - 6, w: x1 - x0 + 12, h: y1 - y0 + 12 };
  }

  /* ---------- 每一帧 ---------- */
  function step(dt: number) {
    t += dt;
    const prevFilm = filmX;
    filmX = damp(filmX, filmTarget(), 4.2, dt);
    const speed = Math.abs(filmX - prevFilm) / Math.max(dt, 0.001);

    // 鼠标指着当前组的哪一格，看片器就滑到哪一格
    hovered = null;
    if (!entering && env.ndc.x < 2) {
      ray.setFromCamera(env.ndc, camera);
      const hit = ray.intersectObjects([...slots.filter((s) => s.mesh.visible).map((s) => s.mesh), ...viewerParts], false)[0];
      if (hit) hovered = hit.object.userData.slot !== undefined ? slots[hit.object.userData.slot as number] : "viewer";
      if (hovered && hovered !== "viewer" && Math.floor(hovered.i / G) === group && speed < 1.5) select(hovered.i);
    }
    env.renderer.domElement.style.cursor = hovered ? "pointer" : "default";

    for (const s of slots) {
      const x = slotX(s.i);
      s.mesh.visible = x > CAN_X + 1.5 && x < 16;
      s.num.visible = s.mesh.visible;
      const nextGroupHover = hovered === s && Math.floor(s.i / G) !== group;
      s.lift = damp(s.lift, nextGroupHover ? 1 : 0, 9, dt);
      const L = s.lift,
        isSel = s.i === sel;
      s.mesh.position.set(x, STRIP_Y + L * 0.1, fz(x) + 0.012 + L * 0.4);
      s.mesh.rotation.y = fry(x);
      s.mesh.scale.setScalar(1 + L * 0.12);
      const lit = Math.max(L, isSel ? 1 : 0); // 没选中的罩一层暗房红
      s.mesh.material.color.setRGB(1, 0.47 + lit * 0.53, 0.33 + lit * 0.67);
      s.mesh.material.emissiveIntensity = 0.2 + L * 0.5;
      s.num.position.set(x - FW / 2 + 0.24, STRIP_Y - FH / 2 - 0.16, fz(x) + 0.014);
      s.num.rotation.y = fry(x);
    }
    stripTex.offset.x = (filmX - (SLOT0 - STRIP_LEFT)) / TILE + 0.5;

    // 看片器滑动、带一点惯性倾斜，旋钮和罐轴跟着转
    const vx = SLOT0 + Math.max(0, sel) * PITCH - filmTarget();
    const prevVx = viewer.position.x;
    viewer.position.x = dt === 0 ? vx : damp(viewer.position.x, vx, 6.5, dt);
    const vSpeed = (viewer.position.x - prevVx) / Math.max(dt, 0.001);
    viewerHover = damp(viewerHover, hovered === "viewer" ? 1 : 0, 8, dt);
    const H = viewerHover;
    viewer.rotation.z = THREE.MathUtils.clamp(-vSpeed * 0.004, -0.04, 0.04);
    viewer.rotation.x = -H * 0.025;
    viewer.position.z = 0.75 + H * 0.18;
    viewerAO.material.opacity = 1 - H * 0.2;
    screen.scale.setScalar(1 + H * 0.03);
    screenMat.emissiveIntensity = damp(screenMat.emissiveIntensity, 1.0, 3.2, dt);
    knob.rotation.x += vSpeed * dt * 0.8;
    arm.rotation.x += vSpeed * dt * 0.8;
    canParts.spool.rotation.y = canParts.spoolTop.rotation.y = -filmX * 0.9;

    // 镜头：平时轻微跟着鼠标（G3）；点了以后推近到看片器
    const m = env.ndc.x < 2 ? env.mouse : { x: 0, y: 0 };
    if (entering) {
      camPos.set(viewer.position.x, 2.6, 9.6);
      camLook.set(viewer.position.x, 2.2, 0.8);
    } else {
      camPos.set(CAM.x + m.x * 0.6, CAM.y - m.y * 0.32, CAM.z);
      camLook.copy(LOOK);
    }
    const cs = entering ? 2.4 : 3.2;
    if (dt === 0) {
      camera.position.copy(camPos);
      lookNow.copy(camLook);
    } else {
      camera.position.set(damp(camera.position.x, camPos.x, cs, dt), damp(camera.position.y, camPos.y, cs, dt), damp(camera.position.z, camPos.z, cs, dt));
      lookNow.set(damp(lookNow.x, camLook.x, cs, dt), damp(lookNow.y, camLook.y, cs, dt), damp(lookNow.z, camLook.z, cs, dt));
    }
    camera.lookAt(lookNow);
    // 灯光跟着鼠标（G2），降级后不跟
    lamp.position.x = damp(lamp.position.x, -3 + (lampFollow ? m.x * 2.4 : 0), 2, dt);

    env.ring(focused && !entering ? ringRect() : null);
  }

  /* ---------- 准备：字体加载好再画铭牌和空白底片，当前组的照片取到（或超时） ---------- */
  const ready = (async () => {
    await ensureFonts(frames0.map((f) => f.name + f.district).join("") + "照片待补WUHAN MEMORY0123456789·EXP");
    // 字体到了以后重画一遍用到字的贴图
    for (const s of slots) {
      if (s.photo === "done" && s.f.photoUrl) continue;
      const a = blankNegative(s.f),
        b = blankNegative(s.f, true);
      s.frameTex.dispose();
      s.squareTex.dispose();
      s.frameTex = a;
      s.squareTex = b;
      owned.push(a, b);
      s.mesh.material.map = a;
      s.mesh.material.emissiveMap = a;
      s.mesh.material.needsUpdate = true;
    }
    sel = -1;
    select(startAt);
    filmX = filmTarget();
    await Promise.all(slots.filter((s) => Math.floor(s.i / G) === group).map(loadPhoto));
  })();
  // 准备好以后，其余照片一张一张在后台取
  void ready.then(async () => {
    for (const s of slots) await loadPhoto(s);
  });

  return {
    scene,
    camera,
    ready,
    update(next) {
      if (next.key !== req.key) return false;
      req = next as StageRequest<RollsData>;
      data = req.data;
      // 从晾片幕回来：停在刚才那一格
      entering = false;
      const i = slots.findIndex((s) => s.f.id === data.at);
      if (i >= 0) select(i);
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
    command(cmd: StageCommand) {
      switch (cmd.type) {
        case "page":
          if (!entering) page(Number(cmd.dir) || 0);
          break;
        case "step":
          if (!entering) select(sel + (Number(cmd.dir) || 0));
          break;
        case "focus": {
          const i = slots.findIndex((s) => s.f.id === cmd.id);
          if (i >= 0) {
            focused = true;
            if (!entering) select(i);
          }
          break;
        }
        case "blur":
          focused = false;
          break;
        case "enter": {
          const i = cmd.id ? slots.findIndex((s) => s.f.id === cmd.id) : sel;
          if (i >= 0) enter(i);
          break;
        }
      }
    },
    dispose() {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("click", onClick);
      env.ring(null);
      for (const tx of owned) tx.dispose();
      disposeTree(scene);
    }
  };
}
