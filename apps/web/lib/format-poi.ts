/**
 * 把景点数据里的结构化内容写成纸上的一行字。只换说法，不加内容。
 * 每个函数最后一个参数是 t（lib/i18n.ts），按当前语言写；数据里的自由文字（例如 note）由后端按语言换好（英文是译文）。
 */
import type { T } from "@/lib/i18n";
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


const WEEKDAY = {
  zh: ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"],
  en: ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
};
const MONTH_EN = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function weekdays(days: number[], t: T): string {
  const W = t(WEEKDAY.zh, WEEKDAY.en);
  const sorted = [...days].sort((a, b) => a - b);
  if (sorted.length === 7) return t("每天", "Daily");
  // 连续的几天写成"周二至周日"
  const contiguous = sorted.every((d, i) => i === 0 || d === sorted[i - 1] + 1);
  if (contiguous && sorted.length > 2) return t(`${W[sorted[0]]}至${W[sorted[sorted.length - 1]]}`, `${W[sorted[0]]}–${W[sorted[sorted.length - 1]]}`);
  return sorted.map((d) => W[d]).join(t("、", ", "));
}

function months(ms: number[] | null, t: T): string {
  if (!ms || ms.length === 0 || ms.length === 12) return "";
  const sorted = [...ms].sort((a, b) => a - b);
  const contiguous = sorted.every((m, i) => i === 0 || m === sorted[i - 1] + 1);
  if (contiguous) return t(`${sorted[0]} 至 ${sorted[sorted.length - 1]} 月，`, `${MONTH_EN[sorted[0]]}–${MONTH_EN[sorted[sorted.length - 1]]}, `);
  return t(`${sorted.join("、")} 月，`, `${sorted.map((m) => MONTH_EN[m]).join(", ")}, `);
}

export function formatOpeningHours(h: OpeningHours, t: T): string {
  const lines: string[] = [];
  if (h.allDay) lines.push(t("全天开放", "Open all day"));
  for (const p of h.periods) {
    const last = p.lastEntry ? t(`（${p.lastEntry} 停止入场）`, ` (last entry ${p.lastEntry})`) : "";
    lines.push(`${months(p.months, t)}${weekdays(p.weekdays, t)} ${p.open}–${p.close}${last}`);
  }
  if (h.closedWeekdays.length) {
    const W = t(WEEKDAY.zh, WEEKDAY.en);
    const days = h.closedWeekdays.map((d) => W[d]).join(t("、", ", "));
    lines.push(t(`${days}闭馆`, `Closed ${days}`));
  }
  if (h.note) lines.push(h.note);
  return lines.join("\n");
}

export function formatTicket(tk: Ticket, t: T): string {
  const lines: string[] = [];
  if (tk.free) lines.push(t("免费", "Free"));
  for (const item of tk.items) lines.push(t(`${item.name} ${item.priceCny} 元`, `${item.name}: ¥${item.priceCny}`));
  if (tk.note) lines.push(tk.note);
  return lines.join("\n");
}

export function formatReservation(r: Reservation, t: T): string {
  const lines = [r.required ? t("需要预约", "Booking required") : t("不需要预约", "No booking needed")];
  if (r.how) lines.push(t(`预约方式：${r.how}`, `How to book: ${r.how}`));
  if (r.advanceDays != null) lines.push(t(`最早提前 ${r.advanceDays} 天`, `Up to ${r.advanceDays} days ahead`));
  if (r.note) lines.push(r.note);
  return lines.join("\n");
}

const PAYMENT: Record<PaymentMethod, { zh: string; en: string }> = {
  wechat: { zh: "微信", en: "WeChat Pay" },
  alipay: { zh: "支付宝", en: "Alipay" },
  cash: { zh: "现金", en: "Cash" },
  "foreign-card": { zh: "外国银行卡", en: "Foreign bank cards" },
  other: { zh: "其他", en: "Other" }
};

export function formatPayment(p: Payment, t: T): string {
  const lines: string[] = [];
  if (p.methods.length) lines.push(p.methods.map((m) => t(PAYMENT[m].zh, PAYMENT[m].en)).join(t("、", ", ")));
  if (p.note) lines.push(p.note);
  return lines.join("\n");
}

export function formatTransport(tr: Transport, t: T): string {
  const lines = tr.metro.map((m) => {
    const line = m.line ? t(`地铁${m.line} `, `Metro ${m.line}, `) : t("地铁 ", "Metro: ");
    const exit = m.exit ? t(` ${m.exit} 出口`, ` exit ${m.exit}`) : "";
    const walk = m.walkMinutes != null ? t(`，步行约 ${m.walkMinutes} 分钟`, `, about ${m.walkMinutes} min walk`) : "";
    return `${line}${m.station}${exit}${walk}`;
  });
  if (tr.note) lines.push(tr.note);
  return lines.join("\n");
}

export function formatDuration(minutes: number, t: T): string {
  if (minutes >= 60 && minutes % 30 === 0) return t(`约 ${minutes / 60} 小时`, `About ${minutes / 60} h`);
  return t(`约 ${minutes} 分钟`, `About ${minutes} min`);
}

type Both = { zh: string; en: string };

export const VERIFICATION_TEXT: Record<Verification, Both> = {
  onsite: { zh: "实地核实", en: "Checked on site" },
  confirmed: { zh: "核对过来源", en: "Checked against source" },
  placeholder: { zh: "占位", en: "Placeholder" },
  todo: { zh: "待补充", en: "To fill in" }
};

export const SOURCE_TYPE_TEXT: Record<SourceType, Both> = {
  "field-visit": { zh: "实地走访", en: "site visit" },
  "official-site": { zh: "官网", en: "official site" },
  "official-wechat": { zh: "官方公众号", en: "official WeChat account" },
  "official-ticketing": { zh: "官方售票页面", en: "official ticketing page" },
  government: { zh: "政府网站", en: "government site" },
  amap: { zh: "高德地图", en: "AMap" },
  media: { zh: "媒体报道", en: "news report" },
  "travel-platform": { zh: "旅游平台", en: "travel platform" },
  ugc: { zh: "游客笔记", en: "visitor notes" },
  other: { zh: "其他", en: "other" }
};

export const STATUS_TEXT: Record<FactStatus, Both> = {
  verified: { zh: "已核实", en: "Verified" },
  pending: { zh: "待确认", en: "To confirm" },
  expired: { zh: "已过期", en: "Expired" },
  missing: { zh: "待补充", en: "To fill in" }
};

/** 按语言取 {zh, en} 里的一句 */
export function both(b: Both, t: T): string {
  return t(b.zh, b.en);
}

/** 一张纸的状态：有过期就是过期，有待确认或待补充就是待确认；一条资料都没有（例如周边美食是空的）也算待确认，不能盖"已核实" */
export function sheetStatus(facts: Array<PoiFact<unknown>>): "verified" | "pending" | "expired" {
  if (facts.length === 0) return "pending";
  if (facts.some((f) => f.status === "expired")) return "expired";
  if (facts.some((f) => f.status === "pending" || f.status === "missing")) return "pending";
  return "verified";
}

/** 景点类别的名称（数据里存的是英文代号）。没收录的代号原样显示 */
const CATEGORY_TEXT: Record<string, Both> = {
  campus: { zh: "校园", en: "Campus" },
  "food-street": { zh: "美食街", en: "Food street" },
  landmark: { zh: "地标", en: "Landmark" },
  museum: { zh: "博物馆", en: "Museum" },
  park: { zh: "公园", en: "Park" },
  riverside: { zh: "江滩", en: "Riverside" },
  street: { zh: "街区", en: "Historic street" },
  temple: { zh: "寺庙", en: "Temple" }
};
export function categoryText(code: string, t: T): string {
  const c = CATEGORY_TEXT[code];
  return c ? t(c.zh, c.en) : code;
}

/** "2026-11-15" → "2026.11.15" */
export function formatDate(iso: string | null): string {
  return iso ? iso.replaceAll("-", ".") : "";
}
