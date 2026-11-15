# WuhanMemory Project Memory

最后更新: 2026-11-15

## 项目定位

WuhanMemory 是一个基于地图的 AI 旅游行程规划 Web 应用。用户通过 AI 对话输入目的地、旅行时间、预算、兴趣偏好、同行人、交通偏好等信息，系统生成可交互的地图行程、每日路线、景点介绍、交通建议、支付与预约提示、多媒体内容和可分享网页。

首个场景以武汉旅游为核心，后续扩展到其他城市。

## 当前仓库状态

- 当前目录已经初始化为 Git 仓库。
- Phase 1 工程骨架已完成。
- 已建立 Next.js 前端、FastAPI 后端、共享 TypeScript schema、mock 武汉 3 日行程、LLM provider gateway 骨架和基础数据库迁移。
- 2026-11-15（板块 4）：千问和豆包已经能通过 `LLMGateway` 真实调用和切换，mock provider 已移出应用代码。现在做到哪一步以 `docs/progress/current-progress.md` 为准。

## 下次进入项目时建议先读

1. `AGENTS.md`
2. `docs/progress/current-progress.md`
3. `docs/product/product-brief.md`
4. `docs/architecture/system-architecture.md`
5. `docs/architecture/ai-planning-pipeline.md`
6. `docs/architecture/data-model.md`

## 已确定的关键方向

- 界面: 按 `docs/design/design-system.md`。首页 `/` 是展示页，地图工作台在 `/map`；"暗房桌面"风格（v3）：每个页面是木桌上的一个场景，黑、红褐木头、墨绿、黄铜、米黄纸，一盏暖灯加暗角；界面做成实物；悬停有反应、点击才进入。地点档案分胶卷、晾片、纸页三幕。立体场景用 three.js 直接写（板块 1B，`lib/scene3d/`），只在首页和地点档案三幕、能悬停的宽屏上用；其余情况显示普通网页版，同一个网址、同一份数据。
- 环境变量: 后端 `apps/api/.env`，前端 `apps/web/.env.local`，根目录不放 `.env`。
- 中英双语（ADR 0009，2026-11-15）：同一个网址，语言记在 cookie `wm-lang`，右上角"中 / EN"铭牌切换。前端 `t("中文", "English")`；后端 `L("中文", "English")`，按 `?lang` → `X-Lang` → cookie 认语言。景点英文是 `data/pois/en/` 里带中文原文的译文（Claude 翻，未经人工核对）。
- 前端: Next.js App Router + TypeScript。
- 地图: 国内 MVP 优先使用高德地图 JS API 2.0 和 Web 服务 API。地图层抽象为 provider，后续可接 Mapbox 或 Cesium。
- 后端: FastAPI + Python，承载 AI 编排、路线规划、POI 聚合、分享页生成和异步任务。
- 数据库: JSON 种子文件 + SQLite（ADR 0003，2026-11-14 取代原来的 PostgreSQL + PostGIS + pgvector）。景点资料以 `data/pois/*.json` 为准，启动时导入 SQLite；读写经过 repository 层，以后可以换 PostgreSQL。
- 缓存: 高德路线等外部结果缓存在 SQLite 的表里，带 `checkedAt` 和 `expiresAt`。不使用 Redis 和任务队列。
- AI: 使用 `LLMGateway` 支持豆包和 Qwen 可切换（`.env` 设默认模型，每次请求可以另外指定，界面上有模型选择）。模型负责规划推理，后端工具负责真实数据查询、路线计算、结构化输出校验和持久化。

## 近期目标

1. 接入真实高德地图 JS API provider，替换 mock map 渲染层。
2. （已完成，板块 4）豆包和 Qwen provider 的真实调用、输出修复。工具调用没有做。
3. 建立 SQLite repository 层，替换 mock repository。
4. 加入规划 job 队列、SSE 状态流和 provider 观测指标。
5. 增强景点内容来源、媒体资产和授权内容管理。

## 进度维护规则

每次有实质性变更后更新:

- `docs/progress/current-progress.md`: 当前状态、完成项、下一步。
- `docs/adr/`: 记录不可轻易回滚的技术决策。
- 相关架构文档: 当接口、数据模型或模块边界改变时同步更新。
