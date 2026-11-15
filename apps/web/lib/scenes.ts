/**
 * 网站的每个页面是一"幕"（设计规范第 2 节）。
 * 幕的编号和样片里的一致：01 桌面，02 到 04 是地点档案，05 灯箱，06 两台打字机，07 笔记本，08 明信片。
 */
export interface SceneInfo {
  no: string;
  name: string;
  path: string;
  /** 菜单里显示的页面名称 */
  page: string;
}

export const SCENES = {
  desk: { no: "01", name: "桌面", path: "/", page: "首页" },
  places: { no: "02", name: "胶卷", path: "/places", page: "地点档案" },
  place: { no: "03", name: "晾片", path: "/places", page: "地点档案" },
  sheet: { no: "04", name: "纸页", path: "/places", page: "地点档案" },
  map: { no: "05", name: "灯箱", path: "/map", page: "地图工作台" },
  compare: { no: "06", name: "两台打字机", path: "/compare", page: "模型对比" },
  trips: { no: "07", name: "笔记本", path: "/trips", page: "我的行程" },
  share: { no: "08", name: "明信片", path: "/s", page: "分享页" }
} as const satisfies Record<string, SceneInfo>;

/** 菜单里的五个页面，顺序固定 */
export const MENU: SceneInfo[] = [SCENES.desk, SCENES.map, SCENES.places, SCENES.compare, SCENES.trips];
