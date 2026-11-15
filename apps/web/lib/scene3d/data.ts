/**
 * 每一幕从页面拿到的数据。页面在服务器端用 lib/places.ts 取真实接口的数据，整理成这里的样子交给场景，
 * 普通版和立体版用的是同一次取到的同一份数据。这个文件不引用 three.js。
 */
import type { PoiSummary } from "@wuhanmemory/shared";
import { countsText, isClosed, pad2, photoCredit } from "@/lib/places";

/** 胶片上的一格 = 一个景点 */
export interface RollsFrame {
  id: string;
  name: string;
  district: string;
  /** 格号：在全部景点里的序号（从 1 开始），筛选后也不变，和普通版一致 */
  no: number;
  /** 封面照片的缩略图地址（800 宽）；公开模式或没有照片时是 null，胶片格显示空白底片 */
  photoUrl: string | null;
  /** 原图地址：缩略图取不到时（例如后端还没装 Pillow）退回用它 */
  photoFull: string | null;
  /** 占位照片的出处，不是占位照片时是 null */
  credit: string | null;
  closed: boolean;
  /** "已过期 1 · 待确认 9 · 待补充 4"，全部核实时为空 */
  counts: string;
}

export interface RollsData {
  frames: RollsFrame[];
  /** 全部景点的数量（右上角"共 N 格"） */
  total: number;
  /** 按区筛选时的区名 */
  district: string | null;
  /** 地址里的 ?at=景点id：从晾片幕回来时停在这一格 */
  at: string | null;
}

export function rollsFrame(p: PoiSummary, no: number): RollsFrame {
  return {
    id: p.id,
    name: p.name,
    district: p.district,
    no,
    photoUrl: p.coverPhoto?.url ? (p.coverPhoto.thumbUrl ?? p.coverPhoto.url) : null,
    photoFull: p.coverPhoto?.url ?? null,
    credit: p.coverPhoto?.url ? photoCredit(p.coverPhoto) : null,
    closed: isClosed(p),
    counts: countsText(p.counts)
  };
}

/** 晾片绳上的一张照片 = 一个景点。和胶片格同样的字段 */
export type LinePrint = RollsFrame;

/** 显影盘里的一张主题卡 */
export interface LineTopic {
  /** 地址里的主题 id：overview、tips、gallery、food */
  id: string;
  name: string;
  /** 这张纸盖哪个章，和普通版的信纸一致 */
  status: "verified" | "pending" | "expired";
}

export interface LineData {
  /** 全部景点，晾在绳子上 */
  prints: LinePrint[];
  /** 当前景点 */
  sel: string;
  /** 标题下面一行："区 · 类别" */
  sub: string;
  topics: LineTopic[];
}

/** 纸页幕：桌上的物件只和主题有关（纸本身是网页文字，不在场景里） */
export interface SheetData {
  /** 当前景点 id（书和方向键跳到别的主题时用） */
  id: string;
  /** 当前主题 id */
  topic: string;
  topics: Array<{ id: string; name: string }>;
}

/** 首页桌面：四件物件各通往哪个页面 */
export interface DeskData {
  /** 顺序：胶卷罐、灯箱、两台打字机、笔记本 */
  stops: Array<{ label: string; href: string }>;
  /** 一开始停在第几站（0 是全景） */
  at?: number;
  /** 要不要播开场（这次访问的第一个页面是首页、还没播过） */
  intro: boolean;
}

/** 胶卷罐侧面的一行小字，只放真实的值 */
export function rollLabel(d: RollsData): string {
  return `${d.district ?? "WUHAN MEMORY"} · ${pad2(d.frames.length)} EXP`;
}
