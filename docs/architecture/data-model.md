# Data Model

最后更新：2026-11-15（板块 2）。数据格式由 Cecilia 在 2026-11-15 确认。

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
| `lastCheckedAt` | 上次核实的日期。`todo` 不用填，其他都必须有 |
| `expiresAt` | 过期日期。会变的信息必须有，不会变的不用填 |
| `todo` | `verification` 为 `todo` 时写明缺什么，例如 `"TODO(Cecilia): 官网没有写学生票"` |
| `note` | 备注，可选 |

### 3.2 核实方式（verification）

| 取值 | 意思 | 界面 |
|---|---|---|
| `onsite` | Cecilia 实地核实过。来源必须是 `field-visit` | 已核实 |
| `confirmed` | Cecilia 核对过官网、公众号或售票页面，但没在现场核实（例如节假日开放时间、预约规则） | 已核实 |
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
| `sources` | 本景点用到的全部来源。`type` 取 `field-visit`（实地走访）、`official-site`（官网）、`official-wechat`（官方公众号）、`official-ticketing`（官方售票或预约页面）、`government`（政府网站：区政府、文旅局、景区管委会，用于没有自己官网的街区）、`amap`（高德）、`media`（媒体报道）、`travel-platform`（携程、美团等旅游平台；2026-11-15 Cecilia 决定官方来源找不到时可以用这两类占位）、`other`。不是实地走访的必须有 `url`；都必须有 `accessedAt`（查阅日期或走访日期） |

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

每张照片都要有 `caption`（给看不到图的人读）。`file` 只写文件名。网站公开前，官网占位照片必须全部换掉，检查脚本每次都会报还剩几张。

后端在 `/media/photos/` 和 `/media/photos-placeholder/` 提供照片文件。

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

## 10. 以后的表

行程、行程版本、分享页、模型对比结果、高德路线缓存这些运行时数据也存进 SQLite，表结构在用到的板块里定，定下来后写进本文件：

- 路线缓存（板块 3）：每条带 `checkedAt` 和 `expiresAt`。
- 行程和行程版本（板块 5）：版本不可变，分享页绑定版本。
- 分享页（板块 7）、对比结果（板块 6）。

2026-07 按 PostgreSQL + PostGIS 写的旧草案已经删掉，可以在 git 历史和 `infra/migrations/0001_initial_schema.sql` 里查到。
