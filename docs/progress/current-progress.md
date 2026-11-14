# Current Progress

最后更新: 2026-11-15（板块 2 进行中）

## 当前阶段

板块 0（准备）已完成。板块 1 在 2026-11-15 拆成两半：

- **板块 1A（已完成，2026-11-15 合进 main）**：界面外壳、地图工作台 `/map` 的布局、地点档案的普通网页版（`/places` 和 `/places/[id]`）、`/compare` 和 `/trips` 的空页面，删除旧的浅色 mock 界面。不用 three.js。
- **板块 1B（板块 5 完成之后）**：把立体三幕（胶卷、晾片、纸页）和首页桌面场景搬进正式网站。

拆的原因：文书里写的功能（数据质量规则、千问和豆包切换、行程校验、双模型对比）一个都还没开始，要先保证它们做出来。

做的顺序：0 → 1A → 2 → 3 → 4 → 5 → 1B → 6 → 7。分板块计划见 `docs/kickoff/claude-code-kickoff.md`。

板块 1A 是在分支 `block-1a-shell` 上做的，已合进 main。

**板块 2（进行中，分支 `block-2-poi-data`）**：景点数据格式、数据检查脚本、SQLite 导入和接口、地点档案接真实接口，代码部分已完成；景点资料还没有录入，等 Cecilia 回答景点清单、坐标和照片的问题。

## 板块 2 完成情况

- [x] 数据格式由 Cecilia 确认（2026-11-15）：每条信息带 `verification`（实地核实 / 核对过来源 / 官网占位 / TODO）、`sourceId`、`lastCheckedAt`，会变的信息还要 `expiresAt`；过期上限：开放时间和预约 90 天，票价、支付、周边美食 180 天，交通 365 天。详见 `docs/architecture/data-model.md`。
- [x] 填写模板 `docs/data/poi-fill-template.md`。
- [x] 数据检查脚本 `corepack pnpm check:data`，错误和警告两级；测试里 12 份故意放错的数据全部能查出来。
- [x] SQLite 导入（只导入没有错误的景点）、repository 层、`GET /api/pois`、`GET /api/pois/{id}`。
- [x] 删除后端的 mock 行程数据；行程、规划、分享接口在板块 5、7 之前如实返回 404 或 501。
- [x] `/places`、`/places/[id]` 接到真实接口：每个条目显示核实方式、来源、核实日期、有效期；占位盖"待确认"，过期盖"已过期"。
- [x] 后端测试 44 个通过；前端 `typecheck` 通过。
- [x] 文档：`data-model.md` 重写，`api-contracts.md`、`frontend-ux.md`、设计规范第 12 节已更新。
- [ ] Cecilia 回答：10 个景点里哪些去过、保留哪些、要不要加；坐标怎么拿；要不要下载官网占位照片。
- [ ] 录入景点资料（Cecilia 提供的照填，没提供的按官网占位并标来源，找不到来源的写 TODO(Cecilia)），全部通过检查。
- [x] 去掉过期条目的红褐色竖线和红字（违反设计规范 8.3：红褐色只用于页码小字和"已过期"章）。
- [ ] 界面上规范里没有、由 Claude 自己加的几处（条目旁的小章、详情页顶部说明、卡片上的计数、"支付和预约提示"改名"支付方式"）等 Cecilia 看过再定。
- [ ] Cecilia 在 Mac 上启动前后端看页面、运行 `pnpm build`；Claude 看截图调样式。
- [ ] 合进 main。

## 板块 1A 完成情况

- [x] 颜色变量、字体（自托管）、基础组件、外壳（四角标注和菜单）、样式参考页 `/styleguide`。
- [x] 临时首页（标题和四个入口），`/compare`、`/trips`、`/s/[slug]` 的空页面。
- [x] 删除旧的浅色 mock 界面、假地图和前端的 mock 接口调用。
- [x] `/map` 的布局：对话纸、灯箱（地图占位）、行程卡；手机上是底部面板。
- [x] `/places` 列表：示例清单 10 个景点，只有名字和区，按区域筛选（板块 2 已换成真实接口）。
- [x] `/places/[id]` 详情：四个主题四张信纸，条目全部显示"待补充"。
- [x] `typecheck` 通过。
- [x] Cecilia 运行 `pnpm build`，通过。
- [x] Claude 在浏览器里看过每个页面（电脑 1280px、平板 800px、手机 375px），改了三处样式：索引卡的横线对齐文字、手机页眉不换行、详情页的主题索引。
- [x] Cecilia 同意合进 main。颜色、字体、版面以后想调可以随时提。

## 怎么看网站

地点档案要用后端的数据，所以前后端都要启动，各开一个终端窗口：

```bash
cd ~/WuhanMemory-project2 && corepack pnpm dev:api
```

```bash
cd ~/WuhanMemory-project2 && corepack pnpm dev
```

然后打开 `http://localhost:3000/`。各页面网址见 `docs/architecture/frontend-ux.md`。

检查景点资料：

```bash
cd ~/WuhanMemory-project2 && corepack pnpm check:data
```

## 板块 0 完成情况

- [x] 读现有代码，列出保留和重写的部分（结论见 `docs/progress/dev-log.md` 2026-11-14）。
- [x] ADR 0003：数据存储改用 JSON 种子文件 + SQLite，不使用 Redis。
- [x] 环境变量模板：`apps/api/.env.example` 和 `apps/web/.env.example`。
- [x] Cecilia 已申请并填好 key：千问、豆包（含 endpoint ID）、高德 JS key、安全密钥、Web 服务 key。只检查过格式，还没有真实调用验证。
- [x] 设计规范 `docs/design/design-system.md` v3（"暗房桌面"风格），方向已由 Cecilia 确认。
- [x] 地点档案三幕的立体样片：`docs/design/prototypes/` 下的 `darkroom-rolls.html`、`darkroom-line.html`、`darkroom-page.html`，三幕已连通，Cecilia 已确认。
- [ ] Cecilia 确认 `WuHan-Memory` 老仓库泄露过的高德 key 已重置。

## 代码现状

前端（`apps/web`）在板块 1A 重写过，结构见 `docs/architecture/frontend-ux.md` 的"前端代码结构"。后端仍是 2026-07-05 的骨架。`docs/design/prototypes/` 里的样片是独立的设计稿（单个网页加 three.js），不属于网站代码。

保留:

- `apps/api/app/services/llm/`：`LLMGateway` 和 provider 边界。
- `packages/map-core`：地图 provider 接口。
- `apps/api/app/main.py`、`core/config.py`、`schemas/itinerary.py`、`packages/shared/src/index.ts`：入口、配置和行程数据结构（景点字段要扩充）。
- monorepo 工程结构。

板块 2 新增（后端）:

- `app/schemas/poi.py`（景点文件格式）、`app/data_quality/`（规则和检查）、`app/db/`（SQLite 和导入）、`app/repositories/`（repository 层）、`app/api/pois.py`（景点接口）、`app/services/poi_view.py`（算状态）。
- 编出来的 mock 行程数据、`mock_planner.py` 已删除（板块 2）。`routes.py` 里的对话、规划、行程、分享接口在板块 5、7 重写。
- `app/schemas/itinerary.py` 里的 `MapPoi` 还是旧字段，板块 5 改成引用景点数据。

保留但暂不使用: `infra/docker/docker-compose.yml`、`infra/migrations/0001_initial_schema.sql`。

## 已知问题

- `apps/api/app/core/config.py` 还没有高德的配置字段，板块 3 添加（数据库和数据目录的字段板块 2 已加）。
- `data/pois/` 现在是空的，地点档案页显示"还没有景点资料"。
- `docs/architecture/frontend-ux.md` 的页面结构和代码结构已按 1A 更新；地图交互、对话体验等章节还是早期设想，板块 3、5 实现时再核对。
- `apps/web/package.json` 里的 `lucide-react` 现在没有用到，要不要卸载等 Cecilia 决定。
- 首页四张入口卡和各空页面上的文案是 Claude 写的草稿，等 Cecilia 定稿。

## 怎么看样片

样片要通过本地网址打开（三个页面共用模块文件，直接双击打不开）。在 Mac 终端运行下面的命令，再用浏览器打开 `http://localhost:4173/darkroom-rolls.html`：

```bash
cd ~/WuhanMemory-project2 && python3 -m http.server 4173 --bind 127.0.0.1 --directory docs/design/prototypes
```

看完后在终端按 Ctrl+C 停止。需要联网（加载 three.js）。

## 其余页面的样片（板块 1B 的依据）

2026-11-15 把分支 `design/prototype-scenes` 合进了 main。`docs/design/prototypes/` 里新增六个样片和共用的 `kit.js`、`kit.css`：

| 样片 | 对应页面 |
|---|---|
| `darkroom-desk.html` | 首页（桌面） |
| `darkroom-map.html` | 地图工作台（灯箱） |
| `darkroom-compare.html` | 模型对比（两台打字机） |
| `darkroom-trips.html` | 我的行程（笔记本） |
| `darkroom-card.html` | 分享页（明信片） |
| `darkroom-plan.html` | 填单（规划前的输入页，设计规范里还没有这一幕） |

这六个样片 Cecilia 还没有逐个确认。板块 1B 开工时要处理：

- 多处用了红色手写字（首页的入口链接、对话纸上用户的话、"再冲洗一份？"、填单的"还想说"），和设计规范"手写字只用蓝灰色、只出现在纸面上"不一致。
- 对比样片的评分卡上有写死的"通过 / 未通过"章，只演示样子，不能带进正式网站。
- 都没有手机版；字体用的是 Google Fonts；对话和填单的选项画在贴图上，不能用键盘操作。
- 填单幕要不要采用、放在哪条路径，由 Cecilia 决定。

工作区 `.claude/worktrees/prototype-scenes` 保留，没有删除。

## 下一步

板块 2 剩下的：Cecilia 回答景点清单、坐标、照片三个问题后录入景点资料，再看页面截图。之后是板块 3（高德地图和路线）。

`three.js`、`@react-three/fiber`、`motion`、`lenis` 留到板块 1B 再确认。

## 开放问题

- 首页各章节的文案和首屏备用图。
- 网站最终怎么让别人打开（板块 7 决定）。
