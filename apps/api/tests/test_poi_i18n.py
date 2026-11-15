"""景点资料英文译文（中英双语）的测试：译文怎么套上去、中文改了以后译文作废、数据检查报出来。

测试数据是虚构的。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.data_quality.checker import check_data_dir
from app.schemas.poi import PoiFile
from app.services.poi_i18n import apply_translation, load_translation, localize_poi, translatable_texts
from tests.poi_factory import TODAY, good_poi, write_data_dir

today = date.fromisoformat(TODAY)


def _write_translation(root: Path, poi_id: str, texts: dict[str, dict[str, str]]) -> Path:
    d = root / "pois" / "en"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{poi_id}.json"
    path.write_text(
        json.dumps({"id": poi_id, "translatedBy": "test", "translatedAt": TODAY, "texts": texts}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_translatable_texts_only_ui_fields() -> None:
    texts = translatable_texts(good_poi())
    assert texts["name"] == "测试景点"
    assert "district" in texts
    # 来源标题、核实备注不翻
    assert not any(k.startswith("sources.") for k in texts)
    assert not any(k.endswith(".note") and k.count(".") == 1 for k in texts)


def test_apply_translation_replaces_matching_text(tmp_path: Path) -> None:
    poi = PoiFile.model_validate(good_poi())
    path = _write_translation(tmp_path, poi.id, {"name": {"zh": "测试景点", "en": "Test Place"}})
    result = apply_translation(poi, load_translation(path))
    assert result.poi.name == "Test Place"
    assert result.used == 1
    assert result.stale == []
    # 原来的对象不变
    assert poi.name == "测试景点"


def test_stale_translation_falls_back_to_chinese(tmp_path: Path) -> None:
    poi = PoiFile.model_validate(good_poi())
    # 译文是按旧的中文翻的
    path = _write_translation(tmp_path, poi.id, {"name": {"zh": "旧名字", "en": "Old Name"}})
    result = apply_translation(poi, load_translation(path))
    assert result.poi.name == "测试景点"
    assert result.stale == ["name"]


def test_localize_poi_only_for_english(tmp_path: Path) -> None:
    data = write_data_dir(tmp_path / "data", [good_poi()], {"good-sample": ["sample.jpg"]})
    _write_translation(data, "good-sample", {"name": {"zh": "测试景点", "en": "Test Place"}})
    poi = PoiFile.model_validate(good_poi())
    assert localize_poi(poi, "zh", data).name == "测试景点"
    assert localize_poi(poi, "en", data).name == "Test Place"


def test_checker_reports_stale_missing_and_orphan(tmp_path: Path) -> None:
    data = write_data_dir(tmp_path / "data", [good_poi()], {"good-sample": ["sample.jpg"]})
    _write_translation(data, "good-sample", {"name": {"zh": "旧名字", "en": "Old Name"}})
    _write_translation(data, "no-such-place", {"name": {"zh": "x", "en": "x"}})
    report = check_data_dir(data, today)
    codes = report.codes("good-sample")
    assert "translation-stale" in codes
    assert "translation-missing" in codes
    assert "translation-orphan" in report.codes("no-such-place")
    # 都是警告，不挡导入
    assert report.ok


def test_checker_quiet_without_translations(tmp_path: Path) -> None:
    data = write_data_dir(tmp_path / "data", [good_poi()], {"good-sample": ["sample.jpg"]})
    report = check_data_dir(data, today)
    assert not any(c.startswith("translation-") for c in report.codes())


def test_real_translations_are_complete() -> None:
    """仓库里 data/pois/en/ 的译文要跟得上中文资料：没有作废的、没有漏翻的。"""
    from app.core.config import settings

    report = check_data_dir(settings.data_dir, today)
    bad = [str(i) for i in report.issues if i.code.startswith("translation-")]
    assert bad == []


def test_poi_api_lang(tmp_path: Path) -> None:
    """接口按 ?lang=、X-Lang 请求头、wm-lang cookie 认语言，都没有时是中文。"""
    from app.api.pois import get_data_dir, get_poi_repository, get_today
    from app.db.import_pois import import_pois
    from app.db.sqlite import connect
    from app.main import app
    from app.repositories.poi_repository import SqlitePoiRepository

    data = write_data_dir(tmp_path / "data", [good_poi()], {"good-sample": ["sample.jpg"]})
    _write_translation(data, "good-sample", {"name": {"zh": "测试景点", "en": "Test Place"}})
    db = tmp_path / "test.db"
    conn = connect(db)
    try:
        import_pois(conn, data, today)
    finally:
        conn.close()
    app.dependency_overrides[get_poi_repository] = lambda: SqlitePoiRepository(db)
    app.dependency_overrides[get_today] = lambda: today
    app.dependency_overrides[get_data_dir] = lambda: data
    try:
        client = TestClient(app)
        name = lambda r: r.json()["pois"][0]["name"]  # noqa: E731
        assert name(client.get("/api/pois")) == "测试景点"
        assert name(client.get("/api/pois?lang=en")) == "Test Place"
        assert name(client.get("/api/pois", headers={"X-Lang": "en"})) == "Test Place"
        assert name(client.get("/api/pois", cookies={"wm-lang": "en"})) == "Test Place"
        assert client.get("/api/pois/good-sample?lang=en").json()["poi"]["name"] == "Test Place"
        assert client.get("/api/pois/nope?lang=en").json()["detail"] == "No such place: nope"
    finally:
        app.dependency_overrides.pop(get_poi_repository, None)
        app.dependency_overrides.pop(get_today, None)
        app.dependency_overrides.pop(get_data_dir, None)
