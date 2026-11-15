/**
 * 立体场景的几个接口。这个文件不引用 three.js，普通版的页面也可以 import，不会把 three.js 带进来。
 */

/** 哪一幕：胶卷、晾片、纸页（地点档案的三幕），首页的桌面 */
export type StageKind = "rolls" | "line" | "sheet" | "desk";

/** 页面告诉场景要显示什么。data 是这一幕自己的数据（来自真实接口），key 变了才重新布置 */
export interface StageRequest<D = unknown> {
  kind: StageKind;
  key: string;
  data: D;
}

/** 场景出问题时告诉外面，外面就退回普通版 */
export type StageFailReason = "init-error" | "context-lost" | "too-slow" | "timeout" | "load-error";

/** 网页上的按钮、键盘、焦点让场景做的事，例如 { type: "page", dir: 1 } */
export interface StageCommand {
  type: string;
  [k: string]: unknown;
}

/** 场景告诉网页的状态（当前选中第几格等），网页据此更新标题、刻度。每一幕自己定内容 */
export type StageState = Record<string, unknown> & { kind: StageKind };

export interface EngineHooks {
  onFail(reason: StageFailReason, detail?: unknown): void;
  /** 帧率太低、降了一级画质时通知（0 是完整画质，1 是降级） */
  onQuality?(level: number): void;
  /** 地址带 ?debug=fps 时显示帧率计数器 */
  debugFps: boolean;
  /** 场景的状态变了 */
  onState(state: StageState): void;
  /** 场景要网页跳到某个网址（点了一格、镜头推近之后） */
  onNavigate(href: string): void;
  /** 键盘聚焦时画在物件周围的黄铜框（网页里的一个元素，场景每帧设它的位置） */
  ring: HTMLElement;
}

export interface StageEngine {
  /** 布置并显示这一幕；第一帧画出来、要用的贴图都准备好以后才算完成 */
  show(req: StageRequest): Promise<void>;
  /** 网页让场景做的事 */
  command(cmd: StageCommand): void;
  /** 当前页面没有立体场景：停止绘制，留着以后回来用 */
  idle(): void;
  dispose(): void;
}

export type CreateEngine = (container: HTMLElement, hooks: EngineHooks) => StageEngine;
