# WuhanMemory

基于地图与 AI 对话的旅游行程规划 Web 应用。

用户输入目的地、时间、偏好和约束后，系统生成可交互地图行程、每日路线、景点信息、交通建议、支付与预约提示、多媒体介绍和可分享网页。首个重点城市是武汉。

## 文档入口

- Codex 工作说明: `AGENTS.md`
- 项目记忆: `PROJECT_MEMORY.md`
- 当前进度: `docs/progress/current-progress.md`
- 产品说明: `docs/product/product-brief.md`
- 系统架构: `docs/architecture/system-architecture.md`
- AI 规划流程: `docs/architecture/ai-planning-pipeline.md`
- 数据模型: `docs/architecture/data-model.md`

## 推荐开发方式

本项目建议采用 monorepo:

```text
apps/
  web/        # Next.js 前端
  api/        # FastAPI 后端
packages/
  shared/     # 共享 TypeScript 类型、JSON Schema、API client
  ui/         # 前端 UI 组件
  map-core/   # 地图 provider 抽象
infra/
  docker/     # 本地开发依赖
  migrations/ # 数据库迁移
docs/
```

## 当前状态

已完成系统框架设计，并进入 Phase 1 工程骨架。当前包含 Next.js 工作台、FastAPI mock API、共享 schema、mock 武汉 3 日行程和 LLM provider gateway 骨架。

## 本地运行

启用 pnpm:

```bash
corepack prepare pnpm@latest --activate
```

安装前端依赖:

```bash
corepack pnpm install
```

启动前端:

```bash
corepack pnpm dev:web
```

启动后端:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m uvicorn app.main:app --reload --port 8000
```

默认 LLM provider 是 `mock`。配置豆包或 Qwen 时复制 `.env.example` 并填写对应 key。

## 验证

```bash
corepack pnpm typecheck
corepack pnpm build
cd apps/api
.venv/bin/python -m pytest
```

Phase 1 当前默认不需要真实外部 API key。
