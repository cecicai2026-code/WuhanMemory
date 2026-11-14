"""命令行：检查景点资料。

用法（在 apps/api 目录下）：
    python -m app.data_quality                  # 检查 data/pois/
    python -m app.data_quality --today 2027-03-01   # 假设今天是这一天，看看到时候哪些会过期
    python -m app.data_quality --data-dir 其他目录

有 error 时退出码为 1，只有 warning 时为 0。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from app.core.config import settings
from app.data_quality.checker import CheckReport, check_data_dir
from app.data_quality.rules import today_in_city


def format_report(report: CheckReport, data_dir: Path, today: date) -> str:
    s = report.stats
    lines = [f"检查 {data_dir / 'pois'}（今天按 {today} 算）", ""]

    by_poi: dict[str, list[str]] = {}
    for issue in report.issues:
        by_poi.setdefault(issue.poi_id, []).append(str(issue))
    for poi_id in sorted(by_poi):
        lines.extend(by_poi[poi_id])
        lines.append("")

    lines += [
        f"景点 {s.pois} 个，信息 {s.facts} 条：实地核实 {s.onsite}，核对过来源 {s.confirmed}，"
        f"官网占位 {s.placeholder}，TODO {s.todo}，已过期 {s.expired}",
        f"照片：自己的或授权的 {s.own_photos} 张，官网占位 {s.placeholder_photos} 张"
        + ("（网站公开前必须换掉）" if s.placeholder_photos else ""),
        f"错误 {len(report.errors)} 个，警告 {len(report.warnings)} 个",
        "通过" if report.ok else "没有通过：有错误的景点不能导入数据库",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 data/pois/*.json 的数据质量")
    parser.add_argument("--data-dir", type=Path, default=settings.data_dir)
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="假设今天是哪天，格式 2026-11-15")
    args = parser.parse_args(argv)

    today = args.today or today_in_city()
    report = check_data_dir(args.data_dir, today)
    print(format_report(report, args.data_dir, today))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
