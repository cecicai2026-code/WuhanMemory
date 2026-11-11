# Current Progress

最后更新: 2026-07-05

## 当前阶段

Phase 1 工程骨架已完成。当前应用可以在本地运行 mock 版武汉 3 日游规划工作台。

## 已完成

- 明确产品定位: 基于地图和 AI 对话的武汉旅游行程规划 Web 应用。
- 明确 MVP 范围: 武汉、1 到 5 天、AI 对话、2D/3D 地图、行程时间线、景点详情、分享页。
- 确定基础技术栈:
  - Next.js App Router + TypeScript
  - FastAPI + Python
  - PostgreSQL + PostGIS + pgvector
  - Redis + 异步 worker
  - 高德地图 JS API 2.0 和 Web 服务 API
  - 豆包和 Qwen 通过 `LLMGateway` 可切换
- 完成架构文档:
  - `AGENTS.md`
  - `docs/product/product-brief.md`
  - `docs/architecture/system-architecture.md`
  - `docs/architecture/technology-stack.md`
  - `docs/architecture/ai-planning-pipeline.md`
  - `docs/architecture/data-model.md`
  - `docs/architecture/api-contracts.md`
  - `docs/architecture/frontend-ux.md`
  - `docs/architecture/llm-provider-gateway.md`
  - `docs/architecture/architecture-review-2026-07-05.md`
  - `docs/operations/reliability-security-performance.md`
  - `docs/adr/0001-foundation-stack.md`
  - `docs/adr/0002-llm-provider-gateway.md`
- 初始化 Git 仓库。
- 初始化 pnpm monorepo。
- 创建 `apps/web` Next.js 前端:
  - 地图工作台首页。
  - AI 对话面板。
  - mock 2D/3D 地图切换。
  - 每日路线和景点详情。
  - 分享页 `/s/[slug]`。
- 创建 `apps/api` FastAPI 后端:
  - `/health`
  - `/api/conversations`
  - `/api/conversations/{id}/messages`
  - `/api/planning-jobs/{id}`
  - `/api/itinerary-versions/{id}`
  - `/api/itinerary-versions/{id}/share`
  - `/api/share/{slug}`
- 创建 `packages/shared`:
  - 共享 TypeScript schema。
  - 武汉 3 日 mock itinerary JSON。
- 创建 `packages/map-core`:
  - 地图 provider 抽象接口。
- 创建 `infra/docker/docker-compose.yml`:
  - PostgreSQL + pgvector/PostGIS。
  - Redis。
- 创建 `infra/migrations/0001_initial_schema.sql` 初版迁移草案。
- 创建 LLM provider gateway 后端骨架:
  - `mock`
  - `qwen`
  - `doubao`
  - fixed/fallback 模式入口。

## 未开始

- 接入高德地图和路线服务。
- 接入真实豆包/Qwen provider。
- 建立真实数据库 repository 和 Alembic 迁移。
- 编写前端组件测试和 E2E 测试。
- 建立 AI 工具调用真实服务。
- 建立生产部署流水线。

## 下一步建议

1. Phase 2: 接入高德地图 JS API provider，并保留 mock map fallback。
2. 接入高德 Web 服务 POI/路线 API，建立服务端缓存。
3. 实现 QwenProvider 和 DoubaoProvider 的真实 smoke test。
4. 增加 `validate_itinerary` 业务校验服务。
5. 增加 SSE planning job 状态流。
6. 建立 Alembic 迁移和 PostgreSQL repository。

## 本轮验证

- `corepack pnpm install`: 通过。
- `corepack pnpm typecheck`: 通过。
- `corepack pnpm build`: 通过。
- `apps/api/.venv/bin/python -m pytest`: 3 passed。
- `apps/api/.venv/bin/python -m compileall app`: 通过。
- `GET http://127.0.0.1:3000/`: 200。
- `GET http://127.0.0.1:3000/s/wuhan-3-days-mock`: 200。
- `GET http://127.0.0.1:8000/api/itinerary-versions/mock-wuhan-3-days`: 200。
- `POST http://127.0.0.1:8000/api/conversations/conv_test/messages`: completed。

## 开放问题

- 是否优先部署在国内云环境，还是先使用海外开发部署。
- 是否已有高德开放平台 Key。
- 是否已有阿里云百炼 Qwen API Key。
- 是否已有火山方舟豆包 API Key 和 endpoint/model id。
- 是否需要用户登录，还是 MVP 先用匿名 session。
- 多媒体内容来源是先人工精选，还是接入授权内容源。
- 分享页是否需要密码或仅链接可见。

## 风险清单

- 中国地图坐标系、服务条款和 key 限制需要尽早确认。
- 评价和多媒体内容涉及版权与授权，不建议抓取未授权内容。
- 3D 地图能力在不同 provider 上差异很大，需要先定义 MVP 级别。
- AI 规划容易幻觉，必须通过后端工具和 schema 校验约束。
- 路线耗时、开放时间、票价具有时效性，需要 TTL 和来源展示。
