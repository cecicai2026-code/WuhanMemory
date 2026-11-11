# Technology Stack

## 推荐技术栈

### 前端

- Next.js App Router + TypeScript。
- React Server Components 用于分享页、详情页和非交互数据读取。
- Client Components 用于地图、对话输入、路线动画和拖拽编辑。
- Zustand 或 Jotai 管理前端地图交互状态。
- TanStack Query 管理 API 请求、缓存和重试。
- Tailwind CSS + Radix UI 或 shadcn/ui 建立一致的 UI 基础。

### 地图

- MVP: 高德地图 JS API 2.0。
- 中国境内路线/POI: 高德 Web 服务 API。
- 可选全球化: Mapbox GL JS。
- 可选深度 3D: CesiumJS。

选择理由:

- 武汉场景对国内 POI、公交/地铁、道路和地址解析质量要求高，优先高德。
- 2D/3D 切换先用高德 `viewMode` 和倾角能力实现，避免 MVP 过早引入双地图引擎。
- 通过地图 provider 抽象保留 Mapbox/Cesium 扩展空间。

### 后端

- FastAPI + Python。
- Pydantic 定义请求、响应和 AI 结构化输出。
- SQLAlchemy 或 SQLModel 操作数据库。
- Alembic 做数据库迁移。
- SSE 或 WebSocket 支持 AI 规划状态流。

选择理由:

- AI 编排、地理数据处理和异步任务更适合 Python 生态。
- FastAPI 的类型约束适合与前端共享 schema。
- 后端独立于 Next.js，便于长期扩展为复杂规划服务。

### 数据库

- PostgreSQL 作为主数据库。
- PostGIS 存储景点坐标、路线、空间索引和距离查询。
- pgvector 存储景点内容、历史文化、评价摘要和拍照机位的 embedding。
- Redis 缓存外部 API 响应、规划 job 状态和速率限制计数。

### AI

- 使用豆包和 Qwen，并通过 `LLMGateway` 支持 provider 切换。
- 本地开发和自动化测试默认使用 `mock` provider。
- 优先使用模型或 OpenAI 兼容接口提供的工具调用和 JSON 输出能力。
- 模型只负责推理、解释和生成候选方案。
- 真实 POI、路线、开放时间、天气和价格由后端工具查询。
- 规划结果保存为版本化 JSON，便于回放、调试和分享。

### 部署

- Web: Vercel、Cloudflare Pages 或自托管 Node。
- API: Docker 容器，部署到 Fly.io、Render、Railway、AWS、GCP、阿里云或腾讯云。
- 数据库: 托管 PostgreSQL，要求支持 PostGIS 和 pgvector。
- 对象存储: S3 兼容存储，用于分享页静态资产、多媒体缓存和导出文件。

## 环境变量

```text
DATABASE_URL=
REDIS_URL=
LLM_PROVIDER=mock
LLM_FALLBACK_PROVIDER=
LLM_PROVIDER_MODE=fixed
QWEN_API_KEY=
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
DOUBAO_API_KEY=
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=
AMAP_WEB_JS_KEY=
AMAP_WEB_SERVICE_KEY=
OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_ACCESS_KEY=
OBJECT_STORAGE_SECRET_KEY=
PUBLIC_APP_URL=
```

## 不建议的做法

- 前端直接持有 Web 服务私密 key。
- 业务代码直接绑定某一家 LLM provider。
- 让 AI 自己编造路线耗时、门票价格或营业时间。
- 用一个大 JSON 字段存完全部核心业务数据。
- 直接抓取第三方评价全文作为产品内容。
- 一开始同时接入多个地图引擎，导致 MVP 复杂度过高。

## 后续可替换点

- AI provider 通过 `AIProvider` 接口替换。
- 地图 provider 通过 `MapProvider` 接口替换。
- 路线 provider 通过 `RoutingProvider` 接口替换。
- 内容源通过 `ContentSource` 接口替换。
