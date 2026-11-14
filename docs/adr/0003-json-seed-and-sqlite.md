# ADR 0003: 数据存储改用 JSON 种子文件 + SQLite，暂不使用 Redis

日期: 2026-11-14

## 状态

Accepted。

取代 ADR 0001 中的两条决定：

- "Database: PostgreSQL + PostGIS + pgvector"
- "Cache and jobs: Redis + async worker"

ADR 0001 的其余决定（Next.js、FastAPI、高德地图、结构化输出加后端校验、monorepo）不变。

## 背景

- 开发用的电脑没有安装 Docker，ADR 0001 选定的 PostgreSQL + PostGIS + pgvector 和 Redis 在本地都跑不起来。
- 项目由一个人开发，景点由负责人逐条核实后录入，数量是几十个的量级。
- 项目规则要求每个景点有坐标和来源，会变的信息带核实时间和过期时间。这些资料需要能逐行审阅、能看到修改历史。
- 路线结果要缓存并记录 `checkedAt` 和 `expiresAt`（板块 3），原计划放在 Redis。

## 决策

### 1. 景点资料以 JSON 文件为准

- 每个景点一个文件，放在 `data/pois/*.json`，照片放在 `data/photos/<景点id>/`。
- 这些文件由负责人手写和核实，提交到 git。git 历史就是每条资料的修改记录。
- 具体字段在板块 2 确定，写入 `docs/architecture/data-model.md`。

### 2. 运行时用 SQLite

- 使用 Python 标准库自带的 `sqlite3`，不需要安装任何服务。
- 数据库是一个本地文件，路径由环境变量 `DATABASE_URL` 指定，不提交到 git。
- 后端启动时把 `data/pois/*.json` 导入 SQLite。景点表可以随时删掉重建，JSON 文件才是原始资料。
- 行程、行程版本、分享链接、模型对比结果这些运行时产生的数据直接写入 SQLite。

### 3. 所有读写经过 repository 层

- 业务代码（规划链路、校验、接口）只调用 repository 的方法，例如"按 id 取景点"、"按区域和类别筛景点"、"保存行程版本"。
- SQL 语句只出现在 repository 的 SQLite 实现里。
- 以后换成 PostgreSQL 时，新写一套 repository 实现，业务代码不用改。

### 4. 不使用 Redis，缓存放在 SQLite 的表里

- 高德路线结果缓存在 SQLite 的一张表中，每条记录带 `checkedAt` 和 `expiresAt`。
- 读取时先比较 `expiresAt`，过期就重新请求高德。
- 缓存写在文件里，后端重启后仍然有效，可以少调用高德接口。
- 规划任务在请求内直接执行，不使用任务队列和独立 worker。

## 理由

- 零安装：SQLite 随 Python 自带，克隆仓库后不需要额外启动任何服务。
- 数据量小：几十个景点、单人使用，SQLite 足够。
- 资料可审阅：JSON 文件能逐行对比，适合"每条都要核实并记录来源"的工作方式。
- 可替换：repository 层把存储方式和业务逻辑隔开，和 `LLMGateway`、地图 provider 的做法一致。

## 影响

正向:

- 本地开发不依赖 Docker。
- 景点资料和代码一起做版本管理。
- 缓存不会因为重启丢失。

代价:

- 没有 PostGIS 的空间查询。两点之间的距离在 Python 里用经纬度公式计算，筛选附近景点时遍历全部景点。在几十个景点的规模下可以接受。
- 没有 pgvector 的向量检索。候选景点按区域、类别、标签筛选。
- SQLite 同一时间只允许一个写入，不适合多人同时使用的线上环境。
- 规划任务在请求内同步执行，耗时较长的请求会让用户等待，界面上需要显示进度。

## 替代方案

### 安装 Docker，继续用 PostgreSQL + PostGIS

功能最完整。缺点是要先装 Docker，每次开发前要启动容器，对目前的数据量来说没有必要。

### 只用 JSON 文件，不用数据库

最简单。缺点是行程、分享链接、对比结果需要频繁写入和按条件查询，用文件管理容易出错。

### 使用云端托管的 PostgreSQL

不需要 Docker。缺点是开发时依赖网络，需要多管理一个账号和连接密码。

## 保留但暂不使用的文件

- `infra/docker/docker-compose.yml`
- `infra/migrations/0001_initial_schema.sql`

这两个文件是 PostgreSQL 方案的产物，留在仓库里供以后参考，目前不参与运行。

## 以后换回 PostgreSQL 的条件

出现下面任意一种情况时重新评估：

- 网站要部署给多人同时使用。
- 景点数量增加到遍历计算距离明显变慢。
- 需要按语义检索景点内容（向量检索）。

做法：新写一套 PostgreSQL 的 repository 实现，把 SQLite 中的运行时数据导出再导入，景点资料仍然从 JSON 文件导入。
