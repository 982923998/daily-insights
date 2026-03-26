#!/usr/bin/env python3
"""Backfill IF field in Obsidian markdown notes from local LetPub datasets."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


def normalize_journal_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def normalize_issn(value: str) -> str:
    token = re.sub(r"[^0-9xX]", "", (value or ""))
    return token.upper()


def normalize_if_value_allow_zero(value):
    if value in (None, ""):
        return None
    try:
        num = float(value)
        if not math.isfinite(num) or num < 0:
            return None
        return num
    except (TypeError, ValueError):
        return None


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
        journals = payload.get("journals")
        if isinstance(journals, list):
            return [x for x in journals if isinstance(x, dict)]
    return []


def build_if_index(rows: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_name: dict[str, dict] = {}
    by_issn: dict[str, dict] = {}
    for item in rows:
        impact_factor_raw = normalize_if_value_allow_zero(item.get("impact_factor"))
        if impact_factor_raw is None:
            continue
        impact_factor = impact_factor_raw if impact_factor_raw > 0 else None
        if_year = item.get("impact_factor_year")
        if if_year in ("", None):
            if_year = item.get("if_year")

        candidates = [
            str(item.get("journal_name", "")).strip(),
            str(item.get("journal_name_short", "")).strip(),
            str(item.get("manual_full_name", "")).strip(),
        ]
        for candidate in candidates:
            key = normalize_journal_key(candidate)
            if not key:
                continue
            current = by_name.get(key)
            current_if = normalize_if_value_allow_zero(current.get("impact_factor")) if current else None
            if current_if is None:
                current_if = -1
            if impact_factor_raw > current_if:
                by_name[key] = {"impact_factor": impact_factor, "impact_factor_year": if_year}

        issn_key = normalize_issn(str(item.get("issn", "")).strip())
        if issn_key:
            current = by_issn.get(issn_key)
            current_if = normalize_if_value_allow_zero(current.get("impact_factor")) if current else None
            if current_if is None:
                current_if = -1
            if impact_factor_raw > current_if:
                by_issn[issn_key] = {"impact_factor": impact_factor, "impact_factor_year": if_year}
    return by_name, by_issn


def split_frontmatter(text: str) -> tuple[list[str] | None, int, int]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, -1, -1
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end == -1:
        return None, -1, -1
    return lines, 0, end


def get_field_value(lines: list[str], start: int, end: int, key: str) -> tuple[int, str]:
    needle = f"{key.lower()}:"
    for i in range(start + 1, end):
        s = lines[i].strip()
        if s.lower().startswith(needle):
            value = lines[i].split(":", 1)[1].strip()
            value = value.strip('"').strip("'")
            return i, value
    return -1, ""


def render_if_value(value) -> str:
    n = normalize_if_value_allow_zero(value)
    if n is None:
        return "None"
    if abs(n - int(n)) < 1e-9:
        return str(int(n))
    return f"{n:.3f}".rstrip("0").rstrip(".")


def should_fill_if(value: str) -> bool:
    token = (value or "").strip().lower()
    return token in ("", "none", "null", "n/a", "na", "-", "unknown")


def process_file(path: Path, by_name: dict[str, dict], by_issn: dict[str, dict], apply: bool) -> tuple[str, str, bool]:
    text = path.read_text(encoding="utf-8")
    parsed = split_frontmatter(text)
    lines, start, end = parsed
    if lines is None:
        return ("skip_no_frontmatter", "", False)

    journal_idx, journal_val = get_field_value(lines, start, end, "journal")
    if journal_idx == -1 or not journal_val:
        return ("skip_no_journal", "", False)

    if_idx, if_val = get_field_value(lines, start, end, "IF")
    if if_idx != -1 and not should_fill_if(if_val):
        return ("skip_has_if", "", False)

    issn_idx, issn_val = get_field_value(lines, start, end, "journal_issn")
    match = None
    issn_key = normalize_issn(issn_val) if issn_idx != -1 else ""
    if issn_key:
        match = by_issn.get(issn_key)
    if not match:
        match = by_name.get(normalize_journal_key(journal_val))
    if not match:
        return ("unmatched", journal_val, False)

    if match.get("impact_factor") in (None, ""):
        return ("matched_but_no_if", journal_val, False)

    new_if = render_if_value(match.get("impact_factor"))
    changed = False
    if if_idx != -1:
        newline = "\n" if lines[if_idx].endswith("\n") else ""
        new_line = f"IF: {new_if}{newline}"
        if lines[if_idx] != new_line:
            lines[if_idx] = new_line
            changed = True
    else:
        insert_at = journal_idx + 1
        line_ending = "\n"
        lines.insert(insert_at, f"IF: {new_if}{line_ending}")
        changed = True

    if changed and apply:
        path.write_text("".join(lines), encoding="utf-8")
    return ("filled", journal_val, changed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Obsidian IF from LetPub local JSON files.")
    parser.add_argument("--vault-dir", required=True, help="Target Obsidian folder")
    parser.add_argument("--project-dir", default=".", help="Project root")
    parser.add_argument("--apply", action="store_true", help="Write changes in place (default is dry-run)")
    parser.add_argument("--report", default="", help="Optional report file path")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    vault_dir = Path(args.vault_dir).resolve()
    letpub_unique = project_dir / "data" / "letpub" / "letpub_life_med_unique.json"
    letpub_raw = project_dir / "data" / "letpub" / "letpub_life_med_raw.json"

    rows = load_rows(letpub_unique) + load_rows(letpub_raw)
    by_name, by_issn = build_if_index(rows)

    stats = {
        "total_md": 0,
        "filled": 0,
        "unmatched": 0,
        "matched_but_no_if": 0,
        "skip_has_if": 0,
        "skip_no_journal": 0,
        "skip_no_frontmatter": 0,
    }
    unmatched: list[str] = []
    filled_files: list[str] = []

    for path in sorted(vault_dir.rglob("*.md")):
        stats["total_md"] += 1
        status, journal, changed = process_file(path, by_name, by_issn, apply=args.apply)
        stats[status] += 1
        if status == "unmatched":
            unmatched.append(f"{path}\t{journal}")
        if status == "filled" and changed:
            filled_files.append(str(path))

    lines = [
        f"mode={'apply' if args.apply else 'dry-run'}",
        f"vault_dir={vault_dir}",
        f"total_md={stats['total_md']}",
        f"filled={stats['filled']}",
        f"unmatched={stats['unmatched']}",
        f"matched_but_no_if={stats['matched_but_no_if']}",
        f"skip_has_if={stats['skip_has_if']}",
        f"skip_no_journal={stats['skip_no_journal']}",
        f"skip_no_frontmatter={stats['skip_no_frontmatter']}",
    ]
    if filled_files:
        lines.append("filled_files:")
        lines.extend(filled_files[:200])
    if unmatched:
        lines.append("unmatched_files:")
        lines.extend(unmatched[:500])

    output = "\n".join(lines) + "\n"
    print(output, end="")
    if args.report:
        Path(args.report).write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
