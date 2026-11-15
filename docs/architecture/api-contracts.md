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
  "lastCheckedAt": "2026-11-15",
  "expiresAt": "2027-02-13",
  "todo": null,
  "note": null
}
```

- `photoSpots`、`food`：上面这种结构的数组；
- `reviews`：署名评价；
- `photos`：照片，多了 `placeholder` 和 `url`（相对于后端地址，例如 `/media/photos/<id>/a.jpg`；占位照片不在本机时为 `null`）。

没有这个景点时返回 404：`{ "detail": "没有这个景点：<id>" }`。

### 照片文件

```http
GET /media/photos/{id}/{file}
GET /media/photos-placeholder/{id}/{file}
```

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
- 这个接口不调用模型。"已配置"不等于"key 有效"，key 对不对要真的调用一次才知道（冒烟测试或下面的试一句）。

### 模型：试一句（临时）

```http
POST /api/llm/ping
```

```json
{ "provider": "doubao" }
```

`provider` 不填就用默认模型。后端通过 `LLMGateway` 给这个模型发一句固定的话，每调一次都是一次真实调用。板块 5 接上对话后去掉这个接口。

```json
{
  "provider": "doubao",
  "label": "豆包",
  "model": "<对方返回的真实模型名>",
  "reply": "<模型的回答>",
  "latencyMs": 2065,
  "attempts": 1,
  "retried": false,
  "repaired": false
}
```

- `latencyMs`：从开始到结束的总时间，含重试之间的等待。`attempts`：一共向模型发了几次请求。
- `retried`：有没有因为超时、限流、对方出错而重试。`repaired`：有没有因为输出不合格让模型重答。

### 模型：出错时

所有经过 `LLMGateway` 的接口（现在是试一句，板块 5 起还有规划）出错时返回同一种结构：

```json
{ "detail": { "code": "rate_limited", "message": "豆包限流（HTTP 429，…）", "retryable": true, "provider": "doubao" } }
```

| `code` | 含义 | HTTP 状态码 | 网关会不会重试 |
|---|---|---|---|
| `unknown_provider` | 指定的模型不在清单里 | 400 | 不会 |
| `not_configured` | 没配 key 或模型名 | 503 | 不会 |
| `invalid_key` | key 无效或没有权限 | 502 | 不会 |
| `bad_config` | 模型名或接入点填错 | 502 | 不会 |
| `quota_exhausted` | 额度用完或账户欠费 | 502 | 不会 |
| `content_blocked` | 被对方的内容审核拦下 | 502 | 不会 |
| `bad_request` | 对方认为请求有问题 | 502 | 不会 |
| `rate_limited` | 限流 | 429 | 会，先等一会儿 |
| `timeout` | 规定时间内没有回答 | 504 | 会 |
| `upstream_error` | 对方服务器出错或网络断开 | 502 | 会 |
| `bad_output` | 让模型重答一次后输出仍不合格 | 502 | 已经重答过一次 |
| `provider_error` | 对方返回的结构和预期不一样 | 502 | 不会 |

`retryable` 说的是这种错值不值得过一会儿再试；返回给前端时网关自己的重试已经用完了。`message` 里不会出现 key。

## 主要接口（设计草案）

### 创建对话

```http
POST /api/conversations
```

Request:

```json
{
  "city": "武汉",
  "locale": "zh-CN"
}
```

Response:

```json
{
  "conversationId": "uuid",
  "status": "active"
}
```

### 发送消息

```http
POST /api/conversations/{conversationId}/messages
```

Request:

```json
{
  "content": "我想国庆去武汉玩 3 天，喜欢历史文化和美食，希望地铁优先。"
}
```

Response:

```json
{
  "messageId": "uuid",
  "planningJobId": "uuid",
  "status": "queued"
}
```

### 查询规划任务

```http
GET /api/planning-jobs/{jobId}
```

Response:

```json
{
  "jobId": "uuid",
  "status": "running",
  "stage": "validating_routes",
  "progress": 0.62
}
```

### 获取行程版本

```http
GET /api/itinerary-versions/{versionId}
```

Response:

```json
{
  "id": "uuid",
  "itineraryId": "uuid",
  "versionNumber": 3,
  "city": "武汉",
  "days": [],
  "map": {
    "pois": [],
    "routes": []
  },
  "validation": {
    "status": "passed",
    "warnings": []
  }
}
```

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

### 发布分享页

```http
POST /api/itinerary-versions/{versionId}/share
```

Request:

```json
{
  "visibility": "public",
  "expiresAt": null
}
```

Response:

```json
{
  "shareId": "uuid",
  "url": "https://example.com/s/wuhan-abc123"
}
```

### 获取分享页

```http
GET /api/share/{slug}
```

Response:

```json
{
  "title": "武汉 3 日历史文化与美食路线",
  "versionId": "uuid",
  "readOnly": true,
  "days": [],
  "map": {
    "pois": [],
    "routes": []
  }
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

- 未登录用户可以创建临时对话和分享页，但需要匿名 session id。
- 登录用户可以保存多个行程。
- 私有行程必须校验 user id。
- 分享页默认只读，撤回后不可访问。

## 限流建议

- 对话消息: 每个匿名 session 每小时限制。
- AI 规划: 每个用户并发 1 到 2 个 job。
- 外部 POI/路线调用: 服务端集中限流和缓存。
