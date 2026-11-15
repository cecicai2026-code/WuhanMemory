/**
 * 第三幕：纸页（/places/[id]/[主题]，设计规范第 8.3 节）。从样片 docs/design/prototypes/darkroom-page.html 改写。
 *
 * 和样片不同的一点（设计规范第 15 节第 4 条）：信纸上的内容是真实的网页文字，叠在立体桌面上，
 * 所以这里只画桌面和纸旁边的小物件：和主题有关的一张贴纸、一支钢笔、右边露出的一本书（点一下翻到下一个主题）。
 * 物件按屏幕上的位置摆（纸左边、右下、右边），窗口宽窄不同时都在纸的两侧。
 *
 * 贴纸：景点概览是相机，游玩建议是地铁票，景点图册是一小段胶片，周边美食是一碗面。线描加平涂，带一圈白边，
 * 不印任何数字和事实。
 */
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { COLORS, MONO, SERIF, add, contact, damp, disposeTree, ensureFonts, makeTable, materials, pad, tex } from "../common";
import type { SheetData } from "../data";
import { addLights, applyShadowQuality } from "../engine";
import type { Act, ActEnv } from "../engine";
import type { StageRequest } from "../types";

interface Thing {
  g: THREE.Group;
  label: string;
  hv: number;
  drop: number;
  flip: number;
  /** 在屏幕上的位置（-1 到 1），窗口变了按它重新摆 */
  at: [number, number];
  rotY: number;
  /** 放在桌上时的高度 */
  y0: number;
  onClick?: () => void;
}

const outline = (g: CanvasRenderingContext2D, path: () => void) => {
  g.strokeStyle = "#f4ecd8";
  g.lineWidth = 26;
  path();
  g.stroke();
  g.fillStyle = "#f4ecd8";
  path();
  g.fill();
};

/** 四张贴纸，顺序和四个主题一致 */
const STICKERS: Array<{ w: number; h: number; label: { zh: string; en: string }; draw: (g: CanvasRenderingContext2D, w: number, h: number, en: boolean) => void }> = [
  {
    w: 2.4,
    h: 1.7,
    label: { zh: "相机贴纸", en: "Camera sticker" },
    draw: (g, w, h) => {
      const body = () => {
        g.beginPath();
        g.roundRect(40, 90, w - 80, h - 130, 26);
      };
      outline(g, body);
      g.fillStyle = "#d9b867";
      body();
      g.fill();
      g.strokeStyle = COLORS.ink;
      g.lineWidth = 6;
      body();
      g.stroke();
      g.fillStyle = "#16332a";
      g.fillRect(40, 150, w - 80, 70);
      g.strokeRect(40, 150, w - 80, 70);
      g.fillStyle = "#d9b867";
      g.beginPath();
      g.roundRect(150, 56, 120, 50, 10);
      g.fill();
      g.stroke();
      for (const [r, c] of [
        [92, COLORS.ink],
        [70, "#8a6830"],
        [46, "#16332a"],
        [20, "#0b0b0c"]
      ] as const) {
        g.fillStyle = c;
        g.beginPath();
        g.arc(w / 2, h / 2 + 22, r, 0, 7);
        g.fill();
        g.stroke();
      }
      g.fillStyle = "#c8281e";
      g.beginPath();
      g.roundRect(w - 150, 108, 70, 34, 6);
      g.fill();
      g.stroke();
    }
  },
  {
    w: 2.6,
    h: 1.25,
    label: { zh: "地铁票贴纸", en: "Metro ticket sticker" },
    draw: (g, w, h, en) => {
      const body = () => {
        g.beginPath();
        g.roundRect(30, 30, w - 60, h - 60, 18);
      };
      outline(g, body);
      g.fillStyle = COLORS.paper;
      body();
      g.fill();
      g.strokeStyle = COLORS.ink;
      g.lineWidth = 5;
      body();
      g.stroke();
      g.fillStyle = "#16332a";
      g.fillRect(30, 60, w - 60, 46);
      g.fillStyle = COLORS.ink;
      g.font = `600 ${en ? 44 : 52}px ${SERIF}`;
      g.fillText(en ? "Metro · Single" : "地铁 · 单程票", 60, 170);
      g.fillStyle = COLORS.oxblood;
      g.font = `22px ${MONO}`;
      g.fillText("WUHAN MEMORY", 62, 208);
      g.setLineDash([8, 10]);
      g.beginPath();
      g.moveTo(w - 130, 40);
      g.lineTo(w - 130, h - 40);
      g.stroke();
      g.setLineDash([]);
    }
  },
  {
    w: 2.3,
    h: 1.6,
    label: { zh: "一段胶片贴纸", en: "Film strip sticker" },
    draw: (g, w, h) => {
      const body = () => {
        g.beginPath();
        g.roundRect(30, 60, w - 60, h - 120, 10);
      };
      outline(g, body);
      g.fillStyle = "#b4532a";
      body();
      g.fill();
      g.strokeStyle = COLORS.ink;
      g.lineWidth = 5;
      body();
      g.stroke();
      g.fillStyle = "#1c0705";
      for (let x = 52; x < w - 60; x += 46) {
        g.fillRect(x, 76, 24, 28);
        g.fillRect(x, h - 104, 24, 28);
      }
      g.fillStyle = "#2a0c08";
      g.fillRect(60, 122, 180, h - 244);
      g.fillRect(262, 122, 180, h - 244);
    }
  },
  {
    w: 2.2,
    h: 2.2,
    label: { zh: "一碗面贴纸", en: "Noodle bowl sticker" },
    draw: (g, w, h) => {
      const bowl = () => {
        g.beginPath();
        g.arc(w / 2, h / 2, 200, 0, 7);
      };
      outline(g, bowl);
      g.fillStyle = COLORS.paper;
      bowl();
      g.fill();
      g.strokeStyle = COLORS.ink;
      g.lineWidth = 6;
      bowl();
      g.stroke();
      g.fillStyle = "#c98a4a";
      g.beginPath();
      g.arc(w / 2, h / 2, 158, 0, 7);
      g.fill();
      g.stroke();
      g.strokeStyle = "#f4dfae";
      g.lineWidth = 9;
      for (let k = 0; k < 9; k++) {
        g.beginPath();
        g.arc(w / 2 + Math.cos(k * 1.7) * 40, h / 2 + Math.sin(k * 2.3) * 40, 60 + k * 9, k, k + 2.6);
        g.stroke();
      }
      g.fillStyle = "#16332a";
      for (let k = 0; k < 14; k++) {
        g.beginPath();
        g.arc(w / 2 + Math.cos(k * 2.4) * (30 + k * 7), h / 2 + Math.sin(k * 2.4) * (30 + k * 7), 6, 0, 7);
        g.fill();
      }
      g.strokeStyle = "#8a6830";
      g.lineWidth = 12;
      g.beginPath();
      g.moveTo(w - 40, 60);
      g.lineTo(w / 2 + 20, h / 2 - 10);
      g.moveTo(w - 16, 90);
      g.lineTo(w / 2 + 40, h / 2 + 10);
      g.stroke();
    }
  }
];

export function createSheet(env: ActEnv, req0: StageRequest): Act {
  let data = (req0 as StageRequest<SheetData>).data;
  // 场景里画的字按搭场景时的语言；换了语言 update 返回 false，引擎重搭
  const lang = data.lang;
  const en = lang === "en";
  const M = materials();
  const owned: THREE.Texture[] = [];
  const topicIndex = () => Math.max(0, data.topics.findIndex((t) => t.id === data.topic));

  const scene = new THREE.Scene();
  scene.environment = env.environment;
  scene.environmentIntensity = 0.1;
  const { lamp } = addLights(scene, { lampPos: [-5, 12, 5], lampTarget: [0.4, 0, 0.4], lampPower: 5.2, lampAngle: 0.8 });

  const camera = new THREE.PerspectiveCamera(40, env.width() / env.height(), 0.1, 120);
  const camY = () => Math.max(12.6, 12.6 * (1.6 / (env.width() / env.height())));
  const CAM = new THREE.Vector3(0.9, camY(), 4.4),
    lookNow = new THREE.Vector3(0.9, 0, 0.75);
  camera.position.copy(CAM);
  camera.lookAt(lookNow);
  const fitFog = () => {
    const f = scene.fog as THREE.Fog;
    f.near = camY() + 14;
    f.far = camY() + 38;
  };
  fitFog();
  scene.add(makeTable());

  const things: Thing[] = [];
  function thing(g: THREE.Group, label: string, at: [number, number], rotY: number, onClick?: () => void): Thing {
    const t: Thing = { g, label, hv: 0, drop: 0, flip: 0, at, rotY, y0: g.position.y, onClick };
    g.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) o.userData.thing = t;
    });
    scene.add(g);
    things.push(t);
    return t;
  }

  /* 钢笔：纸的右下 */
  const pen = new THREE.Group();
  {
    const body = add(pen, new THREE.CylinderGeometry(0.1, 0.085, 2.3, 24), M.green);
    body.rotation.z = Math.PI / 2;
    const cap = add(pen, new THREE.CylinderGeometry(0.105, 0.105, 0.9, 24), M.green, 1.5, 0, 0);
    cap.rotation.z = Math.PI / 2;
    for (const x of [1.04, 1.96]) add(pen, new THREE.CylinderGeometry(0.11, 0.11, 0.07, 24), M.brass, x, 0, 0).rotation.z = Math.PI / 2;
    add(pen, new THREE.CylinderGeometry(0.075, 0.06, 0.5, 24), M.black, -1.4, 0, 0).rotation.z = Math.PI / 2;
    add(pen, new THREE.ConeGeometry(0.06, 0.45, 16), M.brass, -1.87, 0, 0).rotation.z = Math.PI / 2;
    add(pen, new THREE.BoxGeometry(0.75, 0.025, 0.05), M.brass, 1.5, 0.115, 0);
  }
  pen.position.y = 0.14;
  thing(pen, en ? "Fountain pen" : "钢笔", [0.6, -0.55], 1.05);

  /* 贴纸：纸的左边，只显示当前主题那一张 */
  const stickers = STICKERS.map((st) => {
    const t = tex(512, Math.round((512 * st.h) / st.w), (g, cw, ch) => {
      g.lineJoin = g.lineCap = "round";
      st.draw(g, cw, ch, en);
    });
    owned.push(t);
    const g = new THREE.Group();
    const m = new THREE.Mesh(new THREE.PlaneGeometry(st.w, st.h), new THREE.MeshStandardMaterial({ map: t, transparent: true, alphaTest: 0.5, roughness: 0.6 }));
    m.rotation.x = -Math.PI / 2;
    m.position.y = 0.03;
    m.castShadow = true;
    g.add(m);
    contact(g, st.w * 1.25, st.h * 1.25).material.opacity = 0.5;
    return { th: thing(g, en ? st.label.en : st.label.zh, [-0.7, -0.2], 0.3), draw: st.draw, w: st.w, h: st.h, mesh: m };
  });

  /* 右边露出的书：封面写下一个主题，点一下翻过去 */
  const book = new THREE.Group();
  add(book, new RoundedBoxGeometry(4.4, 0.62, 6.2, 4, 0.06), new THREE.MeshPhysicalMaterial({ color: 0x5e130e, roughness: 0.55, clearcoat: 0.3 }), 0, 0.31, 0);
  add(book, new THREE.BoxGeometry(4.2, 0.5, 6.0), M.paper, 0.14, 0.31, 0);
  const bookTex = tex(512, 640, () => {});
  owned.push(bookTex);
  const nextTopic = () => data.topics[(topicIndex() + 1) % data.topics.length];
  function drawBook() {
    const g = (bookTex.image as HTMLCanvasElement).getContext("2d")!,
      w = 512,
      h = 640,
      nx = (topicIndex() + 1) % data.topics.length,
      name = data.topics[nx]?.name ?? "";
    g.fillStyle = COLORS.paper;
    g.fillRect(0, 0, w, h);
    g.strokeStyle = COLORS.ink;
    g.lineWidth = 4;
    g.strokeRect(18, 18, w - 36, h - 36);
    g.fillStyle = COLORS.oxblood;
    g.font = `26px ${MONO}`;
    g.fillText(en ? "NEXT PAGE" : "下一页", 50, 90);
    g.fillStyle = COLORS.ink;
    if (en) {
      // 英文的主题名按词分行
      g.font = `600 64px ${SERIF}`;
      name.split(" ").slice(0, 3).forEach((word, i) => g.fillText(word, 50, 230 + i * 84));
    } else {
      g.font = `600 84px ${SERIF}`;
      g.fillText(name.slice(0, 2), 50, 250);
      g.fillText(name.slice(2), 50, 350);
    }
    g.fillStyle = COLORS.soft;
    g.font = `26px ${MONO}`;
    g.fillText(`${pad(nx + 1)} / ${pad(data.topics.length)}`, 50, 560);
    bookTex.needsUpdate = true;
  }
  const cover = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 2.4), new THREE.MeshStandardMaterial({ map: bookTex, roughness: 0.85 }));
  cover.rotation.x = -Math.PI / 2;
  cover.position.set(-0.9, 0.632, -0.6);
  book.add(cover);
  contact(book, 6.2, 8).position.x = 0.2;
  const bookThing = thing(book, en ? "Next page" : "下一页", [0.92, 0.1], -0.06, () => env.navigate(`/places/${encodeURIComponent(data.id)}/${nextTopic().id}`, { curtain: false }));

  /* ---------- 按屏幕位置摆物件：从镜头往桌面打一条射线，落点就是物件的位置 ---------- */
  const ray = new THREE.Raycaster();
  const desk = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hitPoint = new THREE.Vector3();
  /** 网页告诉场景纸在屏幕上的左右边（像素），物件摆在纸两边的空白里 */
  let paperLeft = 0,
    paperRight = 0;
  function layoutFromPaper() {
    const w = env.width();
    if (!paperRight) return;
    const ndcX = (px: number) => (px / w) * 2 - 1;
    stickers.forEach((st) => (st.th.at = [ndcX(paperLeft / 2), -0.2]));
    const penThing = things.find((t) => t.g === pen);
    if (penThing) penThing.at = [ndcX(paperRight + (w - paperRight) * 0.4), -0.78];
    bookThing.at = [ndcX(paperRight + (w - paperRight) * 0.85), 0.1];
  }
  function placeAll() {
    layoutFromPaper();
    camera.position.copy(CAM);
    camera.lookAt(lookNow);
    camera.updateMatrixWorld();
    for (const t of things) {
      ray.setFromCamera(new THREE.Vector2(t.at[0], t.at[1]), camera);
      if (ray.ray.intersectPlane(desk, hitPoint)) t.g.position.set(hitPoint.x, t.g.position.y, hitPoint.z);
      t.g.rotation.y = t.rotY;
    }
    // 书只露出左边一部分：往右推
    book.position.x += 1.2;
  }

  function showTopic(first: boolean) {
    const k = topicIndex();
    stickers.forEach((s, i) => {
      s.th.g.visible = i === k;
      if (i === k && !first) s.th.drop = 1;
    });
    drawBook();
    if (!first) bookThing.flip = 1;
  }

  /* ---------- 鼠标 ---------- */
  let hovered: Thing | null = null,
    lampFollow = true;
  const onClick = (e: MouseEvent) => {
    if (!env.active() || e.button !== 0 || e.target !== env.renderer.domElement) return;
    hovered?.onClick?.();
  };
  window.addEventListener("click", onClick);
  function pick() {
    hovered = null;
    if (env.ndc.x > 2) return;
    ray.setFromCamera(env.ndc, camera);
    const meshes: THREE.Object3D[] = [];
    for (const t of things) if (t.g.visible) t.g.traverse((o) => (o as THREE.Mesh).isMesh && o.userData.thing && meshes.push(o));
    hovered = (ray.intersectObjects(meshes, false)[0]?.object.userData.thing as Thing | undefined) ?? null;
  }

  /* ---------- 每一帧 ---------- */
  const v = new THREE.Vector3();
  function step(dt: number) {
    pick();
    env.renderer.domElement.style.cursor = hovered?.onClick ? "pointer" : "default";
    for (const t of things) {
      if (!t.g.visible) continue;
      t.hv = damp(t.hv, hovered === t ? 1 : 0, 9, dt);
      t.drop = damp(t.drop, 0, 3, dt);
      t.flip = damp(t.flip, 0, 4, dt);
      const H = t.hv;
      t.g.position.y = t.y0 + H * 0.3 + t.drop * 3;
      t.g.rotation.set(H * 0.08, t.rotY * (1 - H * 0.4) + t.drop * 0.6, t.flip * 0.12);
      t.g.scale.setScalar(1 + H * 0.08);
    }
    if (hovered) {
      v.copy(hovered.g.position).project(camera);
      env.tag({
        text: hovered === bookThing ? `${en ? "Next page" : "下一页"} · ${nextTopic().name}` : hovered.label,
        x: (v.x * 0.5 + 0.5) * env.width(),
        y: (-v.y * 0.5 + 0.5) * env.height() + 54
      });
    } else env.tag(null);

    // 镜头和灯：轻微跟着鼠标（G2、G3）
    const m = env.ndc.x < 2 ? env.mouse : { x: 0, y: 0 };
    camera.position.set(damp(camera.position.x, CAM.x + m.x * 0.5, 3, dt), damp(camera.position.y, CAM.y, 3, dt), damp(camera.position.z, CAM.z + m.y * 0.4, 3, dt));
    camera.lookAt(lookNow);
    lamp.position.x = damp(lamp.position.x, -5 + (lampFollow ? m.x * 2.2 : 0), 2, dt);
  }

  const ready = (async () => {
    await ensureFonts((en ? "Metro·SingleNEXTPAGE" : "地铁单程票下一页") + data.topics.map((t) => t.name).join("") + "WUHANMEMORY0123456789/·");
    // 字体到了以后重画用到字的贴图（地铁票、书）
    const metro = stickers[1];
    const t2 = tex(512, Math.round((512 * metro.h) / metro.w), (g, cw, ch) => {
      g.lineJoin = g.lineCap = "round";
      metro.draw(g, cw, ch, en);
    });
    owned.push(t2);
    (metro.mesh.material as THREE.MeshStandardMaterial).map = t2;
    placeAll();
    showTopic(true);
    env.emit({ kind: "sheet", topic: data.topic });
  })();

  return {
    scene,
    camera,
    ready,
    update(next) {
      const d = (next as StageRequest<SheetData>).data;
      if (d.lang !== lang) return false;
      const changed = d.topic !== data.topic;
      data = d;
      showTopic(!changed);
      env.emit({ kind: "sheet", topic: data.topic });
      return true;
    },
    step,
    resize(w, h) {
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      CAM.y = camY();
      fitFog();
      placeAll();
    },
    setQuality(level) {
      applyShadowQuality(lamp, level);
      lampFollow = level === 0;
    },
    command(cmd) {
      if (cmd.type === "layout") {
        paperLeft = Number(cmd.left) || 0;
        paperRight = Number(cmd.right) || 0;
        placeAll();
      }
    },
    dispose() {
      window.removeEventListener("click", onClick);
      for (const t of owned) t.dispose();
      disposeTree(scene);
    }
  };
}
