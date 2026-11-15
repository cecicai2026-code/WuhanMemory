"""数据检查脚本的测试：故意放错的数据必须能查出来，合格的数据不能误报。

tests/fixtures/data/pois/ 里每个 broken-*.json 只错一处，文件名就是错在哪。
这些都是虚构的测试数据。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.data_quality.__main__ import main
from app.data_quality.checker import check_data_dir
from tests.poi_factory import TODAY, good_poi, write_data_dir

FIXTURES = Path(__file__).parent / "fixtures" / "data"
today = date.fromisoformat(TODAY)


@pytest.fixture(scope="module")
def fixture_report():
    return check_data_dir(FIXTURES, today)


def test_good_sample_passes(fixture_report) -> None:
    issues = [i for i in fixture_report.issues if i.poi_id == "good-sample"]
    assert issues == []


@pytest.mark.parametrize(
    ("poi_id", "code", "level"),
    [
        ("broken-no-location", "missing-location", "error"),
        ("broken-location-todo", "missing-location", "error"),
        ("broken-location-swapped", "location-out-of-bounds", "error"),
        ("broken-location-other-city", "location-out-of-bounds", "error"),
        ("broken-no-source", "missing-source", "error"),
        ("broken-unknown-source", "unknown-source", "error"),
        ("broken-no-checked-at", "missing-checked-at", "error"),
        ("broken-no-expires-at", "missing-expires-at", "error"),
        ("broken-expiry-too-long", "expiry-too-long", "error"),
        ("broken-expired", "expired", "warning"),
        ("broken-onsite-not-visit", "verification-source-mismatch", "error"),
        ("broken-photo-missing", "photo-missing", "error"),
    ],
)
def test_broken_fixture_is_caught(fixture_report, poi_id: str, code: str, level: str) -> None:
    found = [i for i in fixture_report.issues if i.poi_id == poi_id]
    assert any(i.code == code and i.level == level for i in found), found


def test_every_broken_fixture_is_reported(fixture_report) -> None:
    """新加的 broken-*.json 如果什么都没查出来，这条会失败。"""
    broken = {p.stem for p in (FIXTURES / "pois").glob("broken-*.json")}
    reported = {i.poi_id for i in fixture_report.issues}
    assert broken and broken <= reported


def test_cli_exit_code(capsys) -> None:
    assert main(["--data-dir", str(FIXTURES), "--today", TODAY]) == 1
    out = capsys.readouterr().out
    assert "没有通过" in out


# ---------- 用 tmp_path 现搭数据，测更细的情况 ----------


def run(tmp_path: Path, poi: dict, photos: list[str] | None = None, on: date = today):
    write_data_dir(tmp_path, [poi], {poi["id"]: photos if photos is not None else ["sample.jpg"]})
    return check_data_dir(tmp_path, on)


def test_good_poi_has_no_issues(tmp_path: Path) -> None:
    report = run(tmp_path, good_poi())
    assert report.ok and report.issues == []
    assert report.stats.placeholder == 3 and report.stats.todo == 3


def test_good_data_expires_later(tmp_path: Path) -> None:
    """同一份数据，到了过期日之后再检查，就该报已过期。"""
    report = run(tmp_path, good_poi(), on=date(2027, 2, 9))
    expired = {i.field for i in report.issues if i.code == "expired"}
    assert expired == {"openingHours", "reservation"}
    assert report.ok  # 过期是警告，不挡导入


def test_food_item_needs_expiry(tmp_path: Path) -> None:
    poi = good_poi()
    poi["food"] = [{"value": {"name": "测试小吃"}, "verification": "onsite", "sourceId": "visit", "lastCheckedAt": "2026-10-01"}]
    report = run(tmp_path, poi)
    assert any(i.code == "missing-expires-at" and i.field == "food[0]" for i in report.errors)


def test_missing_required_field(tmp_path: Path) -> None:
    poi = good_poi()
    del poi["payment"]
    assert "missing-field" in run(tmp_path, poi).codes()


def test_placeholder_must_not_cite_field_visit(tmp_path: Path) -> None:
    poi = good_poi()
    poi["address"]["verification"] = "placeholder"
    assert "verification-source-mismatch" in run(tmp_path, poi).codes()


def test_future_checked_date(tmp_path: Path) -> None:
    poi = good_poi()
    poi["address"]["lastCheckedAt"] = "2026-12-01"
    assert "future-date" in run(tmp_path, poi).codes()


def test_expiry_before_check(tmp_path: Path) -> None:
    poi = good_poi()
    poi["ticket"]["expiresAt"] = "2026-09-01"
    assert "bad-expiry" in run(tmp_path, poi).codes()


def test_source_without_url_or_date(tmp_path: Path) -> None:
    poi = good_poi()
    del poi["sources"][1]["url"]
    del poi["sources"][0]["accessedAt"]
    report = run(tmp_path, poi)
    assert sum(1 for i in report.errors if i.code == "bad-source") == 2


def test_todo_with_value(tmp_path: Path) -> None:
    poi = good_poi()
    poi["history"]["value"] = "没有来源的内容"
    assert "todo-with-value" in run(tmp_path, poi).codes()


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    poi = good_poi()
    poi["openingHour"] = poi.pop("openingHours")  # 字段名拼错
    codes = run(tmp_path, poi).codes()
    assert "bad-format" in codes


def test_bad_opening_hours(tmp_path: Path) -> None:
    poi = good_poi()
    poi["openingHours"]["value"]["periods"][0].update(open="18:00", close="09:00")
    assert "bad-opening-hours" in run(tmp_path, poi).codes()


def test_review_needs_author(tmp_path: Path) -> None:
    poi = good_poi()
    poi["reviews"][0]["author"] = " "
    assert "review-without-author" in run(tmp_path, poi).codes()


def test_placeholder_photo_missing_is_only_warning(tmp_path: Path) -> None:
    poi = good_poi()
    poi["photos"].append(
        {
            "file": "official.jpg",
            "caption": "测试占位照片",
            "license": "official-placeholder",
            "sourceUrl": "https://example.com/photo",
            "retrievedAt": "2026-11-10",
        }
    )
    report = run(tmp_path, poi)
    assert report.ok
    assert "placeholder-photo-missing" in report.codes()
    assert report.stats.placeholder_photos == 1


def test_placeholder_photo_needs_source(tmp_path: Path) -> None:
    poi = good_poi()
    poi["photos"].append({"file": "official.jpg", "caption": "测试", "license": "official-placeholder"})
    assert "bad-photo" in {i.code for i in run(tmp_path, poi).errors}


def test_unlisted_photo_file(tmp_path: Path) -> None:
    report = run(tmp_path, good_poi(), photos=["sample.jpg", "extra.jpg"])
    assert "photo-not-listed" in report.codes()


def test_id_must_match_filename(tmp_path: Path) -> None:
    poi = good_poi()
    write_data_dir(tmp_path, [poi], {"good-sample": ["sample.jpg"]})
    (tmp_path / "pois" / "good-sample.json").rename(tmp_path / "pois" / "other-name.json")
    assert "id-filename-mismatch" in check_data_dir(tmp_path, today).codes()


def test_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "pois").mkdir()
    (tmp_path / "pois" / "bad.json").write_text("{ 不是 json", encoding="utf-8")
    assert "bad-json" in check_data_dir(tmp_path, today).codes()


# ---------- 开放状态、多个来源、第三方占位照片（2026-11-15 加） ----------


def closed_status(**changes) -> dict:
    fact = {
        "value": {"code": "closed-temporarily", "note": "测试：修缮", "reopenExpected": "2026-12-14"},
        "verification": "confirmed",
        "sourceId": "official",
        "lastCheckedAt": "2026-11-10",
        "expiresAt": "2026-12-14",
    }
    fact.update(changes)
    return fact


def test_operating_status_is_optional_and_checked(tmp_path: Path) -> None:
    poi = good_poi()
    poi["operatingStatus"] = closed_status()
    assert run(tmp_path, poi).issues == []


def test_operating_status_needs_expiry(tmp_path: Path) -> None:
    poi = good_poi()
    poi["operatingStatus"] = closed_status(expiresAt=None)
    assert "missing-expires-at" in {i.code for i in run(tmp_path, poi).errors}


def test_extra_source_must_exist(tmp_path: Path) -> None:
    poi = good_poi()
    poi["intro"]["extraSourceIds"] = ["nowhere"]
    assert "unknown-source" in {i.code for i in run(tmp_path, poi).errors}


def test_third_party_placeholder_photo(tmp_path: Path) -> None:
    photo = {
        "file": "stock.jpg",
        "caption": "测试图库预览图",
        "license": "third-party-placeholder",
        "sourceUrl": "https://example.com/stock",
        "retrievedAt": "2026-11-10",
    }
    poi = good_poi()
    poi["photos"].append(dict(photo))
    assert "bad-photo" in {i.code for i in run(tmp_path, poi).errors}  # 没写出处和授权情况

    poi = good_poi()
    poi["photos"].append({**photo, "licenseNote": "测试图库，商用需授权"})
    report = run(tmp_path, poi)
    assert report.ok and report.stats.placeholder_photos == 1
