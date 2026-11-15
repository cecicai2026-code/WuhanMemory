/**
 * 把景点数据里的结构化内容写成纸上的一行字。只换说法，不加内容。
 */
import type {
  FactStatus,
  OpeningHours,
  Payment,
  PaymentMethod,
  PoiFact,
  SourceType,
  Reservation,
  Ticket,
  Transport,
  Verification
} from "@wuhanmemory/shared";

const WEEKDAY = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function weekdays(days: number[]): string {
  const sorted = [...days].sort((a, b) => a - b);
  if (sorted.length === 7) return "每天";
  // 连续的几天写成"周二至周日"
  const contiguous = sorted.every((d, i) => i === 0 || d === sorted[i - 1] + 1);
  if (contiguous && sorted.length > 2) return `${WEEKDAY[sorted[0]]}至${WEEKDAY[sorted[sorted.length - 1]]}`;
  return sorted.map((d) => WEEKDAY[d]).join("、");
}

function months(ms: number[] | null): string {
  if (!ms || ms.length === 0 || ms.length === 12) return "";
  const sorted = [...ms].sort((a, b) => a - b);
  const contiguous = sorted.every((m, i) => i === 0 || m === sorted[i - 1] + 1);
  return contiguous ? `${sorted[0]} 至 ${sorted[sorted.length - 1]} 月，` : `${sorted.join("、")} 月，`;
}

export function formatOpeningHours(h: OpeningHours): string {
  const lines: string[] = [];
  if (h.allDay) lines.push("全天开放");
  for (const p of h.periods) {
    const last = p.lastEntry ? `（${p.lastEntry} 停止入场）` : "";
    lines.push(`${months(p.months)}${weekdays(p.weekdays)} ${p.open}–${p.close}${last}`);
  }
  if (h.closedWeekdays.length) lines.push(`${h.closedWeekdays.map((d) => WEEKDAY[d]).join("、")}闭馆`);
  if (h.note) lines.push(h.note);
  return lines.join("\n");
}

export function formatTicket(t: Ticket): string {
  const lines: string[] = [];
  if (t.free) lines.push("免费");
  for (const item of t.items) lines.push(`${item.name} ${item.priceCny} 元`);
  if (t.note) lines.push(t.note);
  return lines.join("\n");
}

export function formatReservation(r: Reservation): string {
  const lines = [r.required ? "需要预约" : "不需要预约"];
  if (r.how) lines.push(`预约方式：${r.how}`);
  if (r.advanceDays != null) lines.push(`最早提前 ${r.advanceDays} 天`);
  if (r.note) lines.push(r.note);
  return lines.join("\n");
}

const PAYMENT: Record<PaymentMethod, string> = {
  wechat: "微信",
  alipay: "支付宝",
  cash: "现金",
  "foreign-card": "外国银行卡",
  other: "其他"
};

export function formatPayment(p: Payment): string {
  const lines: string[] = [];
  if (p.methods.length) lines.push(p.methods.map((m) => PAYMENT[m]).join("、"));
  if (p.note) lines.push(p.note);
  return lines.join("\n");
}

export function formatTransport(t: Transport): string {
  const lines = t.metro.map((m) => {
    const line = m.line ? `地铁${m.line} ` : "地铁 ";
    const exit = m.exit ? ` ${m.exit} 出口` : "";
    const walk = m.walkMinutes != null ? `，步行约 ${m.walkMinutes} 分钟` : "";
    return `${line}${m.station}${exit}${walk}`;
  });
  if (t.note) lines.push(t.note);
  return lines.join("\n");
}

export function formatDuration(minutes: number): string {
  if (minutes >= 60 && minutes % 30 === 0) return `约 ${minutes / 60} 小时`;
  return `约 ${minutes} 分钟`;
}

export const VERIFICATION_TEXT: Record<Verification, string> = {
  onsite: "实地核实",
  confirmed: "核对过来源",
  placeholder: "占位",
  todo: "待补充"
};

export const SOURCE_TYPE_TEXT: Record<SourceType, string> = {
  "field-visit": "实地走访",
  "official-site": "官网",
  "official-wechat": "官方公众号",
  "official-ticketing": "官方售票页面",
  government: "政府网站",
  amap: "高德地图",
  media: "媒体报道",
  "travel-platform": "旅游平台",
  ugc: "游客笔记",
  other: "其他"
};

export const STATUS_TEXT: Record<FactStatus, string> = {
  verified: "已核实",
  pending: "待确认",
  expired: "已过期",
  missing: "待补充"
};

/** 一张纸的状态：有过期就是过期，有待确认或待补充就是待确认；一条资料都没有（例如周边美食是空的）也算待确认，不能盖"已核实" */
export function sheetStatus(facts: Array<PoiFact<unknown>>): "verified" | "pending" | "expired" {
  if (facts.length === 0) return "pending";
  if (facts.some((f) => f.status === "expired")) return "expired";
  if (facts.some((f) => f.status === "pending" || f.status === "missing")) return "pending";
  return "verified";
}

/** "2026-11-15" → "2026.11.15" */
/** 景点类别的中文名（数据里存的是英文代号）。没收录的代号原样显示 */
const CATEGORY_TEXT: Record<string, string> = {
  campus: "校园",
  "food-street": "美食街",
  landmark: "地标",
  museum: "博物馆",
  park: "公园",
  riverside: "江滩",
  street: "街区",
  temple: "寺庙"
};
export function categoryText(code: string): string {
  return CATEGORY_TEXT[code] ?? code;
}

export function formatDate(iso: string | null): string {
  return iso ? iso.replaceAll("-", ".") : "";
}
