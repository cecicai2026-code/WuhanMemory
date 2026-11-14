# Current Progress

最后更新: 2026-11-14

## 当前阶段

重做计划的板块 0（准备）基本完成，只差 Cecilia 对设计规范具体数值的最终确认。下一个是板块 1：新界面外壳和地点档案页。

分板块计划见 `docs/kickoff/claude-code-kickoff.md`。

## 板块 0 完成情况

- [x] 读现有代码，列出保留和重写的部分（结论见 `docs/progress/dev-log.md` 2026-11-14）。
- [x] ADR 0003：数据存储改用 JSON 种子文件 + SQLite，不使用 Redis。
- [x] 环境变量模板：`apps/api/.env.example` 和 `apps/web/.env.example`。
- [x] Cecilia 已申请并填好 key：千问、豆包（含 endpoint ID）、高德 JS key、安全密钥、Web 服务 key。只检查过格式，还没有真实调用验证。
- [x] 设计规范 `docs/design/design-system.md` v3 草案（"暗房桌面"风格，地点档案三幕：胶卷、晾片、纸页）。
- [ ] Cecilia 确认设计规范 v3。
- [ ] Cecilia 确认 `WuHan-Memory` 老仓库泄露过的高德 key 已重置。

## 代码现状

仓库里的代码仍是 2026-07-05 的 Phase 1 骨架，板块 0 没有改代码。

保留:

- `apps/api/app/services/llm/`：`LLMGateway` 和 provider 边界。
- `packages/map-core`：地图 provider 接口。
- `apps/api/app/main.py`、`core/config.py`、`schemas/itinerary.py`、`packages/shared/src/index.ts`：入口、配置和行程数据结构（景点字段要扩充）。
- monorepo 工程结构。

待重写或删除:

- `apps/web` 的全部界面和样式（浅色 mock 界面）。
- `apps/web/features/map/MockMap.tsx`（假地图）。
- `packages/shared/data/wuhan-three-day-itinerary.json`（内容是编的 mock 数据）。
- `apps/api/app/api/routes.py`、`services/planning/mock_planner.py`（全部返回同一份 mock）。
- `apps/api/tests/test_api.py`（断言的是 mock 内容）。

保留但暂不使用: `infra/docker/docker-compose.yml`、`infra/migrations/0001_initial_schema.sql`。

## 已知问题

- `apps/api/app/core/config.py` 还没有高德和数据库的配置字段，板块 2、3 添加。
- `docs/architecture/data-model.md` 里的表结构仍是 PostgreSQL 草案，板块 2 重写。
- `docs/architecture/frontend-ux.md` 只更新了页面结构的提示，板块 1 同步其余内容。

## 下一步

板块 1：按设计规范重做界面外壳、首页（桌面）、地图工作台布局（`/map`）、地点档案三幕。工作量比原计划大很多，开工时先商量分几步做。开工时需要确认设计规范第 14 节的待定事项：物件的精细程度和清单、各幕文案、周边美食的数据来源、新增依赖（`three.js`、`@react-three/fiber`、`motion`、`lenis`、字体），以及是否允许 Claude 自己启动本地服务器查看效果。

## 开放问题

- 首页各章节的文案和首屏备用图。
- 网站最终怎么让别人打开（板块 7 决定）。
