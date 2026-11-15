"""兴趣和景点类别的对照表。

景点资料里的 tags 现在全是空的，所以按类别（category）判断一个景点对得上哪些兴趣。
这张表是程序的判断规则，不是景点事实；2026-11-15 由 Claude 起草，待 Cecilia 确认。
以后景点有了 tags，可以把 tags 也算进来。
"""

from __future__ import annotations

from app.schemas.poi import PoiFile

# 抽偏好时，模型只能从这几个兴趣里选（用户说的别的兴趣写进 notes）
INTERESTS: tuple[str, ...] = (
    "历史文化",
    "美食",
    "自然风光",
    "城市漫步",
    "老建筑",
    "博物馆",
    "夜景",
    "拍照",
    "寺庙",
    "大学校园",
)

CATEGORY_INTERESTS: dict[str, tuple[str, ...]] = {
    "landmark": ("历史文化", "老建筑", "拍照"),
    "museum": ("历史文化", "博物馆"),
    "campus": ("大学校园", "老建筑", "拍照"),
    "park": ("自然风光", "拍照"),
    "riverside": ("自然风光", "城市漫步", "夜景"),
    "temple": ("寺庙", "历史文化", "老建筑"),
    "street": ("城市漫步", "老建筑", "历史文化"),
    "food-street": ("美食", "城市漫步"),
}


def poi_interests(poi: PoiFile) -> list[str]:
    found = list(CATEGORY_INTERESTS.get(poi.category, ()))
    for tag in poi.tags:
        if tag in INTERESTS and tag not in found:
            found.append(tag)
    return found


def matched_interests(poi: PoiFile, wanted: list[str]) -> list[str]:
    have = poi_interests(poi)
    return [w for w in wanted if w in have]
