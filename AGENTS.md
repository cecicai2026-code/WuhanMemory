# Agent Instructions for WuhanMemory

> 当前开发目标、工作规则和分阶段计划见 `docs/kickoff/claude-code-kickoff.md`，开始工作前必须先读。

本项目是基于地图和 AI 对话的旅游行程规划 Web 应用。后续代码代理进入仓库后，请先读取 `PROJECT_MEMORY.md`，再根据任务读取相关文档。

## 必读顺序

1. `PROJECT_MEMORY.md`
2. `docs/progress/current-progress.md`
3. `docs/product/product-brief.md`
4. `docs/architecture/system-architecture.md`
5. 与当前任务直接相关的架构文档

## 架构原则

- 地图工作台是核心体验，前端不要做成营销 landing page。
- AI 输出必须结构化，并由后端 schema 和业务规则校验。
- AI provider 必须通过 `LLMGateway` 接入，不能在业务代码里直接绑定豆包或 Qwen SDK。
- POI、路线、开放时间、票价、支付和预约信息都要保留来源与更新时间。
- 前端不能持有私密 Web 服务 key。
- 地图 provider、AI provider、路线 provider 都应保持可替换边界。
- 分享页绑定不可变 itinerary version。

## 修改项目时的维护要求

- 改变技术决策时，在 `docs/adr/` 新增或更新 ADR。
- 改变数据模型时，同步更新 `docs/architecture/data-model.md`。
- 改变接口时，同步更新 `docs/architecture/api-contracts.md`。
- 改变 AI 规划流程时，同步更新 `docs/architecture/ai-planning-pipeline.md`。
- 完成阶段性工作后更新 `docs/progress/current-progress.md`。

## 当前默认技术栈

- Frontend: Next.js App Router + TypeScript。
- Backend: FastAPI + Python。
- Database: JSON 种子文件（`data/pois/*.json`）+ SQLite，读写经过 repository 层，见 ADR 0003。
- Cache: 存在 SQLite 的表里，带 `checkedAt` 和 `expiresAt`；不使用 Redis 和独立 worker。
- Map MVP: 高德地图 JS API 2.0 + 高德 Web 服务 API。
- LLM: 豆包和 Qwen 可切换，MVP 本地默认 mock provider。

## 安全提醒

- 不要提交真实 API key、数据库密码或个人敏感信息。
- 不要抓取或保存未授权的第三方评价全文。
- 对动态旅行信息设置 TTL，并在 UI 展示“待确认”状态。
