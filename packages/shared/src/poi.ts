/**
 * 景点接口返回的数据结构，和后端 apps/api/app/schemas/poi_api.py 对应。
 * GET /api/pois → PoiList；GET /api/pois/{id} → PoiDetailResponse。
 * 字段说明见 docs/architecture/data-model.md 和 docs/architecture/api-contracts.md。
 */

/** 这条信息是怎么来的：实地核实、核对过来源、官网占位、没有来源 */
export type Verification = "onsite" | "confirmed" | "placeholder" | "todo";

/** 界面上的状态，后端按请求当天现算 */
export type FactStatus = "verified" | "pending" | "expired" | "missing";
export type PoiStatus = "verified" | "pending" | "expired";

export type SourceType = "field-visit" | "official-site" | "official-wechat" | "official-ticketing" | "government" | "amap" | "media" | "travel-platform" | "other";

export interface PoiSource {
  id: string;
  type: SourceType;
  title: string;
  url: string | null;
  accessedAt: string | null;
}

export interface PoiFact<T> {
  value: T | null;
  verification: Verification;
  status: FactStatus;
  source: PoiSource | null;
  lastCheckedAt: string | null;
  expiresAt: string | null;
  todo: string | null;
  note: string | null;
}

export interface Coordinates {
  lng: number;
  lat: number;
  coordSystem: "GCJ-02";
}

export interface OpeningPeriod {
  months: number[] | null;
  weekdays: number[];
  open: string;
  close: string;
  lastEntry: string | null;
}

export interface OpeningHours {
  allDay: boolean;
  periods: OpeningPeriod[];
  closedWeekdays: number[];
  note: string | null;
}

export interface Ticket {
  free: boolean;
  items: Array<{ name: string; priceCny: number }>;
  note: string | null;
}

export interface Reservation {
  required: boolean;
  how: string | null;
  advanceDays: number | null;
  note: string | null;
}

export type PaymentMethod = "wechat" | "alipay" | "cash" | "foreign-card" | "other";

export interface Payment {
  methods: PaymentMethod[];
  note: string | null;
}

export interface Transport {
  metro: Array<{ station: string; line: string | null; exit: string | null; walkMinutes: number | null }>;
  note: string | null;
}

export interface PhotoSpot {
  title: string;
  description: string;
  photo: string | null;
}

export interface FoodItem {
  name: string;
  walkMinutes: number | null;
  note: string | null;
}

export interface Review {
  author: string;
  relation: "self" | "friend";
  visitedAt: string;
  text: string;
}

export interface PoiPhoto {
  file: string;
  caption: string;
  license: "own" | "open-license" | "official-placeholder";
  placeholder: boolean;
  author: string | null;
  takenAt: string | null;
  sourceUrl: string | null;
  retrievedAt: string | null;
  licenseNote: string | null;
  /** 相对于后端地址；占位照片不在本机时为 null */
  url: string | null;
}

export interface FactCounts {
  verified: number;
  pending: number;
  expired: number;
  missing: number;
}

export interface PoiSummary {
  id: string;
  name: string;
  district: string;
  category: string;
  tags: string[];
  location: Coordinates;
  status: PoiStatus;
  counts: FactCounts;
  coverPhoto: PoiPhoto | null;
}

export interface PoiDetail extends PoiSummary {
  sources: PoiSource[];
  address: PoiFact<string>;
  intro: PoiFact<string>;
  history: PoiFact<string>;
  openingHours: PoiFact<OpeningHours>;
  ticket: PoiFact<Ticket>;
  reservation: PoiFact<Reservation>;
  payment: PoiFact<Payment>;
  transport: PoiFact<Transport>;
  recommendedDurationMinutes: PoiFact<number>;
  bestTime: PoiFact<string>;
  photoSpots: Array<PoiFact<PhotoSpot>>;
  food: Array<PoiFact<FoodItem>>;
  reviews: Review[];
  photos: PoiPhoto[];
}

export interface PoiList {
  /** 状态按哪一天算的 */
  asOf: string;
  pois: PoiSummary[];
}

export interface PoiDetailResponse {
  asOf: string;
  poi: PoiDetail;
}
