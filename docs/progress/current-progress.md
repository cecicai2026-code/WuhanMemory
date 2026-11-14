# Current Progress

最后更新: 2026-11-15

## 当前阶段

板块 0（准备）已完成。板块 1 在 2026-11-15 拆成两半：

- **板块 1A（正在做）**：界面外壳、地图工作台 `/map` 的布局、地点档案的普通网页版（`/places` 和 `/places/[id]`）、`/compare` 和 `/trips` 的空页面，删除旧的浅色 mock 界面。不用 three.js。
- **板块 1B（板块 5 完成之后）**：把立体三幕（胶卷、晾片、纸页）和首页桌面场景搬进正式网站。

拆的原因：文书里写的功能（数据质量规则、千问和豆包切换、行程校验、双模型对比）一个都还没开始，要先保证它们做出来。

做的顺序：0 → 1A → 2 → 3 → 4 → 5 → 1B → 6 → 7。分板块计划见 `docs/kickoff/claude-code-kickoff.md`。

板块 1A 在分支 `block-1a-shell` 上做。

## 板块 0 完成情况

- [x] 读现有代码，列出保留和重写的部分（结论见 `docs/progress/dev-log.md` 2026-11-14）。
- [x] ADR 0003：数据存储改用 JSON 种子文件 + SQLite，不使用 Redis。
- [x] 环境变量模板：`apps/api/.env.example` 和 `apps/web/.env.example`。
- [x] Cecilia 已申请并填好 key：千问、豆包（含 endpoint ID）、高德 JS key、安全密钥、Web 服务 key。只检查过格式，还没有真实调用验证。
- [x] 设计规范 `docs/design/design-system.md` v3（"暗房桌面"风格），方向已由 Cecilia 确认。
- [x] 地点档案三幕的立体样片：`docs/design/prototypes/` 下的 `darkroom-rolls.html`、`darkroom-line.html`、`darkroom-page.html`，三幕已连通，Cecilia 已确认。
- [ ] Cecilia 确认 `WuHan-Memory` 老仓库泄露过的高德 key 已重置。

## 代码现状

仓库里的网站代码仍是 2026-07-05 的 Phase 1 骨架，板块 0 没有改网站代码。`docs/design/prototypes/` 里的样片是独立的设计稿（单个网页加 three.js），不属于网站代码。

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

## 怎么看样片

样片要通过本地网址打开（三个页面共用模块文件，直接双击打不开）。在 Mac 终端运行下面的命令，再用浏览器打开 `http://localhost:4173/darkroom-rolls.html`：

```bash
cd ~/WuhanMemory-project2 && python3 -m http.server 4173 --bind 127.0.0.1 --directory docs/design/prototypes
```

看完后在终端按 Ctrl+C 停止。需要联网（加载 three.js）。

## 其余页面的样片（板块 1B 的依据）

2026-11-15 把分支 `design/prototype-scenes` 合进了 main。`docs/design/prototypes/` 里新增六个样片和共用的 `kit.js`、`kit.css`：

| 样片 | 对应页面 |
|---|---|
| `darkroom-desk.html` | 首页（桌面） |
| `darkroom-map.html` | 地图工作台（灯箱） |
| `darkroom-compare.html` | 模型对比（两台打字机） |
| `darkroom-trips.html` | 我的行程（笔记本） |
| `darkroom-card.html` | 分享页（明信片） |
| `darkroom-plan.html` | 填单（规划前的输入页，设计规范里还没有这一幕） |

这六个样片 Cecilia 还没有逐个确认。板块 1B 开工时要处理：

- 多处用了红色手写字（首页的入口链接、对话纸上用户的话、"再冲洗一份？"、填单的"还想说"），和设计规范"手写字只用蓝灰色、只出现在纸面上"不一致。
- 对比样片的评分卡上有写死的"通过 / 未通过"章，只演示样子，不能带进正式网站。
- 都没有手机版；字体用的是 Google Fonts；对话和填单的选项画在贴图上，不能用键盘操作。
- 填单幕要不要采用、放在哪条路径，由 Cecilia 决定。

工作区 `.claude/worktrees/prototype-scenes` 保留，没有删除。

## 下一步

板块 1A。分几步做、每步能看到什么，开工时由 Claude 列出、Cecilia 确认后再写代码。新增依赖只装 1A 用得上的（字体），`three.js`、`@react-three/fiber`、`motion`、`lenis` 留到板块 1B 再确认。

## 开放问题

- 首页各章节的文案和首屏备用图。
- 网站最终怎么让别人打开（板块 7 决定）。
