# Architecture Review 2026-07-05

## 结论

原架构方向可以继续推进 Phase 1。需要升级但不阻塞的点已经纳入文档和 Phase 1 实现边界:

- 新增 `LLMGateway`，正式支持豆包和 Qwen 可切换。
- AI 输出从“模型能力假设”升级为“provider 输出 + Pydantic 校验 + JSON repair + 业务校验”。
- Phase 1 使用 mock 地图和 mock 行程闭环，避免过早依赖高德、豆包、Qwen 的真实 key。
- 后续真实地图接入前，需要明确高德坐标系和 WGS84/PostGIS 存储转换策略。

## 检查项

### 前端

状态: 可继续。

- Next.js App Router 适合工作台和分享页。
- 地图工作台作为首屏符合产品目标。
- Phase 1 应避免过度复杂的地图 SDK 接入，先用 mock map 验证交互和数据结构。

建议:

- 地图组件从第一天就只吃 `MapPoi` 和 `MapRoute` 类型。
- 真实高德 provider 只替换渲染层，不改变 itinerary 数据结构。

### 后端

状态: 可继续。

- FastAPI + Pydantic 适合 AI 编排、schema 校验和 provider 适配。
- 异步 job 设计合理，但 Phase 1 可先用同步 mock job 简化闭环。

建议:

- API 层不要暴露 provider 私有字段。
- LLM gateway 和 planning service 要分层，避免业务逻辑和供应商 SDK 混在一起。

### 数据库

状态: 可继续。

- PostgreSQL + PostGIS + pgvector 适合长期需求。
- Phase 1 可以先不启动数据库，用 mock repository 保持接口边界。

建议:

- 初始迁移中明确坐标系字段和 source metadata。
- 动态信息必须带 `last_verified_at` 或 `expires_at`。

### AI

状态: 需要升级，已给出方案。

- 豆包和 Qwen 都通过 provider 适配层接入。
- 不把某家模型的 function calling 或 JSON mode 当成唯一能力。
- 结构化输出失败必须可观测、可重试、可降级。

### 地图

状态: 可继续。

- 高德作为武汉 MVP 地图 provider 是合理选择。
- Mapbox/Cesium 作为后续 provider 保留。

建议:

- Phase 1 的 mock map 不假装是真实 3D，只实现 2D/3D UI 状态切换和路线数据绑定。
- 接入高德前新增坐标转换和 key 权限检查任务。

### 安全与合规

状态: 可继续。

- API key 服务端保存原则正确。
- 用户分享页版本不可变设计正确。

建议:

- `.env.example` 明确区分 public key 和 server secret。
- 日志不记录完整用户隐私偏好和完整 prompt。

## Phase 1 验收边界

Phase 1 完成时应具备:

- monorepo 基础结构。
- Next.js 前端工作台页面。
- FastAPI 后端 mock API。
- 共享 TypeScript schema。
- 武汉 3 日游 mock itinerary。
- AI 对话输入到 itinerary 展示的端到端假数据闭环。
- 2D/3D 切换 UI、按天查看路线、景点详情、分享页。
- LLM provider 配置和后端接口骨架，不要求真实调用豆包/Qwen。

## 当前不建议做

- 直接接入真实支付或预约。
- 在没有授权内容源前抓取评价全文。
- 同时接入高德、Mapbox、Cesium 三套真实地图 SDK。
- 在 Phase 1 直接做复杂路线优化算法。
