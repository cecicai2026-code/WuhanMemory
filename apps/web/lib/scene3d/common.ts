/**
 * 立体场景共用的部分：贴图、木桌、材质、接触阴影、胶卷罐。
 * 从设计样片 docs/design/prototypes/common.js 改写成 TypeScript，参数（颜色、尺寸、光）照搬，
 * 保证和 Cecilia 确认过的样子一致。去掉了样片里的示意照片和示例景点清单（规范第 15 节）。
 *
 * 贴图都是用画布现画的，不下载图片。画了字的贴图要先等字体加载好（ensureFonts）。
 */
import * as THREE from "three";

export const pad = (n: number) => String(n).padStart(2, "0");
/** 指数阻尼：每帧向目标靠近一点，帧率不同时速度一样 */
export const damp = (cur: number, to: number, speed: number, dt: number) => cur + (to - cur) * (1 - Math.exp(-speed * dt));

/** 画在贴图上的字用项目里自托管的字体（app/layout.tsx），不用 Google Fonts */
export const SERIF = '"Noto Serif SC","Songti SC","STSong",serif';
export const MONO = '"IBM Plex Mono","Noto Sans SC",Menlo,monospace';
export const TYPE = '"Courier Prime","LXGW WenKai","Kaiti SC",serif';
export const NOTE = '"Caveat","Kaiti SC","STKaiti",cursive';

export const COLORS = {
  ink: "#2a2420",
  soft: "#6b5e4c",
  oxblood: "#a8321f",
  pencil: "#44607a",
  green: "#2f6b4f",
  paper: "#e9dfc6",
  brass: "#c9a45c"
};

/**
 * 画在贴图上的字要先把字体（中文按字集拆成了很多小文件）加载好，不然画出来是系统字体。
 * text 传要画的字，浏览器只下载用得到的那几个字集。
 */
export async function ensureFonts(text: string): Promise<void> {
  const fonts = [`600 40px "Noto Serif SC"`, `400 40px "IBM Plex Mono"`, `400 40px "Noto Sans SC"`, `400 40px "Courier Prime"`, `700 40px "Courier Prime"`, `400 40px "LXGW WenKai"`];
  const sample = text || "武汉";
  await Promise.all(fonts.map((f) => document.fonts.load(f, sample).catch(() => [])));
}

/* 确定的伪随机数：每次画出来的木纹一样 */
let seed = 7;
export const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
export const reseed = (s: number) => {
  seed = s;
};

let maxAniso = 8;
export function setMaxAnisotropy(v: number) {
  maxAniso = v;
}

/** 用画布画一张贴图 */
export function tex(w: number, h: number, draw: (g: CanvasRenderingContext2D, w: number, h: number) => void, srgb = true): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  draw(c.getContext("2d")!, w, h);
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = maxAniso;
  return t;
}

/* ---------- 木桌 ---------- */
function grainLines(g: CanvasRenderingContext2D, w: number, h: number, dark: (a: number) => string, light: (a: number) => string, n: number) {
  for (let i = 0; i < n; i++) {
    const y = rnd() * h,
      len = 200 + rnd() * 1100,
      x = rnd() * w - 300;
    g.strokeStyle = rnd() > 0.45 ? dark(rnd()) : light(rnd());
    g.lineWidth = 0.5 + rnd() * 2.4;
    g.beginPath();
    g.moveTo(x, y);
    g.bezierCurveTo(x + len * 0.3, y + (rnd() - 0.5) * 10, x + len * 0.6, y + (rnd() - 0.5) * 10, x + len, y + (rnd() - 0.5) * 8);
    g.stroke();
  }
}

let woodCache: { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } | null = null;
/** 木纹贴图很大（2048），画一次就留着，几幕共用 */
function woodTextures() {
  if (woodCache) return woodCache;
  reseed(7);
  const map = tex(2048, 2048, (g, w, h) => {
    g.fillStyle = "#6a2015";
    g.fillRect(0, 0, w, h);
    for (let p = 0; p < 6; p++) {
      g.fillStyle = `rgba(${p % 2 ? 40 : 120},${p % 2 ? 8 : 40},${p % 2 ? 4 : 24},.10)`;
      g.fillRect(0, (h / 6) * p, w, h / 6);
    }
    grainLines(g, w, h, (a) => `rgba(20,4,2,${0.05 + a * 0.16})`, (a) => `rgba(214,96,60,${0.02 + a * 0.07})`, 5200);
    for (let k = 0; k < 14; k++) {
      const x = rnd() * w,
        y = rnd() * h,
        r = 14 + rnd() * 30;
      for (let q = 0; q < 7; q++) {
        g.strokeStyle = `rgba(18,4,2,${0.1 + q * 0.02})`;
        g.lineWidth = 1.2;
        g.beginPath();
        g.ellipse(x, y, r * (1 + q * 0.5), r * 0.32 * (1 + q * 0.45), 0, 0, 7);
        g.stroke();
      }
    }
    for (let p = 1; p < 6; p++) {
      g.fillStyle = "rgba(10,2,1,.7)";
      g.fillRect(0, (h / 6) * p - 1, w, 3);
      g.fillStyle = "rgba(255,150,110,.08)";
      g.fillRect(0, (h / 6) * p + 2, w, 1);
    }
  });
  reseed(7);
  const bump = tex(
    2048,
    2048,
    (g, w, h) => {
      g.fillStyle = "#808080";
      g.fillRect(0, 0, w, h);
      grainLines(g, w, h, (a) => `rgba(0,0,0,${0.1 + a * 0.25})`, (a) => `rgba(255,255,255,${0.05 + a * 0.12})`, 5200);
      for (let p = 1; p < 6; p++) {
        g.fillStyle = "#000";
        g.fillRect(0, (h / 6) * p - 1, w, 4);
      }
    },
    false
  );
  for (const t of [map, bump]) {
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(2.4, 2.4);
  }
  woodCache = { map, bump };
  return woodCache;
}

export function makeTable(): THREE.Mesh {
  const { map, bump } = woodTextures();
  const table = new THREE.Mesh(
    new THREE.PlaneGeometry(70, 44),
    new THREE.MeshPhysicalMaterial({ map, bumpMap: bump, bumpScale: 0.9, roughness: 0.42, clearcoat: 0.35, clearcoatRoughness: 0.35 })
  );
  table.rotation.x = -Math.PI / 2;
  table.receiveShadow = true;
  return table;
}

/* ---------- 材质 ---------- */
export interface Materials {
  green: THREE.MeshPhysicalMaterial;
  greenDark: THREE.MeshPhysicalMaterial;
  brass: THREE.MeshStandardMaterial;
  brassDark: THREE.MeshStandardMaterial;
  steel: THREE.MeshStandardMaterial;
  black: THREE.MeshStandardMaterial;
  felt: THREE.MeshStandardMaterial;
  paper: THREE.MeshStandardMaterial;
  wood: THREE.MeshStandardMaterial;
  bamboo: THREE.MeshStandardMaterial;
  cherry: THREE.MeshPhysicalMaterial;
  glass: THREE.MeshPhysicalMaterial;
}
let matCache: Materials | null = null;
export function materials(): Materials {
  if (matCache) return matCache;
  reseed(3);
  const brushed = tex(
    512,
    512,
    (g, w, h) => {
      g.fillStyle = "#6a6a6a";
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < 3000; i++) {
        const v = rnd() > 0.5 ? 255 : 0;
        g.fillStyle = `rgba(${v},${v},${v},.06)`;
        g.fillRect(0, rnd() * h, w, 1);
      }
    },
    false
  );
  brushed.wrapS = brushed.wrapT = THREE.RepeatWrapping;
  matCache = {
    green: new THREE.MeshPhysicalMaterial({ color: 0x143026, roughness: 0.36, metalness: 0.1, clearcoat: 0.7, clearcoatRoughness: 0.28 }),
    greenDark: new THREE.MeshPhysicalMaterial({ color: 0x0e2019, roughness: 0.45, clearcoat: 0.4, clearcoatRoughness: 0.4 }),
    brass: new THREE.MeshStandardMaterial({ color: 0xd0a85c, roughness: 0.26, metalness: 1, roughnessMap: brushed, envMapIntensity: 2.2 }),
    brassDark: new THREE.MeshStandardMaterial({ color: 0x8a6830, roughness: 0.36, metalness: 1, roughnessMap: brushed, envMapIntensity: 1.8 }),
    steel: new THREE.MeshStandardMaterial({ color: 0xb9b4aa, roughness: 0.34, metalness: 1, roughnessMap: brushed, envMapIntensity: 2.4 }),
    black: new THREE.MeshStandardMaterial({ color: 0x100d0b, roughness: 0.75 }),
    felt: new THREE.MeshStandardMaterial({ color: 0x050404, roughness: 1 }),
    paper: new THREE.MeshStandardMaterial({ color: 0xe9dfc6, roughness: 0.85 }),
    wood: new THREE.MeshStandardMaterial({ color: 0xb8794a, roughness: 0.7 }),
    bamboo: new THREE.MeshStandardMaterial({ color: 0xc9a06a, roughness: 0.55 }),
    cherry: new THREE.MeshPhysicalMaterial({ color: 0xc4201a, roughness: 0.12, clearcoat: 1, clearcoatRoughness: 0.05, envMapIntensity: 2.5 }),
    glass: new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.04, metalness: 0, transparent: true, opacity: 0.05, envMapIntensity: 6 })
  };
  return matCache;
}

export const sh = <T extends THREE.Object3D>(m: T): T => {
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
};
export const add = (parent: THREE.Object3D, geo: THREE.BufferGeometry, mat: THREE.Material | THREE.Material[], x = 0, y = 0, z = 0): THREE.Mesh => {
  const m = sh(new THREE.Mesh(geo, mat));
  m.position.set(x, y, z);
  parent.add(m);
  return m;
};

/* 物件底下的接触阴影，让它们"坐"在桌上 */
let aoTex: THREE.CanvasTexture | null = null;
export function contact(parent: THREE.Object3D, w: number, d: number): THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial> {
  aoTex ??= tex(256, 256, (g, s) => {
    const r = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    r.addColorStop(0, "rgba(0,0,0,.85)");
    r.addColorStop(0.55, "rgba(0,0,0,.4)");
    r.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = r;
    g.fillRect(0, 0, s, s);
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshBasicMaterial({ map: aoTex, transparent: true, depthWrite: false }));
  m.rotation.x = -Math.PI / 2;
  m.position.y = 0.012;
  parent.add(m);
  return m;
}

/* ---------- 胶卷罐 ---------- */
/** chars：罐身竖排的两个字；sub：侧面的一行小字（只放真实的值，例如卷号和格数） */
export function makeCanister(chars: string, sub: string) {
  const M = materials(),
    can = new THREE.Group();
  contact(can, 4.6, 4.6);
  const label = tex(2048, 835, (g, w, h) => {
    g.fillStyle = "#143026";
    g.fillRect(0, 0, w, h);
    const x0 = w * 0.25;
    g.fillStyle = COLORS.paper;
    g.textAlign = "center";
    g.textBaseline = "middle";
    const cs = [...chars];
    const size = cs.length > 2 ? 190 : 250;
    g.font = `600 ${size}px ${SERIF}`;
    cs.slice(0, 3).forEach((c, i, arr) => g.fillText(c, x0 - 40, h * ((i + 1) / (arr.length + 1))));
    g.save();
    g.translate(x0 + 170, h * 0.5);
    g.rotate(Math.PI / 2);
    g.font = `34px ${MONO}`;
    g.fillStyle = COLORS.brass;
    g.fillText(sub, 0, 0);
    g.restore();
    g.strokeStyle = COLORS.brass;
    g.lineWidth = 3;
    g.strokeRect(x0 - 250, 40, 520, h - 80);
  });
  const body = add(
    can,
    new THREE.CylinderGeometry(1.25, 1.25, 3.1, 96),
    new THREE.MeshPhysicalMaterial({ map: label, roughness: 0.36, metalness: 0.1, clearcoat: 0.7, clearcoatRoughness: 0.28 }),
    0,
    1.9,
    0
  );
  body.rotation.y = -Math.PI / 2;
  add(can, new THREE.CylinderGeometry(1.36, 1.38, 0.3, 96), M.brassDark, 0, 0.15, 0);
  add(can, new THREE.TorusGeometry(1.3, 0.05, 16, 96), M.brass, 0, 0.36, 0).rotation.x = Math.PI / 2;
  add(can, new THREE.TorusGeometry(1.3, 0.05, 16, 96), M.brass, 0, 3.44, 0).rotation.x = Math.PI / 2;
  add(can, new THREE.CylinderGeometry(1.38, 1.36, 0.32, 96), M.brassDark, 0, 3.62, 0);
  add(can, new THREE.CylinderGeometry(1.2, 1.3, 0.06, 96), M.brass, 0, 3.81, 0);
  const spool = add(can, new THREE.CylinderGeometry(0.3, 0.3, 0.7, 24), M.black, 0, 4.15, 0);
  const spoolTop = add(can, new THREE.CylinderGeometry(0.34, 0.34, 0.1, 12), M.brass, 0, 4.55, 0);
  return { group: can, body, spool, spoolTop };
}

/** 释放一组物件用到的几何体和贴图（材质缓存和木纹不释放，几幕共用） */
export function disposeTree(root: THREE.Object3D, keep: Set<THREE.Material | THREE.Texture> = new Set()) {
  const shared = new Set<unknown>([...keep, ...(matCache ? Object.values(matCache) : []), woodCache?.map, woodCache?.bump, aoTex]);
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry?.dispose();
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const m of mats) {
      if (!m || shared.has(m)) continue;
      for (const v of Object.values(m)) if (v instanceof THREE.Texture && !shared.has(v)) v.dispose();
      m.dispose();
    }
  });
}

/** 整个引擎关掉时把共用的贴图和材质也释放 */
export function disposeShared() {
  if (matCache) for (const m of Object.values(matCache)) m.dispose();
  woodCache?.map.dispose();
  woodCache?.bump.dispose();
  aoTex?.dispose();
  matCache = null;
  woodCache = null;
  aoTex = null;
}

/**
 * 取一张照片做贴图。照片在后台线程解码并缩到 maxWidth 宽（createImageBitmap），
 * 取到就先传到显卡（initTexture），不在画面切换的那一帧里现解码、现上传，免得卡一下。
 * 浏览器不支持这些参数时退回普通的 TextureLoader。超时或取不到时抛错，调用的地方继续用空白底片。
 */
export async function loadPhotoTexture(url: string, renderer: THREE.WebGLRenderer, { maxWidth = 1024, timeoutMs = 4000 } = {}): Promise<THREE.Texture> {
  const work = (async () => {
    let t: THREE.Texture;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`照片取不到：${res.status}`);
      const blob = await res.blob();
      const bmp = await createImageBitmap(blob, { resizeWidth: maxWidth, resizeQuality: "high", imageOrientation: "flipY", premultiplyAlpha: "none" });
      t = new THREE.Texture(bmp);
      t.flipY = false;
    } catch (err) {
      if (err instanceof Error && err.message.startsWith("照片取不到")) throw err;
      t = await new THREE.TextureLoader().loadAsync(url);
    }
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    t.needsUpdate = true;
    renderer.initTexture(t);
    return t;
  })();
  let timer = 0;
  const timeout = new Promise<never>((_, reject) => {
    timer = window.setTimeout(() => reject(new Error("照片超时")), timeoutMs);
  });
  try {
    return await Promise.race([work, timeout]);
  } finally {
    window.clearTimeout(timer);
  }
}

/** 等浏览器空闲时再做（没有 requestIdleCallback 的浏览器等 200 毫秒） */
export function whenIdle(timeout = 2000): Promise<void> {
  return new Promise((resolve) => {
    const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number };
    if (w.requestIdleCallback) w.requestIdleCallback(() => resolve(), { timeout });
    else window.setTimeout(resolve, 200);
  });
}
