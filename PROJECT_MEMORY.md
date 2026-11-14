# WuhanMemory Project Memory

最后更新: 2026-11-14

## 项目定位

WuhanMemory 是一个基于地图的 AI 旅游行程规划 Web 应用。用户通过 AI 对话输入目的地、旅行时间、预算、兴趣偏好、同行人、交通偏好等信息，系统生成可交互的地图行程、每日路线、景点介绍、交通建议、支付与预约提示、多媒体内容和可分享网页。

首个场景以武汉旅游为核心，后续扩展到其他城市。

## 当前仓库状态

- 当前目录已经初始化为 Git 仓库。
- Phase 1 工程骨架已完成。
- 已建立 Next.js 前端、FastAPI 后端、共享 TypeScript schema、mock 武汉 3 日行程、LLM provider gateway 骨架和基础数据库迁移。
- 本地默认使用 mock LLM provider，不依赖真实豆包、Qwen 或高德 key。

## 下次进入项目时建议先读

1. `AGENTS.md`
2. `docs/progress/current-progress.md`
3. `docs/product/product-brief.md`
4. `docs/architecture/system-architecture.md`
5. `docs/architecture/ai-planning-pipeline.md`
6. `docs/architecture/data-model.md`

## 已确定的关键方向

- 界面: 按 `docs/design/design-system.md`。首页 `/` 是展示页，地图工作台在 `/map`；"暗房桌面"风格（v3）：每个页面是木桌上的一个场景，黑、红褐木头、墨绿、黄铜、米黄纸，一盏暖灯加暗角；界面做成实物；悬停有反应、点击才进入。地点档案分胶卷、晾片、纸页三幕。立体场景用 three.js。
- 环境变量: 后端 `apps/api/.env`，前端 `apps/web/.env.local`，根目录不放 `.env`。
- 前端: Next.js App Router + TypeScript。
- 地图: 国内 MVP 优先使用高德地图 JS API 2.0 和 Web 服务 API。地图层抽象为 provider，后续可接 Mapbox 或 Cesium。
- 后端: FastAPI + Python，承载 AI 编排、路线规划、POI 聚合、分享页生成和异步任务。
- 数据库: JSON 种子文件 + SQLite（ADR 0003，2026-11-14 取代原来的 PostgreSQL + PostGIS + pgvector）。景点资料以 `data/pois/*.json` 为准，启动时导入 SQLite；读写经过 repository 层，以后可以换 PostgreSQL。
- 缓存: 高德路线等外部结果缓存在 SQLite 的表里，带 `checkedAt` 和 `expiresAt`。不使用 Redis 和任务队列。
- AI: 使用 `LLMGateway` 支持豆包和 Qwen 可切换。模型负责规划推理，后端工具负责真实数据查询、路线计算、结构化输出校验和持久化。

## 近期目标

1. 接入真实高德地图 JS API provider，替换 mock map 渲染层。
2. 接入豆包和 Qwen provider 的真实 API 调用、schema repair 和工具调用。
3. 建立 SQLite repository 层，替换 mock repository。
4. 加入规划 job 队列、SSE 状态流和 provider 观测指标。
5. 增强景点内容来源、媒体资产和授权内容管理。

## 进度维护规则

每次有实质性变更后更新:

- `docs/progress/current-progress.md`: 当前状态、完成项、下一步。
- `docs/adr/`: 记录不可轻易回滚的技术决策。
- 相关架构文档: 当接口、数据模型或模块边界改变时同步更新。
