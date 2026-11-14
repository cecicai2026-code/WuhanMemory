# System Architecture

## 总体架构

```mermaid
flowchart LR
  User[User Browser] --> Web[Next.js Web App]
  Web --> API[FastAPI API]
  Web --> MapSDK[Map SDK Provider]
  API --> Planner[AI Planning Orchestrator]
  Planner --> LLMGateway[LLM Gateway]
  LLMGateway --> Doubao[Doubao Provider]
  LLMGateway --> Qwen[Qwen Provider]
  Planner --> Tools[Planning Tools]
  Tools --> Poi[POI and Content Services]
  Tools --> Routing[Routing Service]
  Tools --> Weather[Weather Service]
  Seed[(data/pois JSON 种子文件)] --> Repo[Repository 层]
  API --> Repo
  Repo --> DB[(SQLite：景点、行程、分享、缓存)]
  API --> ObjectStore[(Object Storage)]
```

## 推荐仓库结构

```text
apps/
  web/
    app/            每个页面一个文件夹，页面自己的组件和样式放在一起
    components/
      ui/           基础组件（按钮、纸、印章、输入框）
      shell/        外壳（四角标注、菜单、空页面）
    lib/            页面清单、景点数据入口
  api/
    app/
      api/
      core/
      models/
      repositories/
      services/
      workers/
      schemas/
packages/
  shared/
    schemas/
    types/
  ui/
  map-core/
infra/
  docker/
  migrations/
docs/
```

## 前端边界

前端负责:

- AI 对话输入、流式状态展示和缺失信息补问。
- 地图渲染、2D/3D 切换、路线动画、景点卡片和每日筛选。
- 行程时间线、交通段、预算、预约和支付提示展示。
- 分享页静态化或半静态化展示。

前端不负责:

- 直接调用私密第三方 API key。
- 自行做可信路线规划和开放时间校验。
- 将 AI 文本当作最终路线数据。

## 后端边界

后端负责:

- 用户会话和旅行规划请求管理。
- AI 编排、工具调用、结构化输出校验。
- POI、路线、天气、内容和媒体数据聚合。
- 行程版本管理、分享页生成和权限控制。
- 缓存、限流、审计、观测和错误恢复。

## 地图 Provider 抽象

使用 `packages/map-core` 定义统一接口:

```ts
export interface MapProvider {
  mount(container: HTMLElement, options: MapInitOptions): Promise<void>;
  setMode(mode: "2d" | "3d"): Promise<void>;
  renderPois(pois: MapPoi[]): void;
  renderRoute(route: MapRoute): void;
  focusBounds(bounds: MapBounds): void;
  destroy(): void;
}
```

MVP provider:

- `AmapProvider`: 高德 JS API 2.0，适合武汉和中国境内 POI、路线、公交、地理编码场景。

后续 provider:

- `MapboxProvider`: 更强的全球化视觉和 3D 建筑。
- `CesiumProvider`: 更强的真实三维地球、倾斜摄影和大型地理数据能力。

## 核心服务

### Conversation Service

- 保存用户消息、AI 消息、补问状态和偏好提取结果。
- 支持流式响应和规划任务状态轮询。

### Planning Orchestrator

- 将自然语言需求转成结构化约束。
- 通过 `LLMGateway` 调用豆包、Qwen 或 mock provider。
- 调用 POI、路线、天气、内容检索和预算工具。
- 生成候选路线，排序后输出可验证的 itinerary JSON。

### LLM Gateway

- 对业务层提供统一 `complete_json` 和 `complete_with_tools` 接口。
- 支持 `qwen`、`doubao` 和 `mock` provider。
- 支持 fixed、fallback 和 shadow provider 选择策略。
- 统一结构化输出校验、错误码、token usage、latency 和 trace。

### POI Service

- 统一外部 POI 查询、内部 POI 缓存和人工精选内容。
- 维护坐标、分类、营业时间、门票、预约、适合人群、标签和来源。

### Routing Service

- 调用高德路径规划 Web API。
- 缓存起终点和交通方式的路线结果。
- 对路线耗时设置过期时间，因为道路和算法会变化。

### Content Service

- 为景点生成或聚合简介、历史文化、拍照机位、注意事项和评价摘要。
- 所有生成内容保留来源、更新时间和置信度。

### Share Service

- 将某个行程版本发布为只读分享页。
- 支持公开链接、过期时间、撤回和访问统计。

## 典型数据流

1. `POST /api/conversations` 创建对话。
2. `POST /api/conversations/{id}/messages` 发送用户需求。
3. API 创建 `planning_job`，返回 job id 并流式返回理解过程。
4. Worker 执行 AI 规划和工具调用。
5. 规划结果写入 `itinerary_versions`。
6. 前端通过 WebSocket/SSE 或轮询拿到结构化结果。
7. 地图层渲染 POI 点位、路线和每日行程。
8. 用户修改后生成新版本，不覆盖旧版本。

## 可靠性原则

- AI 输出必须经过 JSON Schema 校验。
- LLM provider 切换不能改变业务层 schema。
- 每个 POI 必须有坐标、来源和更新时间。
- 每个交通段必须有起终点、交通方式、预计耗时和来源。
- 路线、开放时间、价格等动态信息需要 TTL。
- 分享页绑定 itinerary version，避免后续编辑影响已分享链接。
