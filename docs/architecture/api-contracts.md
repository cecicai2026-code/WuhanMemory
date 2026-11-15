# API Contracts

## 风格

- 外部 API 使用 REST + JSON。
- 长任务状态使用 SSE 或 WebSocket，MVP 可先用轮询。
- 请求和响应 schema 使用 OpenAPI + Pydantic 生成，前端同步生成 TypeScript 类型。
- 所有写操作返回资源 id，复杂结果通过查询接口读取。

## 现在已经实现的接口

> 2026-11-15（板块 2）：景点接口已实现。对话、规划、行程、分享接口原来返回同一份编出来的 mock 行程，已删掉；
> 在板块 5、7 实现之前，`POST /api/conversations/{id}/messages` 返回 501，查询规划任务、行程和分享页返回 404。
> 下面"主要接口"一节是这些接口的设计草案。
>
> 2026-11-15（板块 3）：路线接口和高德安全密钥代理已实现，见"路线"和"高德安全密钥代理"两节。
>
> 2026-11-15（板块 4）：模型接口已实现，见"模型"一节。
>
> 2026-11-15（板块 5）：对话、规划任务、行程版本的接口已实现，见"对话和规划"一节；临时的 `POST /api/llm/ping` 已删掉。
> 分享接口在板块 7 之前，发布返回 501，查询返回 404。
>
> 2026-11-15（板块 7）：分享接口和我的行程接口已实现，见"分享（板块 7）"和"我的行程（板块 7）"两节；下面草案里的旧"发布分享页""获取分享页"已删掉。
>
> 2026-11-15（中英双语，ADR 0009）：全部接口按请求的语言写给人看的话，见下面"语言"一节。

## 语言（中英双语，ADR 0009）

每个请求的语言按这个顺序认，都没有时是中文（`app/core/lang.py`）：

1. 查询参数 `?lang=zh` / `?lang=en`（网站在服务器端取数据时用，例如 `GET /api/pois?lang=en`）
2. 请求头 `X-Lang: en`（浏览器里调接口时用，`apps/web/lib/planning-client.ts`）
3. cookie `wm-lang`（网站上"中 / EN"切换时写的，经网站转发的请求自带）

跟着语言变的：

- 景点接口：`lang=en` 时名字、区、标签、地址、简介、历史、开放时间和票价的说明、拍照机位、周边美食、照片说明换成 `data/pois/en/` 里的译文；没有译文或译文作废的条目保留中文。来源标题、核实备注不翻。字段和结构不变。
- 出错时的 `detail`、规划任务和对比任务的步骤名 `stages[].label`、一轮方案的侧重名 `plans[].label` 和对比表、历次对比的 `emphasisLabel`、我的行程的 `emphasisLabel`：按这次请求的语言现写。
- 发消息（`POST /api/conversations/{id}/messages`）和发起对比（`POST /api/comparisons`）：任务按发请求时的语言跑，反问、校验说明、按默认补的设置、交通方式说明、对比表都用这种语言；英文时让模型用英文写 `title`、`theme`、`reason`。存下的行程版本、对话消息、对比结果是生成时的语言，以后不再变。
- 路线接口：线路名（"轨道交通 2 号线" → "Metro Line 2"、"14 路" → "Bus 14"）和程序写的固定说法换成英文；高德给的其他名字不变。
- 区筛选 `GET /api/pois?district=` 仍用中文区名。

### 景点列表

```http
GET /api/pois
GET /api/pois?district=武昌区&category=museum
```

Response（`PoiListOut`，前端类型 `PoiList`）：

```json
{
  "asOf": "2026-11-15",
  "pois": [
    {
      "id": "景点id",
      "name": "名称",
      "district": "所在区",
      "category": "类别",
      "tags": [],
      "location": { "lng": 0, "lat": 0, "coordSystem": "GCJ-02" },
      "status": "pending",
      "counts": { "verified": 6, "pending": 3, "expired": 0, "missing": 3 },
      "coverPhoto": null
    }
  ]
}
```

- `asOf`：状态按哪一天算的（武汉时间的今天）。
- `status`：`verified` / `pending` / `expired`，规则见 `data-model.md` 第 5 节。
- `counts`：各状态的信息条数，程序数出来的。拍照机位、周边美食空着时各算一条 `missing`。
- 只返回通过数据检查、已导入 SQLite 的景点，按文件名排序。

### 景点详情

```http
GET /api/pois/{id}
```

Response（`PoiDetailResponse`）：`{ "asOf": "...", "poi": PoiDetail }`。`PoiDetail` 在列表字段之外还有：

- `sources`：全部来源；
- `address`、`intro`、`history`、`openingHours`、`ticket`、`reservation`、`payment`、`transport`、`recommendedDurationMinutes`、`bestTime`：每项都是

```json
{
  "value": "...",
  "verification": "placeholder",
  "status": "pending",
  "source": { "id": "official-site", "type": "official-site", "title": "...", "url": "https://...", "accessedAt": "2026-11-15" },
  "extraSources": [],
  "lastCheckedAt": "2026-11-15",
  "expiresAt": "2027-02-13",
  "todo": null,
  "note": null
}
```

- `operatingStatus`：也是上面这种结构，`value` 是 `{ code, note, reopenExpected, reopenNote }`；资料里没写（正常开放）时为 `null`。列表接口的每个景点也带这一项；
- `photoSpots`、`food`：上面这种结构的数组；
- `reviews`：署名评价；
- `photos`：照片，多了 `placeholder`、`url`（相对于后端地址，例如 `/media/photos/<id>/a.jpg`；占位照片不在本机时为 `null`）和 `thumbUrl`（800 宽的缩略图，见下面；`url` 为 `null` 时也是 `null`，板块 1B 加的）。

没有这个景点时返回 404：`{ "detail": "没有这个景点：<id>" }`。

### 照片文件

```http
GET /media/photos/{id}/{file}
GET /media/photos-placeholder/{id}/{file}
GET /media/thumbs/{width}/{photos|photos-placeholder}/{id}/{file}
```

照片缩略图（板块 1B，2026-11-15）：`width` 只能是 480 或 800；只缩小不放大，统一给 JPEG（质量 80），手机照片按拍摄方向转正。第一次被要时用 Pillow 生成，存在 `data/thumbs/`（不进 git，可以随时删），以后直接给缓存，原图比缓存新时重新生成；浏览器缓存一天。参数不对、原图不存在或不是图片、后端没装 Pillow 时返回 404（网页的立体场景这时退回取原图）。公开模式下 `photos-placeholder` 的缩略图也是 404。代码在 `app/services/thumbnails.py`、`app/api/media.py`，测试 `tests/test_thumbnails.py`。

### 路线：三种交通方式对比

```http
GET /api/routes/compare?from=<起点景点id>&to=<终点景点id>
```

依次查步行、公交地铁、驾车，返回：

```json
{
  "origin": { "id": "yellow-crane-tower", "name": "黄鹤楼", "location": { "lng": 114.302467, "lat": 30.544649 } },
  "destination": { "id": "hubu-alley", "name": "户部巷", "location": { "...": "..." } },
  "routes": [
    {
      "mode": "walk",
      "status": "ok",
      "durationMinutes": 9,
      "distanceMeters": 699,
      "cost": { "kind": "free", "amountCny": 0, "note": "步行不花钱" },
      "summary": null,
      "reason": null,
      "polyline": [{ "lng": 114.302467, "lat": 30.544649 }],
      "source": { "provider": "amap", "api": "/v5/direction/walking" },
      "checkedAt": "2026-11-15T21:30:00+08:00",
      "expiresAt": "2026-12-15T21:30:00+08:00",
      "cache": "fresh",
      "warning": null,
      "error": null
    }
  ]
}
```

（上面的数字只是说明格式。）

| 字段 | 说明 |
|---|---|
| `mode` | `walk` 步行、`transit` 公交地铁、`drive` 驾车 / 打车 |
| `status` | `ok` 有方案；`none` 高德没给方案（例如两地太近没有公交），看 `reason`；`error` 没查成，看 `error` |
| `walkingDistanceMeters` | 要走的路（米）：步行是全程距离；公交地铁是换乘、进出站的步行（高德 transit 返回的 `walking_distance`，没有时把每段步行距离加起来）；打车是 0。板块 5B 加的，旧缓存没有时为 null，`corepack pnpm routes:prewarm` 从缓存的原始返回里补 |
| `cost.kind` | `free` 步行；`fare` 公交地铁票价（高德估算）；`taxi` 打车费（高德估算），自驾过路费写在 `note` 里 |
| `summary` | 公交地铁坐哪几条线，例如"地铁2号线 → 地铁4号线" |
| `polyline` | 路线折线，GCJ-02 |
| `checkedAt`、`expiresAt` | 向高德查询的时间和过期时间（武汉时间）。步行 30 天、公交地铁 7 天、驾车 1 天 |
| `cache` | `fresh` 刚查的；`cached` 缓存里还没过期；`stale` 缓存过期了、重查又失败，先返回旧结果，`warning` 写原因 |
| `error.code` | `amap-key-missing`（没配 Web 服务 key）、`amap-unreachable`（连不上高德）、`amap-<高德错误码>`，例如 `amap-10003` 当天次数用完、`amap-10021` 被限流 |

某一种方式没查成不影响其他两种，整个接口仍返回 200。起点和终点是同一个景点返回 400，景点不存在返回 404。

只接受景点 id，不接受任意坐标。前端不直接调用高德 Web 服务，Web 服务 key 只在后端。

### 路线：只查一种

```http
GET /api/routes?from=<id>&to=<id>&mode=walk|transit|drive
```

返回上面 `routes` 里的一项。板块 5 的行程直接在后端调用同一个 `RouteService`。

### 高德安全密钥代理

```http
GET|POST /_AMapService/{path}
```

给浏览器里的高德 JS API 用（`window._AMapSecurityConfig.serviceHost`），不是给页面代码调用的。照高德官方的 nginx 示例：`/_AMapService/v4/map/styles` 转到 `https://webapi.amap.com/v4/map/styles`，其余转到 `https://restapi.amap.com/`，转发时在查询参数末尾加上 `jscode=<安全密钥>`。只接受 `Referer` 或 `Origin` 是 CORS 白名单里网址的请求（否则 403）；没配安全密钥返回 503，连不上高德返回 502。

### 模型：有哪些可以选

```http
GET /api/llm/providers
```

```json
{
  "defaultProvider": "qwen",
  "providers": [
    { "id": "qwen", "label": "通义千问", "configured": true, "isDefault": true },
    { "id": "doubao", "label": "豆包", "configured": false, "isDefault": false }
  ]
}
```

- `configured`：`apps/api/.env` 里这个模型的 key 和模型名（豆包是接入点 ID）都填了。只说有没有，不返回 key，也不返回接入点 ID。
- `defaultProvider`：`.env` 里 `LLM_PROVIDER` 指的模型。填的不是 `qwen` 或 `doubao` 时是 `null`。
- 这个接口不调用模型。"已配置"不等于"key 有效"，key 对不对要真的调用一次才知道（冒烟测试，或在 `/map` 上发一条消息）。

### 模型：出错时

规划在后台任务里调用模型，所以模型出错不是 HTTP 错误，而是写在规划任务的 `error` 上（见下面"查询规划任务"）：

```json
{ "code": "rate_limited", "message": "豆包限流（HTTP 429，…）", "retryable": true, "provider": "doubao" }
```

| `code` | 含义 | 网关会不会重试 |
|---|---|---|
| `unknown_provider` | 指定的模型不在清单里 | 不会 |
| `not_configured` | 没配 key 或模型名 | 不会 |
| `invalid_key` | key 无效或没有权限 | 不会 |
| `bad_config` | 模型名或接入点填错 | 不会 |
| `quota_exhausted` | 额度用完或账户欠费 | 不会 |
| `content_blocked` | 被对方的内容审核拦下 | 不会 |
| `bad_request` | 对方认为请求有问题 | 不会 |
| `rate_limited` | 限流 | 会，先等一会儿 |
| `timeout` | 规定时间内没有回答 | 会 |
| `upstream_error` | 对方服务器出错或网络断开 | 会 |
| `bad_output` | 让模型重答一次后输出仍不合格 | 已经重答过一次 |
| `provider_error` | 对方返回的结构和预期不一样 | 不会 |
| `internal_error` | 规划链路里程序自己出错（不是模型的错），详情只在后端日志里 | 不会 |

`retryable` 说的是这种错值不值得过一会儿再试；到前端时网关自己的重试已经用完了。`message` 里不会出现 key。

## 对话和规划（板块 5）

代码：`apps/api/app/api/planning.py`，数据结构 `apps/api/app/schemas/api.py`、`itinerary.py`、`planning.py`，前端类型 `packages/shared/src/planning.ts`。链路见 `ai-planning-pipeline.md`。

### 新建对话

```http
POST /api/conversations
```

Request：`{ "city": "武汉" }`（可以省略）。Response：`{ "conversationId": "conv_…", "status": "active" }`。

### 查看对话

```http
GET /api/conversations/{conversationId}
```

```json
{
  "conversationId": "conv_…",
  "preferences": { "days": 2, "startDate": null, "dateUndecided": true, "pace": null, "interests": ["历史文化"], "budget": null, "party": null, "transport": "metro", "mustVisit": [], "avoid": [], "notes": null },
  "itineraryId": "itin_…",
  "messages": [
    { "id": 1, "role": "user", "content": "武汉两天……", "createdAt": "…", "kind": null, "provider": null, "itineraryVersionId": null },
    { "id": 2, "role": "assistant", "content": "排了 3 份方案，展示 2 份……", "createdAt": "…", "kind": "itinerary", "provider": "qwen", "itineraryVersionId": "ver_…", "planningRoundId": "round_…" }
  ]
}
```

- `preferences`：到目前为止抽到的偏好，没说的是 null 或空列表。
- `kind`（回复才有）：`question` 反问；`itinerary` 带出了行程（通过或有警告）；`failed` 修正后仍未通过；`error` 模型或程序出错。
- `planningRoundId`（板块 5B）：这条回复带出的那一轮方案，用"获取一轮方案"取；`itineraryVersionId` 是这一轮第一份展示的方案（一份都没展示时是第一份存下的）。板块 5 存的旧回复没有 `planningRoundId`，只有一个版本。
- 前端刷新页面后用它接着显示对话。没有这段对话时 404。

### 发送消息

```http
POST /api/conversations/{conversationId}/messages
```

```json
{ "content": "武汉两天，喜欢历史和美食，坐地铁", "provider": "doubao" }
```

- `provider`：界面上选中的模型，不填用 `.env` 的默认模型。链路里的每一次模型调用都用它。
- 返回 202：`{ "messageId": 3, "planningJobId": "job_…", "status": "queued" }`。规划在后台跑，用下面的接口查进度。
- 对话不存在 404；内容是空的 400；这段对话上一条还在规划中 409。

### 查询规划任务

```http
GET /api/planning-jobs/{jobId}
```

前端每秒问一次，直到 `status` 是 `completed` 或 `failed`。

```json
{
  "jobId": "job_…",
  "conversationId": "conv_…",
  "status": "completed",
  "stage": "saving",
  "stages": [
    { "id": "understanding", "label": "理解需求" },
    { "id": "selecting", "label": "从景点库挑候选" },
    { "id": "generating", "label": "模型排三份方案" },
    { "id": "routing", "label": "查真实交通时间" },
    { "id": "validating", "label": "校验" },
    { "id": "repairing", "label": "把错误交给模型修正" },
    { "id": "routing", "label": "查真实交通时间" },
    { "id": "validating", "label": "校验" },
    { "id": "saving", "label": "保存" }
  ],
  "kind": "itinerary",
  "reply": "排好了（第一版有错误，交给模型修正过一次）……",
  "provider": "doubao",
  "itineraryVersionId": "ver_…",
  "planningRoundId": "round_…",
  "error": null
}
```

- `stages`：链路真的走过的步骤，按顺序，最后一个是正在做的（或最后做完的）。`repairing` 和第二遍的 `routing`、`validating` 只在第一轮有错误时出现；反问时只有 `understanding`。
- `status`：`failed` 只表示任务本身出错（模型调用失败等），看 `error`，结构见"模型：出错时"。**行程没通过校验时任务是 `completed`，`kind` 是 `failed`**，`itineraryVersionId` 照样有，界面只显示问题清单。
- 板块 5B：一次规划是一轮三份方案，`planningRoundId` 是这一轮；三份同时排，步骤只记一次（例如 `generating` 只出现一次，表示三份一起在排）。`repairing` 在任一份有错误时出现。
- 任务只存在内存里，后端重启后查不到（404），但已经存进 SQLite 的消息和行程不丢。

### 获取行程版本

```http
GET /api/itinerary-versions/{versionId}
```

返回 `ItineraryVersion`（后端 `apps/api/app/schemas/itinerary.py`）：

| 字段 | 说明 |
|---|---|
| `id`、`itineraryId`、`versionNumber`、`createdAt` | 同一份行程的版本从 1 递增；版本存下后不再修改 |
| `title`、`city` | |
| `frame` | `{ days, startDate, pace }`：校验时用的天数、开始日期（未定时 null）、节奏 |
| `preferences` | 抽到的偏好 |
| `defaultsUsed` | 程序替用户补上的默认值，例如"节奏：适中（你没说，按默认）"，界面上要列出来 |
| `days[]` | `{ dayNumber, date, theme, stops[], legs[] }` |
| `days[].stops[]` | `{ poiId, name, district, category, location, arrive, leave, reason, facts }`；`facts` 是生成时景点库里的 `openingHours`、`reservation`、`ticket`、`payment`、`recommendedDurationMinutes`，结构和景点详情里的一条信息一样（带 `status`：已核实、待确认、已过期、待补充） |
| `days[].legs[]` | `{ fromPoiId, toPoiId, route, choice }`；`route` 是路线接口的一条 route（高德的真实时间、折线、查询时间、缓存状态），`choice` 是为什么选这种方式 |
| `validation` | `{ status, issues[] }`；`status` 是 `passed` / `warning` / `failed`；每条 issue 是 `{ level, code, message, dayNumber, poiId, fields }`，code 的全部取值见 `ai-planning-pipeline.md` |
| `planner` | `{ provider, providerLabel, model, rounds, firstRoundStatus, firstRoundErrors }`：用的模型、对方返回的真实模型名、生成了几轮（2 表示修正过一次）、第一轮的结果 |
| `draft` | 模型最后一轮的原始输出。没通过时 `days` 里可能缺了不存在的景点，`draft` 里原样留着 |
| `dataAsOf` | 资料状态按哪一天算的 |
| `emphasis` | 板块 5B：这份方案的侧重，`classic` 经典必去 / `relaxed` 轻松少走路 / `culture` 深度文化；之前的版本为 null |
| `metrics` | 板块 5B：程序算的数字（景点、交通分方式、步行距离、每站门票和合计、每天几点结束、校验条数），计算规则见 `ai-planning-pipeline.md` 的"比较"；之前的版本为 null |

没有这个版本时 404。

- 板块 6C：版本里多了 `outline`（模型给的行程：每天 `start`，每站 `poiId`、`stayMinutes`、`reason`）和 `firstOutline`（修正过时模型的第一版）。`days` 里的到达、离开时间是程序按真实交通推出来的。之前存的版本没有这两项。

### 获取一轮方案（板块 5B）

```http
GET /api/planning-rounds/{roundId}
```

```json
{
  "id": "round_…",
  "conversationId": "conv_…",
  "roundNumber": 1,
  "provider": "qwen",
  "providerLabel": "通义千问",
  "defaultsUsed": ["节奏：适中（你没说，按默认）"],
  "plans": [
    { "emphasis": "classic", "label": "经典必去", "itineraryId": "itin_…", "versionId": "ver_…", "shown": true, "removedReason": null },
    { "emphasis": "relaxed", "label": "轻松少走路", "itineraryId": "itin_…", "versionId": "ver_…", "shown": false,
      "removedReason": "和「经典必去」几乎一样：用到的景点只差 1 个，每天结束时间相差不到 1 小时" },
    { "emphasis": "culture", "label": "深度文化", "itineraryId": "itin_…", "versionId": "ver_…", "shown": true, "removedReason": null }
  ],
  "versions": [ "…展示的两份 ItineraryVersion…" ],
  "comparison": {
    "labels": ["经典必去", "深度文化"],
    "rows": [
      { "key": "places", "label": "用了哪些景点", "texts": ["黄鹤楼、湖北省博物馆、东湖听涛", "黄鹤楼、昙华林、湖北省博物馆"], "values": [null, null], "note": null },
      { "key": "transportMinutes", "label": "交通时间合计", "texts": ["62 分钟", "48 分钟"], "values": [62, 48], "note": "高德查到的时间，没查到的段没算进去" },
      { "key": "tickets", "label": "门票（每人）", "texts": ["70 元", "70 元"], "values": [70, 70], "note": "…" }
    ]
  }
}
```

- `plans`：按"经典必去 → 轻松少走路 → 深度文化"的顺序。`shown` 为 false 的是没展示的，`removedReason` 写着为什么（几乎一样、没通过校验、模型没排出来）。模型没排出来的没有版本（`versionId` 为 null）。
- `versions`：只有展示的几份，顺序和 `plans` 里 `shown` 的一致。没展示的版本也存着，用 `GET /api/itinerary-versions/{id}` 取得到。
- `comparison`：展示的几份之间的对比表，每格是程序写好的文字（`texts`），能比大小的行另有 `values`。行的 key：`places`、`stopCount`、`transportMinutes`、`byMode`、`walkingMeters`、`tickets`、`end-day-1`…`end-day-N`、`validation`。一份都没展示时为 null。上面例子里的数字只是示意格式，不是真实结果。
- 没有这一轮时 404。

## 双模型对比（板块 6）

代码在 `apps/api/app/api/comparisons.py`，做法见 `ai-planning-pipeline.md` 的"双模型对比"和 ADR 0006。

### 发起对比

```http
POST /api/comparisons
```

```json
{ "request": "武汉两天，喜欢历史和美食，坐地铁，11 月 28 日出发", "emphasis": "classic" }
```

返回 202：`{ "jobId": "cjob_…", "status": "queued" }`。

- `emphasis`：`classic` 经典必去（默认）/ `relaxed` 轻松少走路 / `culture` 深度文化。
- 400：请求是空的、侧重不对、千问或豆包有一个没配置。409：上一次对比还在跑（一次只跑一个，免得重复花 token）。
- 后台：默认模型抽一次偏好，两边共用；千问和豆包同时排同一种侧重。调用模型 3 到 5 次。

### 查询对比任务

```http
GET /api/comparison-jobs/{jobId}
```

```json
{
  "jobId": "cjob_…",
  "status": "running",
  "request": "…",
  "emphasis": "classic",
  "stages": [{ "id": "understanding", "label": "理解需求（抽一次偏好，两边共用）" }],
  "sides": [
    { "provider": "qwen", "label": "通义千问", "stages": [{ "id": "selecting", "label": "从景点库挑候选" }, { "id": "generating", "label": "…" }] },
    { "provider": "doubao", "label": "豆包", "stages": [] }
  ],
  "comparisonId": null,
  "error": null
}
```

- `stages` 是共用的步骤（抽偏好、保存），`sides` 是每边各自走过的步骤，最后一步是 `done`。
- `status` 是 `completed` 时 `comparisonId` 有值。`failed` 时 `error.code` 是 `needs_days`（偏好里没有天数，请用户把天数写进请求）、模型的错误码（抽偏好时出错），或 `internal_error`。一边排行程时模型出错不算任务失败，写在那一边的结果里。
- 任务只在内存里，后端重启会丢（结果已经存进 SQLite 的不丢）。

### 历次对比

```http
GET /api/comparisons?limit=50
```

新的在前。每条：`id`、`createdAt`、`request`、`emphasisLabel`、`evalRequestId`（批量评测的请求 id，页面上发起的为 null）、`sides`（每边的 `providerLabel`、`model`、`error`、`firstPassed`、`finalPassed`；没排出来时两个 passed 为 null）。

### 获取一次对比

```http
GET /api/comparisons/{id}
```

```json
{
  "id": "cmp_…",
  "createdAt": "…",
  "request": "…",
  "preferences": { "days": 2, "startDate": "2026-11-28", "interests": ["历史文化", "美食"], "transport": "metro", "…": "…" },
  "preferencesSource": "extracted",
  "extractor": "qwen",
  "extractorCalls": { "callCount": 1, "…": "…" },
  "emphasis": "classic",
  "emphasisLabel": "经典必去",
  "defaultsUsed": ["节奏：适中（你没说，按默认）"],
  "sides": [
    {
      "provider": "qwen", "providerLabel": "通义千问", "model": "…", "versionId": "ver_…", "error": null,
      "quality": { "firstPassed": false, "firstErrorCount": 2, "firstErrorCodes": { "overlap": 1, "closed-day": 1 }, "repaired": true,
                   "finalPassed": true, "firstFabricatedPoiIds": [], "firstOffListPoiIds": [], "…": "…" },
      "plan": { "…5B 的 PlanMetrics…": "" },
      "calls": { "callCount": 2, "requestCount": 2, "modelMs": 0, "inputTokens": 0, "outputTokens": 0, "byTask": { "generate_itinerary": 1, "repair_itinerary": 1 }, "…": "…" },
      "wallMs": 0
    },
    { "provider": "doubao", "…": "…" }
  ],
  "diff": { "onlyLeft": [], "onlyRight": [], "both": [], "days": [], "moved": [], "nearDuplicate": null },
  "table": { "labels": ["通义千问", "豆包"], "rows": [ { "key": "firstCheck", "label": "第一版校验", "texts": ["…", "…"], "values": [2, 0], "note": "…" } ] },
  "evalRequestId": null,
  "versions": [ "…左边的 ItineraryVersion…", "…右边的，没排出来为 null…" ]
}
```

- 上面的数字只示意格式，不是真实结果。
- `table.rows` 的 key：`firstCheck`、`firstCodes`、`repair`、`fabricated`、`offList`，然后是 5B 对比表的各行（`places` … `end-day-N`，`validation` 改名"最终校验"），最后是 `modelTime`、`wallTime`、`calls`、`tokens`。没排出来的一边写原因或"—"。
- `diff`：两边都排出来时才有。`days[].orders` 是两边这一天的景点（第一个是左边），`sameOrder` 在都有的景点不到 2 个时为 null。
- 没有这次对比时 404。

## 分享（板块 7）

代码：`apps/api/app/api/shares.py`，数据结构 `apps/api/app/schemas/share.py`，前端类型 `packages/shared/src/share.ts`。表结构见 `data-model.md` 第 13 节。

规则（2026-11-15 Cecilia 定）：只有通过校验或只有警告的版本能分享；同一个版本再分享给回同一个链接；可以撤回，撤回后再分享换新链接；链接是 8 位随机小写字母和数字，不带名字和日期。链接绑定版本，版本本身不可变，所以原行程以后再改（加新版本）也不影响分享页。

### 生成分享链接

```http
POST /api/itinerary-versions/{versionId}/share
```

没有请求体。新建的返回 201，这个版本已经有没撤回的链接时返回那一个（200）：

```json
{ "slug": "k3f9x2qa", "versionId": "ver_…", "createdAt": "…", "revokedAt": null, "path": "/s/k3f9x2qa" }
```

- `path` 是网站上的路径；完整网址由前端按当前网站拼（后端不知道网站开在哪个域名）。
- 没有这个版本：404。没通过校验的版本：409，`detail` 是"这份行程没通过校验，不能分享"。
- 两个请求同时分享同一个版本时，数据库的唯一索引保证只建一个链接。

### 查这个版本现在的链接

```http
GET /api/itinerary-versions/{versionId}/share
```

返回和上面一样的结构；没有没撤回的链接时 404。

### 打开分享页

```http
GET /api/share/{slug}
```

```json
{ "slug": "k3f9x2qa", "createdAt": "…", "version": { "…完整的 ItineraryVersion，见"获取行程版本"…": "" } }
```

- 没有这个链接：404。撤回了：410，`detail` 是"这个分享链接已经撤回"。

### 撤回

```http
DELETE /api/share/{slug}
```

返回撤回后的链接（`revokedAt` 有值）。撤回过的再撤回一次不改时间。没有这个链接：404。

## 我的行程（板块 7）

```http
GET /api/trips
```

代码：`apps/api/app/api/trips.py`、`apps/api/app/services/trips.py`，数据结构 `apps/api/app/schemas/trips.py`。

只列 `/map` 上生成的行程（属于某段对话的）；`/compare` 产生的行程不属于对话，不列。按对话分组，最近有新版本的在前：

```json
[
  {
    "conversationId": "conv_…",
    "updatedAt": "…",
    "request": "武汉两天，喜欢历史和美食，坐地铁",
    "itineraries": [
      {
        "itineraryId": "itin_…",
        "emphasis": "classic",
        "emphasisLabel": "经典必去",
        "versions": [
          {
            "id": "ver_…", "versionNumber": 2, "createdAt": "…", "title": "…",
            "providerLabel": "豆包", "model": "…", "validationStatus": "warning", "errorCount": 0, "warningCount": 9,
            "days": 2, "startDate": "2026-11-28", "poiNames": ["…"],
            "share": { "slug": "…", "path": "/s/…", "…": "…" }
          }
        ]
      }
    ]
  }
]
```

- `request` 是这段对话里用户的第一句话。
- 一段对话里的行程按 经典必去 → 轻松少走路 → 深度文化 排；板块 5B 之前存的单份行程没有侧重（`emphasis` 为 null），排在最后。
- 每份行程的版本新的在前；`share` 是没撤回的链接，没有为 null。
- **没有登录**：列的是这个数据库里的全部行程。公开上线时这个接口和 `/trips` 要关掉或加口令（和上线方式一起定）。

## 以后的接口（设计草案）

### 修改行程

```http
POST /api/itineraries/{itineraryId}/revise
```

Request:

```json
{
  "baseVersionId": "uuid",
  "instruction": "第二天少走路，把夜景换成江滩附近。"
}
```

Response:

```json
{
  "planningJobId": "uuid",
  "status": "queued"
}
```

## 错误格式

```json
{
  "error": {
    "code": "ROUTE_PROVIDER_TIMEOUT",
    "message": "路线服务暂时不可用，请稍后重试。",
    "retryable": true,
    "details": {}
  }
}
```

## 权限规则

> 2026-11-15（板块 7）：现在没有登录，也没有匿名 session。分享页只读、撤回后打不开（410）已经做到。
>
> **公开模式**（ADR 0008，后端 `.env` 的 `PUBLIC_MODE=true`；本机开发时关着，下面这些都不查）：
>
> - 要网站主人口令的接口（请求头 `X-Owner-Passcode`）：`GET /api/trips`、`POST /api/itinerary-versions/{id}/share`、`GET /api/itinerary-versions/{id}/share`、`DELETE /api/share/{slug}`。没带或不对是 401（`detail`："这个功能需要网站主人的口令"）；后端没设 `OWNER_PASSCODE` 是 403。`GET /api/share/{slug}` 不要口令。
> - 限次数的接口：`POST /api/conversations/{id}/messages` 算 1 次，`POST /api/comparisons` 算 2 次。同一个地址每小时、全站每天各有上限，超了是 429，`detail` 是中文说明（"每小时最多……"或"今天全站的试用次数……用完了"）。带对口令的不限。
> - 景点接口不返回占位照片（`placeholder` 为 true 的那些），`/media/photos-placeholder` 不挂。
>
> 下面是早期草案。

- 未登录用户可以创建临时对话和分享页，但需要匿名 session id。
- 登录用户可以保存多个行程。
- 私有行程必须校验 user id。
- 分享页默认只读，撤回后不可访问。

## 限流建议

- 对话消息: 每个匿名 session 每小时限制。
- AI 规划: 每个用户并发 1 到 2 个 job。
- 外部 POI/路线调用: 服务端集中限流和缓存。
