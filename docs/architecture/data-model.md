# Data Model

最后更新：2026-11-15（板块 5 加了对话和行程）。数据格式由 Cecilia 在 2026-11-15 确认。

## 1. 存储方式（ADR 0003）

| 数据 | 放在哪 | 谁写 |
|---|---|---|
| 景点资料 | `data/pois/<景点id>.json`，一个景点一个文件，提交到 git | Cecilia 核实后写；Claude 按她填的模板 `docs/data/poi-fill-template.md` 转成 JSON |
| Cecilia 自己拍的照片、可自由使用授权的图片 | `data/photos/<景点id>/`，提交到 git | Cecilia |
| 官网占位照片 | `data/photos-placeholder/<景点id>/`，**不提交**（`.gitignore`），来源记在景点 JSON 里 | 经 Cecilia 同意后下载 |
| 运行时数据库 | SQLite 文件，路径由 `DATABASE_URL` 指定（默认 `apps/api/wuhanmemory.db`），不提交 | 后端 |

后端启动时先检查 `data/pois/*.json`，再把没有错误的景点导入 SQLite。景点表每次都清空重建，JSON 文件才是原始资料。

代码位置：

- 景点文件的数据模型：`apps/api/app/schemas/poi.py`
- 规则常量（武汉范围、过期上限）：`apps/api/app/data_quality/rules.py`
- 检查：`apps/api/app/data_quality/checker.py`，命令行 `python -m app.data_quality`
- 导入：`apps/api/app/db/import_pois.py`
- repository：`apps/api/app/repositories/poi_repository.py`
- 接口返回的结构：`apps/api/app/schemas/poi_api.py`，前端类型 `packages/shared/src/poi.ts`

## 2. 文书里的三条规则落在哪

| 规则 | 字段 | 怎么强制 |
|---|---|---|
| 每个景点必须有坐标和记录在案的来源 | `location`（GCJ-02）、每条信息的 `sourceId` 指向 `sources` | 缺坐标、坐标不在武汉范围、缺来源、来源不存在，都是错误，景点不能导入 |
| 会变的信息必须记录上次核实时间和过期时间 | `lastCheckedAt`、`expiresAt` | 缺任何一个是错误；有效期超过上限是错误；过期了是警告，界面上标"已过期" |
| 每条信息能区分"实地核实"和"官网占位、待确认" | `verification` | 四个取值，界面按它显示"已核实""待确认""待补充"；`onsite` 必须引用实地走访的来源，`placeholder` 不能引用实地走访 |

## 3. 景点文件格式

### 3.1 一条信息（Fact）

景点的每一条事实性信息都用同一种结构：

```json
{
  "value": "...",
  "verification": "placeholder",
  "sourceId": "official-site",
  "lastCheckedAt": "2026-11-15",
  "expiresAt": "2027-02-13",
  "todo": null,
  "note": null
}
```

| 字段 | 意思 |
|---|---|
| `value` | 内容。不同信息的内容结构不同，见 3.3 |
| `verification` | 这条信息是怎么来的，见 3.2 |
| `sourceId` | 来源，指向本文件 `sources` 里的一项。`todo` 不用填 |
| `extraSourceIds` | 同一条信息还参考了哪些来源（可选，2026-11-15 加）。`sourceId` 写最主要的那个，其余写这里；每个都必须在 `sources` 里 |
| `lastCheckedAt` | 上次核实的日期。`todo` 不用填，其他都必须有 |
| `expiresAt` | 过期日期。会变的信息必须有，不会变的不用填 |
| `todo` | `verification` 为 `todo` 时写明缺什么，例如 `"TODO(Cecilia): 官网没有写学生票"` |
| `note` | 备注，可选 |

### 3.2 核实方式（verification）

| 取值 | 意思 | 界面 |
|---|---|---|
| `onsite` | Cecilia 实地核实过。来源必须是 `field-visit` | 已核实 |
| `confirmed` | Cecilia 核对过官网、公众号或售票页面，但没在现场核实（例如节假日开放时间、预约规则）。2026-11-15 导入的豆包资料包，Cecilia 决定标成这个值 | 已核实 |
| `placeholder` | Claude 按官网先填的占位，待 Cecilia 确认。设计规范第 12 节说的 `placeholder: true` 就用这个值表示 | 待确认 |
| `todo` | 找不到可靠来源，`value` 为 `null` | 待补充 |

### 3.3 景点文件的全部字段

```json
{
  "schemaVersion": 1,
  "id": "景点id",
  "name": "名称",
  "district": "所在区",
  "category": "类别",
  "tags": ["标签"],
  "sources": [
    { "id": "visit-2026-10", "type": "field-visit", "title": "Cecilia 实地走访", "accessedAt": "2026-10-03" },
    { "id": "official-site", "type": "official-site", "title": "官网页面标题", "url": "https://...", "accessedAt": "2026-11-15" }
  ],
  "operatingStatus": { "...": "Fact<OperatingStatus>，可选，写了就必须有 expiresAt" },
  "location": { "value": { "lng": 0, "lat": 0, "coordSystem": "GCJ-02" }, "verification": "...", "sourceId": "...", "lastCheckedAt": "..." },
  "address": { "...": "Fact<string>" },
  "intro": { "...": "Fact<string>" },
  "history": { "...": "Fact<string>" },
  "openingHours": { "...": "Fact<OpeningHours>，必须有 expiresAt" },
  "ticket": { "...": "Fact<Ticket>，必须有 expiresAt" },
  "reservation": { "...": "Fact<Reservation>，必须有 expiresAt" },
  "payment": { "...": "Fact<Payment>，必须有 expiresAt" },
  "transport": { "...": "Fact<Transport>，必须有 expiresAt" },
  "recommendedDurationMinutes": { "...": "Fact<int>" },
  "bestTime": { "...": "Fact<string>" },
  "photoSpots": [{ "...": "Fact<PhotoSpot>" }],
  "food": [{ "...": "Fact<FoodItem>，每项必须有 expiresAt" }],
  "reviews": [{ "author": "署名", "relation": "self", "visitedAt": "2026-10-03", "text": "原话" }],
  "photos": [{ "file": "a.jpg", "caption": "一句说明", "license": "own", "author": "拍摄人", "takenAt": "2026-10-03" }]
}
```

基本信息：

| 字段 | 说明 |
|---|---|
| `id` | 小写英文、数字和连字符，必须和文件名一致，例如 `yellow-crane-tower` |
| `name`、`district`、`category`、`tags` | 名称、所在区、类别、标签。列表筛选和板块 5 挑候选景点用。`category` 取 `landmark`（地标建筑）、`museum`、`campus`、`park`（公园湖泊）、`riverside`（江滩）、`temple`、`street`（历史街区、步行街）、`food-street`（美食街） |
| `sources` | 本景点用到的全部来源。`type` 取 `field-visit`（实地走访）、`official-site`（官网）、`official-wechat`（官方公众号）、`official-ticketing`（官方售票或预约页面）、`government`（政府网站：区政府、文旅局、景区管委会，用于没有自己官网的街区）、`amap`（高德）、`media`（媒体报道）、`travel-platform`（携程、美团等旅游平台；2026-11-15 Cecilia 决定官方来源找不到时可以用这两类占位）、`ugc`（游客自己发的笔记和短视频，是个人经验，准确度最低；2026-11-15 加）、`other`。不是实地走访的必须有 `url`；都必须有 `accessedAt`（查阅日期或走访日期） |

单条信息（11 项都必须出现在文件里，没有资料也要写出来，标 `todo`）：

| 字段 | 内容（value 的结构） | 会变吗 |
|---|---|---|
| `location` | `{ lng, lat, coordSystem: "GCJ-02" }`。高德地图用 GCJ-02，写明以免点位偏移。**不能是 todo** | 不会 |
| `address` | 文字 | 不会 |
| `intro` | 两三句简介。官网占位时由 Claude 根据官方页面改写，不整段复制 | 不会 |
| `history` | 一段历史文化 | 不会 |
| `openingHours` | `{ allDay, periods: [{ months, weekdays, open, close, lastEntry }], closedWeekdays, note }`。`weekdays` 用 1 到 7 表示周一到周日，`months` 为空表示全年。结构化是为了板块 5 的 `validate_itinerary` 能自动判断"到达时开没开门" | **会** |
| `ticket` | `{ free, items: [{ name, priceCny }], note }` | **会** |
| `reservation` | `{ required, how, advanceDays, note }` | **会** |
| `payment` | `{ methods: ["wechat" / "alipay" / "cash" / "foreign-card" / "other"], note }` | **会** |
| `transport` | `{ metro: [{ station, line, exit, walkMinutes }], note }` | **会** |
| `recommendedDurationMinutes` | 分钟数，来自 Cecilia 的经验。板块 5 排时间用 | 不会 |
| `bestTime` | 适合去的时段 | 不会 |

开放状态（可选，2026-11-15 加）：

| 字段 | 内容 | 会变吗 |
|---|---|---|
| `operatingStatus` | `{ code: "open" / "closed-temporarily", note, reopenExpected, reopenNote }`。不写表示正常开放。暂停开放（修缮、闭园）时写 `closed-temporarily`，`expiresAt` 填预计恢复的日子，到期后界面显示"已过期"，提醒重新核实。暂停开放的景点不进板块 5 的候选，校验遇到报 `poi-closed`；这条资料过期了也照样算关着，要改资料才恢复 | **会** |

多项信息：

| 字段 | 内容 | 会变吗 |
|---|---|---|
| `photoSpots` | 每项是 `Fact<{ title, description, photo }>`，`photo` 必须是 `photos` 里登记过的文件 | 不会 |
| `food` | 每项是 `Fact<{ name, walkMinutes, note }>` | **会**（店会关） |
| `reviews` | `{ author, relation: "self" / "friend", visitedAt, text }`。只用 Cecilia 和试用过的朋友写的，必须署名。评价的来源就是署名人，不用 `sourceId` | — |
| `photos` | `{ file, caption, license, author, takenAt, sourceUrl, retrievedAt, licenseNote }`，见第 6 节 | — |

文件里出现模型没有的字段名（例如拼错）会报错，不会悄悄忽略。

### 3.4 坐标怎么来

坐标不能编，有两种来法：

- Cecilia 用高德坐标拾取器复制，来源类型 `amap`，核实方式 `confirmed`。
- 运行 `corepack pnpm amap:lookup 景点id=搜索词 ...`（`apps/api/app/tools/amap_lookup.py`），用高德"关键字搜索"在武汉市范围内查，列出前几个结果的名称、区、地址和坐标，原始结果存到 `data/amap-lookup/`（不进 git）。写进景点资料时来源类型 `amap`、核实方式 `placeholder`；Cecilia 在地图上看过点位后改成 `confirmed`。

高德返回的坐标就是 GCJ-02，不用转换。

## 4. 过期时间的上限

`expiresAt` 不能晚于 `lastCheckedAt` 加下表的天数；可以填得更早，例如节假日的临时开放时间写到假期结束那天。数值在 `apps/api/app/data_quality/rules.py` 的 `VOLATILE_MAX_DAYS`。

| 信息 | 上限 | 理由 |
|---|---|---|
| 开放状态 `operatingStatus` | 90 天 | 修缮工期常常变，一般填到预计恢复的那天 |
| 开放时间 `openingHours` | 90 天 | 不少景点分淡旺季，换季前后要再看一次 |
| 预约规则 `reservation` | 90 天 | 博物馆的预约方式改得比较勤 |
| 票价 `ticket` | 180 天 | 调价不频繁 |
| 支付方式 `payment` | 180 天 | 变化少 |
| 周边美食 `food` | 180 天 | 小店容易关门或搬走 |
| 交通 `transport` | 365 天 | 地铁新线一般提前很久公布 |
| 坐标、地址、介绍、建议时长、时段、拍照机位 | 不过期 | 基本不变，但必须有来源和核实日期 |

"今天"按武汉时间（Asia/Shanghai）算。

## 5. 状态怎么算

状态和日期有关，后端每次请求时现算（`apps/api/app/services/poi_view.py`），不存进数据库。

一条信息：

1. `todo` → `missing`，界面写"待补充"；
2. 有 `expiresAt` 且早于今天 → `expired`，"已过期"（不管原来是怎么核实的）；
3. `placeholder` → `pending`，"待确认"；
4. `onsite`、`confirmed` → `verified`，"已核实"。

一个景点、一张信纸：有一条 `expired` 就是"已过期"；否则有一条 `pending` 或 `missing` 就是"待确认"；全部 `verified` 才是"已核实"。图册那张纸里有官网占位照片或没有照片时算"待确认"。拍照机位、周边美食是列表，空着时各算一条 `missing`，一张纸上一条信息都没有时也算"待确认"，不会因为空着而显示"已核实"。

## 6. 照片

| `license` | 放在哪 | 必填 | 文件不存在时 |
|---|---|---|---|
| `own`（自己拍的） | `data/photos/<id>/` | `author` | 错误 |
| `open-license`（可自由使用授权） | `data/photos/<id>/` | `sourceUrl`、`licenseNote` | 错误 |
| `official-placeholder`（官网占位） | `data/photos-placeholder/<id>/`，不进 git | `sourceUrl`、`retrievedAt` | 警告（换台电脑就没有） |
| `third-party-placeholder`（图库预览图、媒体和平台图片占位，2026-11-15 Cecilia 决定） | `data/photos-placeholder/<id>/`，不进 git | `sourceUrl`、`retrievedAt`、`licenseNote`（出处和授权情况） | 警告 |

每张照片都要有 `caption`（给看不到图的人读）。`file` 只写文件名。网站公开前，两种占位照片必须全部换掉（第三方占位里有付费图库的预览图和带水印的图，没有授权），检查脚本每次都会报还剩几张。

后端在 `/media/photos/` 和 `/media/photos-placeholder/` 提供照片文件。

## 6.5 英文译文（中英双语，ADR 0009）

景点资料只有中文。英文是译文，单独放在 `data/pois/en/<id>.json`（`app/services/poi_i18n.py`）：

```json
{
  "id": "yellow-crane-tower",
  "translatedBy": "Claude（AI）从中文资料翻译，未经人工核对",
  "translatedAt": "2026-11-15",
  "texts": {
    "name": {"zh": "黄鹤楼", "en": "Yellow Crane Tower"},
    "ticket.value.items.0.name": {"zh": "日场全票", "en": "Day ticket, full price"}
  }
}
```

- 键是字段在景点文件里的位置，点号连接，列表用序号。只翻界面上会显示的字段（`TRANSLATABLE`）：名字、区、标签、地址、简介、历史、开放时间和票价的 note、票名、预约和支付说明、地铁站和线路、交通说明、适合去的时段、拍照机位、周边美食、评价、照片说明和作者、开放状态说明。
- 每条存着翻译时的中文原文。中文改了、对不上时这条作废，英文版显示中文。
- 不进 SQLite：接口按 `lang=en` 读出景点后再套上译文（文件改了按修改时间重新读，不用重启后端）。规划链路的逻辑仍用中文资料，只在存进行程版本时换成译文。
- 2026-11-15 的 10 个景点 528 条译文由 Claude 翻译，未经人工核对。

## 7. 检查脚本

```bash
cd ~/WuhanMemory-project2 && corepack pnpm check:data
```

也可以加 `--today 2027-03-01`，看到那天会有哪些信息过期。

错误（有错误的景点不能导入数据库，命令退出码为 1）：

| code | 什么情况 |
|---|---|
| `missing-location` | 缺坐标，或坐标标了 todo |
| `location-out-of-bounds` | 坐标不在武汉范围（东经 113.66 到 115.10、北纬 29.95 到 31.39 的矩形）；经纬度写反会提示 |
| `missing-source` / `unknown-source` | 缺来源 / 来源不在 `sources` 里 |
| `bad-source` | 来源缺标题、链接或日期 |
| `verification-source-mismatch` | 标了实地核实却不是实地走访的来源，或反过来 |
| `missing-checked-at` | 缺核实日期 |
| `missing-expires-at` | 会变的信息缺过期日期 |
| `expiry-too-long` / `bad-expiry` | 有效期超过上限 / 过期日期不晚于核实日期 |
| `future-date` | 日期在今天之后 |
| `missing-field` / `missing-value` / `todo-with-value` | 缺字段 / 有核实方式没内容 / 标了 todo 却有内容 |
| `bad-opening-hours` | 时间格式不对、开门晚于关门、星期或月份超出范围 |
| `photo-missing` | 自己的或授权的照片文件不存在 |
| `bad-photo` | 照片缺说明、拍摄人、来源，或拍照机位引用了没登记的照片 |
| `review-without-author` | 评价没署名 |
| `bad-format` / `bad-json` / `bad-id` / `id-filename-mismatch` / `duplicate-id` | 格式问题 |

警告（照样导入）：`expired`（已过期）、`placeholder-photo-missing`（占位照片不在本机）、`photo-not-listed`（照片目录里有没登记的文件）、`todo-without-note`。

最后一行统计实地核实、核对过来源、官网占位、TODO、已过期的条数，以及官网占位照片的张数。

测试：`apps/api/tests/test_poi_checker.py`。`apps/api/tests/fixtures/data/pois/` 里有一份合格的虚构样例和 12 份各错一处的数据（文件名就是错在哪），每一份都必须被查出来。

英文译文（都是警告，不挡导入）：

| code | 什么情况 |
|---|---|
| `translation-stale` | 中文资料改过，这几条译文作废了，要重新翻译 |
| `translation-missing` | 有中文、还没有译文的条目 |
| `translation-orphan` | 译文文件对应的景点不存在或没通过检查 |
| `translation-unknown-field` | 译文里有不需要翻译的位置 |
| `translation-bad-file` | 译文文件读不出来 |

## 8. SQLite 表

```sql
CREATE TABLE pois (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    district    TEXT NOT NULL,
    category    TEXT NOT NULL,
    lng         REAL NOT NULL,   -- GCJ-02
    lat         REAL NOT NULL,   -- GCJ-02
    sort_order  INTEGER NOT NULL,
    tags_json   TEXT NOT NULL,
    data_json   TEXT NOT NULL,   -- 整个景点文件
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE poi_facts (
    poi_id          TEXT NOT NULL REFERENCES pois(id) ON DELETE CASCADE,
    field           TEXT NOT NULL,   -- 例如 ticket、food[0]
    verification    TEXT NOT NULL,
    source_id       TEXT,
    last_checked_at TEXT,
    expires_at      TEXT,
    PRIMARY KEY (poi_id, field)
);
```

- `pois` 把常用于筛选的列（区、类别、坐标）单独存，完整内容存在 `data_json`，取出来再按 `PoiFile` 校验。
- `poi_facts` 每条信息一行，方便以后直接查"哪些已过期""还剩多少占位"（板块 5 校验行程时也会用到）。
- 没有 PostGIS：两点距离在 Python 里用经纬度公式算（ADR 0003）。

## 9. repository 层

```python
class PoiRepository(Protocol):
    def list_pois(self, *, district: str | None = None, category: str | None = None) -> list[PoiFile]: ...
    def get_poi(self, poi_id: str) -> PoiFile | None: ...
```

接口和以后的规划链路只调用这两个方法。SQL 只出现在 `SqlitePoiRepository` 和 `app/db/` 里。换 PostgreSQL 时新写一个实现这两个方法的类。

## 10. 路线缓存（板块 3）

文书里"交通时间等会变的信息，要记录上次核实时间和过期时间"落在这张表上。

```sql
CREATE TABLE route_cache (
    from_poi_id TEXT NOT NULL,
    to_poi_id   TEXT NOT NULL,
    mode        TEXT NOT NULL,   -- walk / transit / drive
    origin      TEXT NOT NULL,   -- 发给高德的起点 "lng,lat"（GCJ-02）
    destination TEXT NOT NULL,
    provider    TEXT NOT NULL,   -- amap
    result_json TEXT NOT NULL,   -- 整理后的结果（接口里的一条 route）
    raw_json    TEXT NOT NULL,   -- 高德原始返回，留着核对
    checked_at  TEXT NOT NULL,   -- 向高德查询的时间，带时区
    expires_at  TEXT NOT NULL,
    PRIMARY KEY (from_poi_id, to_poi_id, mode)
);
```

- 一对景点、一种交通方式一行。A 到 B 和 B 到 A 分开存（单行道、公交方向不同）。
- 过期时间（2026-11-15 Cecilia 选的方案 A）：步行 30 天，公交地铁 7 天，驾车 1 天。数值在 `apps/api/app/services/routing/service.py` 的 `ROUTE_TTL_DAYS`。
- 过期了就重新向高德查，查到的覆盖旧的。重查失败时先返回旧结果，标"已过期"。
- 景点坐标改了，`origin` / `destination` 对不上，旧缓存不再使用。景点表重建时这张表不动。
- 只缓存查成功的（有方案或高德明确说没有方案），出错不缓存。
- 公交地铁统一按当天上午 10 点出发查，避免半夜查到"地铁停运"又被缓存一周。
- 板块 5B：`result_json` 里加了 `walkingDistanceMeters`（步行全程、公交地铁的换乘和进出站步行、打车 0）。之前存的行没有这个字段，`corepack pnpm routes:prewarm` 先从 `raw_json` 里补（`fill_walking_distances`，不发请求、不改有效期），再把 9 个开放景点两两的步行和公交地铁查齐。
- 代码：repository `apps/api/app/repositories/route_cache_repository.py`，服务 `apps/api/app/services/routing/`。

这张表可以随时删掉，下次查询会重新向高德要。

## 11. 大模型调用记录（板块 4）

网关（`LLMGateway`）每调用一次写一行，成功失败都写。板块 6 的双模型对比从这张表取耗时、重试和修复的情况。

```sql
CREATE TABLE llm_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id      TEXT NOT NULL,
    task          TEXT NOT NULL,      -- 这次调用的用途，例如 ping、extract_preferences
    provider      TEXT NOT NULL,      -- qwen / doubao
    model         TEXT,               -- 对方返回的真实模型名
    started_at    TEXT NOT NULL,      -- 开始时间，UTC
    latency_ms    INTEGER NOT NULL,   -- 从开始到结束的总时间，含重试之间的等待
    attempts      INTEGER NOT NULL,   -- 一共向模型发了几次请求
    retried       INTEGER NOT NULL,   -- 有没有因为超时、限流、对方出错而重试
    repaired      INTEGER NOT NULL,   -- 有没有因为输出不合格让模型重答
    ok            INTEGER NOT NULL,
    error_code    TEXT,               -- 失败时的错误类型，例如 timeout、rate_limited、bad_output
    input_tokens  INTEGER,
    output_tokens INTEGER
);
```

- 不存提示词和回答的内容，也不存 key（2026-11-15 Cecilia 选的）。
- 豆包请求里填的是 endpoint ID，`model` 记的是对方返回的真实模型名。
- 一次网关调用可能向模型发好几次请求（重试、让模型重答），`attempts` 是总次数，token 数是几次的合计。
- 开了"自动换备用模型"时，失败的默认模型和接手的备用模型各写一行。
- 记录写不进去不影响这次调用，只在日志里留一条警告。
- 代码：repository `apps/api/app/repositories/llm_call_repository.py`，记录的结构 `LLMCallRecord` 在 `apps/api/app/services/llm/base.py`。

## 12. 对话和行程（板块 5）

```sql
CREATE TABLE conversations (
    id               TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    preferences_json TEXT NOT NULL,   -- 到目前为止抽到的偏好（TravelerPreferences）
    itinerary_id     TEXT             -- 这段对话生成的行程；还没生成时为空
);

CREATE TABLE conversation_messages (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id      TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role                 TEXT NOT NULL,  -- user / assistant
    content              TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    kind                 TEXT,           -- 回复的种类：question / itinerary / failed / error
    asked                TEXT,           -- 反问时问了什么：days、date、past-date，逗号分隔
    provider             TEXT,           -- 这条回复用的模型
    itinerary_version_id TEXT,           -- 这条回复带出的行程版本
    planning_round_id    TEXT            -- 板块 5B：这条回复带出的那一轮方案
);

CREATE TABLE itineraries (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE itinerary_versions (
    id                TEXT PRIMARY KEY,
    itinerary_id      TEXT NOT NULL REFERENCES itineraries(id) ON DELETE CASCADE,
    version_number    INTEGER NOT NULL,  -- 同一份行程从 1 开始
    created_at        TEXT NOT NULL,
    provider          TEXT NOT NULL,     -- qwen / doubao
    model             TEXT,              -- 对方返回的真实模型名
    validation_status TEXT NOT NULL,     -- passed / warning / failed
    error_count       INTEGER NOT NULL,
    warning_count     INTEGER NOT NULL,
    rounds            INTEGER NOT NULL,  -- 1 或 2（把错误交给模型修正过一次）
    data_json         TEXT NOT NULL,     -- 整个版本（ItineraryVersionData）
    UNIQUE (itinerary_id, version_number)
);
```

- 一段对话对应一份行程；每条带出行程的回复是这份行程的一个新版本。
- **版本只能新增，不能修改**：repository 没有 update 方法。分享页（板块 7）绑定版本，见第 13 节。
- `data_json` 是快照：生成时的景点资料（连同核实状态）、交通、校验结果、模型、模型最后一轮的原始输出。以后景点资料改了，旧版本不变。字段见 `api-contracts.md` 的"获取行程版本"。
- 模型、校验结果、错误和警告条数、修正轮数单独存成列，板块 6 按模型统计时不用解析 JSON。
- 没通过校验的版本也存，`validation_status` 是 `failed`。
- 偏好和消息内容会存（对话要接着进行）；`llm_calls` 里仍然不存提示词和回答。
- `kind` 和 `asked` 两列是后加的：`init_schema` 发现旧表缺这两列时用 `ALTER TABLE` 补上（`app/db/sqlite.py` 的 `_ADDED_COLUMNS`）。
- 规划任务（进行到哪一步）只在内存里，不进数据库。

### 12.1 规划的轮（板块 5B）

```sql
CREATE TABLE planning_rounds (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    round_number    INTEGER NOT NULL,  -- 同一段对话从 1 开始
    created_at      TEXT NOT NULL,
    data_json       TEXT NOT NULL,     -- 整轮（PlanningRoundData）
    UNIQUE (conversation_id, round_number)
);
```

- 一次规划按三种侧重排三份，是一"轮"。`data_json` 里按"经典必去 → 轻松少走路 → 深度文化"记下每份的侧重、行程 id、版本 id、展示没有、不展示的原因，以及三份共用的 `defaultsUsed`。
- 每份方案是一份行程（`itineraries` 一行）：同一段对话里同一侧重是同一份行程，下一轮是它的下一个版本。所以一段对话现在最多有三份行程；`conversations.itinerary_id` 只记第一次展示的那份，界面不再用它找行程，而是按消息上的 `planning_round_id` 取一轮。
- 轮存下后不再修改；再发消息就是新的一轮，旧的保留。
- 版本的 `data_json` 里多了 `emphasis`（侧重）和 `metrics`（程序算的数字）；之前存的版本没有，为 null。
- `conversation_messages.planning_round_id` 是后加的列，和 `kind`、`asked` 一样由 `_ADDED_COLUMNS` 补上。
- 代码：`apps/api/app/repositories/planning_round_repository.py`。
- 代码：`apps/api/app/repositories/conversation_repository.py`、`itinerary_repository.py`。

### 12.2 双模型对比（板块 6）

```sql
CREATE TABLE model_comparisons (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    eval_request_id TEXT,              -- 批量评测时是请求的 id（例如 r01），页面上发起的为空
    data_json       TEXT NOT NULL      -- 整次对比（ModelComparisonData）
);
```

- 一次对比：请求原文、两边共用的偏好（`preferencesSource` 是 `extracted` 或 `given`，抽偏好的模型和那次调用的统计）、侧重、两边各自的结果（模型名、版本 id 或出错说明、校验情况 `quality`、5B 的数字 `plan`、调用统计 `calls`、整体耗时）、两份的差异 `diff`、对比表 `table`。结构见 `apps/api/app/schemas/comparison.py`。
- 两份行程各是一个行程版本（`itineraries` 的 `conversation_id` 为空，不属于任何对话）。对比存下后不再修改。
- 版本的 `data_json` 里多了 `firstValidation`（第一版的完整校验报告）和 `firstDraft`（修正过时模型的第一版输出，没修正过为 null）。板块 6 之后存的版本都有（`/map` 的也有）；之前存的为 null。
- 板块 6C：版本里再多 `outline`（模型给的行程：每天出发时间、站点顺序、停留时长）和 `firstOutline`（修正过时模型的第一版，没修正过为 null）。`draft` 和 `firstDraft` 从这时起是程序推出钟点后的行程。之前存的版本没有 `outline`。
- 代码：`apps/api/app/repositories/model_comparison_repository.py`。

## 13. 分享链接（板块 7）

```sql
CREATE TABLE share_links (
    slug        TEXT PRIMARY KEY,      -- 8 位随机小写字母和数字（去掉 0 o 1 l i）
    version_id  TEXT NOT NULL REFERENCES itinerary_versions(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    revoked_at  TEXT                   -- 撤回的时间；没撤回为空
);
-- 同一个版本只能有一个没撤回的链接
CREATE UNIQUE INDEX share_links_active_idx ON share_links (version_id) WHERE revoked_at IS NULL;
```

- 链接指向一个行程版本。版本是不可变的快照（第 12 节），所以分享页不复制数据，原行程以后加了新版本也不影响分享页。
- 撤回只填 `revoked_at`，不删行：撤回过的链接打开时能说"已经撤回"，而不是"没有这个链接"。撤回后再分享同一个版本，建一个新链接。
- 没通过校验的版本不能分享，这条规则在接口里查（`app/api/shares.py`），表上不管。
- 代码：`apps/api/app/repositories/share_link_repository.py`。

## 14. 公开模式的次数记录（板块 7）

```sql
CREATE TABLE rate_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client      TEXT NOT NULL,         -- 网络地址的摘要（sha256），不存原始地址
    weight      INTEGER NOT NULL,      -- 规划 1，对比 2
    created_at  TEXT NOT NULL
);
CREATE INDEX rate_events_time_idx ON rate_events (created_at);
```

- 只在公开模式下写（ADR 0008）。每写一行顺便删掉两天前的，够算"每小时"和"今天"。
- 代码：`apps/api/app/repositories/rate_event_repository.py`、`apps/api/app/core/site_policy.py`。

## 15. 以后的表

2026-07 按 PostgreSQL + PostGIS 写的旧草案已经删掉，可以在 git 历史和 `infra/migrations/0001_initial_schema.sql` 里查到。
