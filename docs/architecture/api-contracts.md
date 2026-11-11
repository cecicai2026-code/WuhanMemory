# API Contracts

## 风格

- 外部 API 使用 REST + JSON。
- 长任务状态使用 SSE 或 WebSocket，MVP 可先用轮询。
- 请求和响应 schema 使用 OpenAPI + Pydantic 生成，前端同步生成 TypeScript 类型。
- 所有写操作返回资源 id，复杂结果通过查询接口读取。

## 主要接口

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
