/**
 * 前后端共用的数据结构。每个文件对应后端的一个 schema，两边要一致。
 *
 * 2026-11-15（板块 5）：7 月骨架里的旧行程结构（MapPoi、RouteSegment、DayStop 等）已删掉，
 * 行程的新结构在 planning.ts。
 */

export interface GeoPoint {
  lng: number;
  lat: number;
}

// 景点接口（板块 2）
export * from "./poi";
// 路线接口（板块 3）
export * from "./route";
// 模型接口（板块 4）
export * from "./llm";
// 对话、规划、行程（板块 5）
export * from "./planning";
// 双模型对比（板块 6）
export * from "./comparison";
// 分享链接和我的行程（板块 7）
export * from "./share";
