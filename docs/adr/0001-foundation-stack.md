# ADR 0001: Foundation Stack

日期: 2026-07-05

## 状态

Accepted for MVP planning.

## 背景

项目需要构建一个基于地图的 AI 旅行规划 Web 应用。核心要求包括:

- AI 对话式规划。
- 2D/3D 地图动态展示。
- 景点、路线、交通、支付、历史文化、评价和拍照机位信息。
- 可分享网页行程。
- 后续 Codex 可以快速理解项目并持续开发。

## 决策

采用以下基础技术栈:

- Frontend: Next.js App Router + TypeScript。
- Backend: FastAPI + Python。
- Database: PostgreSQL + PostGIS + pgvector。
- Cache and jobs: Redis + async worker。
- Map provider for MVP: 高德地图 JS API 2.0 + 高德 Web 服务 API。
- AI design: 结构化输出 + 工具调用 + 后端校验。
- Repo shape: pnpm/Turborepo monorepo。

## 理由

- 武汉和中国境内旅游场景需要国内地图、POI、路线和公交数据，高德更适合 MVP。
- Next.js 适合同时承载交互工作台和分享页。
- FastAPI 与 AI 编排、Pydantic schema、地理数据处理和异步任务匹配度高。
- PostgreSQL + PostGIS + pgvector 能减少基础设施数量，同时支持关系、空间和向量检索。
- 地图 provider 抽象能避免被单一地图厂商锁死。

## 影响

正向:

- MVP 技术风险较低。
- 数据模型可支持长期演进。
- AI 输出可验证、可回放、可调试。
- 后续可扩展 Mapbox、Cesium 或其他地图服务。

代价:

- 前后端双栈增加工程复杂度。
- 需要维护地图坐标系和 provider 差异。
- 数据来源授权和缓存策略必须尽早设计。

## 替代方案

### 全栈 Next.js

优点是初期更简单。缺点是 AI 编排、异步 worker、空间数据和长期服务边界会更快变复杂。

### 直接使用 Mapbox/Cesium

全球 3D 表现更强。缺点是武汉本地 POI、路线、公交和国内可用性不如高德优先方案。

### 独立向量数据库

可扩展性强。MVP 阶段会增加部署和运维成本，先用 pgvector 更稳妥。

## 后续检查点

- 接入真实高德 Key 后验证 2D/3D 切换、路线规划和 POI 查询质量。
- 完成 mock 原型后评估 FastAPI 与 Next.js 的接口复杂度。
- 内容规模超过 pgvector 单库舒适范围时，再评估独立向量数据库。
