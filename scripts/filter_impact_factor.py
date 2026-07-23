#!/usr/bin/env python3
"""Filter enriched article JSON files by impact factor."""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path


RETAINED_UNKNOWN_STATUSES = {"unresolved", "lookup_error"}


def filter_articles_by_if(articles, minimum=8.0):
    if not isinstance(articles, list):
        raise ValueError("articles must be an array")
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or not math.isfinite(minimum):
        raise ValueError("minimum must be a finite number")

    kept = []
    removed = 0
    unresolved = 0
    for index, article in enumerate(articles, start=1):
        if not isinstance(article, dict):
            raise ValueError(f"article #{index} must be an object")
        status = article.get("impact_factor_status")
        impact_factor = article.get("impact_factor")
        if status == "available":
            if (
                isinstance(impact_factor, bool)
                or not isinstance(impact_factor, (int, float))
                or not math.isfinite(impact_factor)
            ):
                raise ValueError(
                    f'article #{index}: available status requires a finite numeric impact_factor'
                )
            if impact_factor < minimum:
                removed += 1
                continue
        elif status == "not_available_yet":
            if impact_factor is not None:
                raise ValueError(
                    f'article #{index}: {status} status requires null impact_factor'
                )
            removed += 1
            continue
        elif status in RETAINED_UNKNOWN_STATUSES:
            if impact_factor is not None:
                raise ValueError(
                    f'article #{index}: {status} status requires null impact_factor'
                )
            unresolved += 1
        else:
            raise ValueError(f'article #{index}: unsupported impact_factor_status {status!r}')
        kept.append(dict(article))

    return kept, {"kept": len(kept), "removed": removed, "unresolved": unresolved}


def _atomic_write(path: Path, payload: dict) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def filter_file(path, minimum=8.0):
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON must be an object")
    filtered, stats = filter_articles_by_if(payload.get("articles"), minimum=minimum)
    payload["articles"] = filtered
    _atomic_write(path, payload)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter enriched articles by impact factor")
    parser.add_argument("file", type=Path, help="Article JSON file")
    parser.add_argument("--minimum", type=float, default=8.0, help="Inclusive minimum IF")
    args = parser.parse_args()
    stats = filter_file(args.file, minimum=args.minimum)
    print(json.dumps(stats, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
