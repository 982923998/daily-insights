#!/usr/bin/env python3
"""Remove impact factor fields from daily data files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FIELDS = ("impact_factor", "impact_factor_year", "impact_factor_status")


def cleanup_file(path: Path) -> tuple[int, bool]:
    if not path.exists():
        return (0, False)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return (0, False)
    articles = payload.get("articles")
    if not isinstance(articles, list):
        return (0, False)
    changed = False
    removed = 0
    for article in articles:
        if not isinstance(article, dict):
            continue
        for field in FIELDS:
            if field in article:
                article.pop(field, None)
                removed += 1
                changed = True
    if changed:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return (removed, changed)


def default_targets(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob("????-??-??-*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove impact_factor fields from data files.")
    parser.add_argument("files", nargs="*", help="Target JSON files. Defaults to data/YYYY-MM-DD-*.json")
    parser.add_argument("--project-dir", default=".", help="Project root directory")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    data_dir = (project_dir / "data").resolve()
    files = [Path(f).resolve() if Path(f).is_absolute() else (project_dir / f).resolve() for f in args.files]
    if not files:
        files = default_targets(data_dir)

    total_removed = 0
    total_changed = 0
    for path in files:
        removed, changed = cleanup_file(path)
        total_removed += removed
        total_changed += 1 if changed else 0
        if changed:
            print(f"[OK] cleaned {path} (removed={removed})")
    print(f"[DONE] files_changed={total_changed}, fields_removed={total_removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
