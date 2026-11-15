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
  /** 封面照片的地址；公开模式或没有照片时是 null，胶片格显示空白底片 */
  photoUrl: string | null;
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
    photoUrl: p.coverPhoto?.url ?? null,
    credit: p.coverPhoto?.url ? photoCredit(p.coverPhoto) : null,
    closed: isClosed(p),
    counts: countsText(p.counts)
  };
}

/** 胶卷罐侧面的一行小字，只放真实的值 */
export function rollLabel(d: RollsData): string {
  return `${d.district ?? "WUHAN MEMORY"} · ${pad2(d.frames.length)} EXP`;
}
