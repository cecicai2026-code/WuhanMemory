/**
 * 幕间转场（设计规范 G4）：物件不消失再出现，而是飞到新位置。
 *
 * 做法：点下去以后，上一幕把那个物件（胶片格里的照片、主题卡）画到一块画布上，交给这里；
 * 这里在黑幕上面放一个网页元素，样子和位置都和那个物件一样。黑幕落下、换页、下一幕准备好以后，
 * 让它飞到下一幕里对应物件的位置，变成那个物件，再把真的物件露出来、把它撤掉。
 *   - 照片（胶卷 → 晾片）：飞的途中长出相纸的白边，底片慢慢显成相纸上的照片。
 *   - 翻页（晾片 → 纸页）：主题卡一边飞一边翻过来，背面是信纸，落在信纸的位置。
 * 不引用 three.js。
 */

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** 上一幕交出来的物件 */
export interface Handoff {
  kind: "print" | "card";
  /** 景点 id */
  id: string;
  /** 主题 id（主题卡才有） */
  topic?: string;
  /** 在屏幕上的位置 */
  rect: Rect;
  /** 物件的样子 */
  image: HTMLCanvasElement;
}

const EASE = "cubic-bezier(0.16, 1, 0.3, 1)";

export function createFlyer(root: HTMLElement) {
  const el = root;
  el.innerHTML = "";
  const inner = document.createElement("div");
  inner.className = "stage-flyer-inner";
  const front = document.createElement("div");
  front.className = "stage-flyer-face";
  const back = document.createElement("div");
  back.className = "stage-flyer-face stage-flyer-back";
  inner.append(front, back);
  el.append(inner);
  let running: Animation[] = [];

  const box = (r: Rect) => ({ left: `${r.x}px`, top: `${r.y}px`, width: `${r.w}px`, height: `${r.h}px` });

  function reset() {
    running.forEach((a) => a.cancel());
    running = [];
    front.innerHTML = "";
    back.innerHTML = "";
    el.removeAttribute("data-on");
    el.removeAttribute("data-mode");
  }

  return {
    /** 在上一幕物件的位置放好替身 */
    show(h: Handoff) {
      reset();
      h.image.className = "stage-flyer-img";
      front.append(h.image);
      Object.assign(el.style, box(h.rect), { padding: "0px", transform: "none" });
      el.dataset.mode = h.kind;
      el.dataset.on = "";
    },

    /**
     * 照片：飞到晾片绳上那张照片的位置。to 是相纸的外框，image 是那张照片在晾片幕里的样子（例如空白相纸），
     * 飞的途中从底片渐变成它。pad 是相纸白边，按宽度的比例（上、左右、下）。
     */
    async toPrint(to: Rect, image: HTMLCanvasElement | null, pad: { top: number; side: number; bottom: number }, rotateDeg: number, ms = 950) {
      if (image) {
        image.className = "stage-flyer-img stage-flyer-develop";
        front.append(image);
      }
      const p = (v: number) => `${v * to.w}px`;
      const a = el.animate(
        [
          { ...box(rectOf(el)), padding: "0px", backgroundColor: "rgba(233,223,198,0)", transform: "rotate(0deg)", boxShadow: "0 0 0 rgba(0,0,0,0)" },
          { ...box(to), padding: `${p(pad.top)} ${p(pad.side)} ${p(pad.bottom)}`, backgroundColor: "rgba(233,223,198,1)", transform: `rotate(${rotateDeg}deg)`, boxShadow: "10px 18px 26px rgba(0,0,0,.5)" }
        ],
        { duration: ms, easing: EASE, fill: "forwards" }
      );
      running.push(a);
      if (image) running.push(image.animate([{ opacity: 0 }, { opacity: 1 }], { duration: ms * 0.8, delay: ms * 0.15, easing: "ease-in-out", fill: "both" }));
      await a.finished.catch(() => {});
    },

    /** 翻页：主题卡一边飞一边翻过来，落在信纸的位置 */
    async toSheet(to: Rect, ms = 1000) {
      const from = rectOf(el);
      const a = el.animate([box(from), box(to)], { duration: ms, easing: EASE, fill: "forwards" });
      const b = inner.animate([{ transform: "rotateY(0deg)" }, { transform: "rotateY(180deg)" }], { duration: ms * 0.8, easing: "cubic-bezier(0.65, 0, 0.35, 1)", fill: "forwards" });
      running.push(a, b);
      await a.finished.catch(() => {});
    },

    /** 真的物件露出来以后，替身淡出撤掉 */
    async done(ms = 220) {
      const a = el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: ms, fill: "forwards" });
      running.push(a);
      await a.finished.catch(() => {});
      reset();
    },

    cancel: reset
  };
}

function rectOf(el: HTMLElement): Rect {
  const r = el.getBoundingClientRect();
  return { x: r.left, y: r.top, w: r.width, h: r.height };
}

export type Flyer = ReturnType<typeof createFlyer>;
