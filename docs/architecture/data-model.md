# Data Model

## 数据库

主库使用 PostgreSQL，启用:

- PostGIS: 空间数据、距离查询、路线几何。
- pgvector: 内容向量检索。
- JSONB: 存储外部 API 原始片段和灵活扩展字段，但核心业务字段仍结构化。

## 核心实体

### users

```text
id uuid pk
display_name text
email text nullable
auth_provider text
created_at timestamptz
updated_at timestamptz
```

### conversations

```text
id uuid pk
user_id uuid nullable fk users.id
city text
status text
created_at timestamptz
updated_at timestamptz
```

### messages

```text
id uuid pk
conversation_id uuid fk conversations.id
role text
content text
structured_payload jsonb
created_at timestamptz
```

### planning_jobs

```text
id uuid pk
conversation_id uuid fk conversations.id
status text
input_snapshot jsonb
error_code text nullable
error_message text nullable
started_at timestamptz nullable
finished_at timestamptz nullable
created_at timestamptz
```

### traveler_preferences

```text
id uuid pk
conversation_id uuid fk conversations.id
city text
start_date date
end_date date
pace text
budget_level text
transport_preference text
party_type text
interests text[]
must_include text[]
must_exclude text[]
constraints jsonb
created_at timestamptz
updated_at timestamptz
```

### pois

```text
id uuid pk
external_provider text
external_id text
name text
city text
district text nullable
category text
tags text[]
location geography(Point, 4326)
address text nullable
opening_hours jsonb
ticket_info jsonb
reservation_info jsonb
payment_info jsonb
recommended_duration_minutes int
source_url text nullable
last_verified_at timestamptz
created_at timestamptz
updated_at timestamptz
```

Indexes:

```sql
CREATE INDEX pois_location_gix ON pois USING gist (location);
CREATE INDEX pois_city_category_idx ON pois (city, category);
CREATE INDEX pois_tags_gin ON pois USING gin (tags);
```

### poi_contents

```text
id uuid pk
poi_id uuid fk pois.id
content_type text
title text
body text
source_name text
source_url text nullable
confidence numeric
embedding vector
created_at timestamptz
updated_at timestamptz
```

Content types:

- `intro`
- `history`
- `review_summary`
- `photo_spot`
- `safety_tip`
- `accessibility`

### itineraries

```text
id uuid pk
conversation_id uuid fk conversations.id
user_id uuid nullable fk users.id
title text
city text
created_at timestamptz
updated_at timestamptz
```

### itinerary_versions

```text
id uuid pk
itinerary_id uuid fk itineraries.id
version_number int
status text
planner_model text
preference_snapshot jsonb
itinerary_json jsonb
validation_result jsonb
created_at timestamptz
```

版本不可变。用户编辑生成新版本。

### itinerary_days

```text
id uuid pk
itinerary_version_id uuid fk itinerary_versions.id
day_number int
date date nullable
theme text
summary text
created_at timestamptz
```

### itinerary_items

```text
id uuid pk
itinerary_day_id uuid fk itinerary_days.id
sort_order int
item_type text
poi_id uuid nullable fk pois.id
start_time time nullable
end_time time nullable
title text
description text
metadata jsonb
created_at timestamptz
```

### route_segments

```text
id uuid pk
itinerary_day_id uuid fk itinerary_days.id
from_item_id uuid fk itinerary_items.id
to_item_id uuid fk itinerary_items.id
mode text
duration_minutes int
distance_meters int
cost_estimate_cny numeric nullable
polyline geography(LineString, 4326) nullable
provider text
provider_payload jsonb
expires_at timestamptz
created_at timestamptz
```

Indexes:

```sql
CREATE INDEX route_segments_polyline_gix ON route_segments USING gist (polyline);
CREATE INDEX route_segments_expiry_idx ON route_segments (expires_at);
```

### share_pages

```text
id uuid pk
itinerary_version_id uuid fk itinerary_versions.id
slug text unique
visibility text
expires_at timestamptz nullable
revoked_at timestamptz nullable
view_count int
created_at timestamptz
```

### external_api_cache

```text
id uuid pk
provider text
cache_key text
payload jsonb
expires_at timestamptz
created_at timestamptz
```

Indexes:

```sql
CREATE UNIQUE INDEX external_api_cache_key_idx ON external_api_cache (provider, cache_key);
CREATE INDEX external_api_cache_expiry_idx ON external_api_cache (expires_at);
```

## 空间查询建议

- 附近 POI 查询用 `ST_DWithin` 和 GiST 索引。
- 最近点排序用 PostGIS KNN 运算符。
- 经纬度统一使用 WGS84 `SRID 4326` 存储。
- 高德坐标系返回结果需要明确记录原始坐标系和转换策略，避免地图展示偏移。

## 数据质量要求

- 每条 POI 至少有 `name`、`city`、`category`、`location`、`external_provider`。
- 动态字段必须有 `last_verified_at`。
- route segment 必须有 `expires_at`。
- AI 生成的 `itinerary_json` 必须能反查到结构化表中的 POI 和 route segment。
