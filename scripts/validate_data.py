#!/usr/bin/env python3
"""Validate fetched data JSON structure and quality constraints."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.json$")
SPACE_RE = re.compile(r"\s+")
BASE_REQUIRED_FIELDS = ("title", "summary", "url", "category", "published_date", "date")
IF_REQUIRED_FIELDS = (
    "impact_factor",
    "impact_factor_year",
    "impact_factor_status",
    "impact_factor_source",
    "impact_factor_match_method",
    "impact_factor_matched_journal",
)
DOMAIN_CATEGORIES = {
    "ad": "Alzheimer",
    "adhd": "ADHD",
    "ai": "AI",
    "autism": "Autism",
    "brainmri": "Brain MRI",
    "depression": "Depression",
    "mefmri": "Multi-Echo fMRI",
    "pd": "Parkinson",
}
ENRICHED_STAGES = {"enriched", "final"}
UNKNOWN_IF_STATUSES = {"not_available_yet", "unresolved", "lookup_error"}


def infer_domain_id(path: Path) -> str:
    name = path.stem
    parts = name.rsplit("-", 1)
    if len(parts) == 2:
        return parts[1].strip().lower()
    return ""


def is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_valid_date(value: str) -> bool:
    return bool(DATE_RE.match(value))


def normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{netloc}{path}{query}"


def is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def normalize_title(value: str) -> str:
    return SPACE_RE.sub(" ", value.strip().lower())


def required_fields_for_domain(domain_id: str) -> tuple[str, ...]:
    if domain_id == "ai":
        return BASE_REQUIRED_FIELDS + ("subcategory",)
    return BASE_REQUIRED_FIELDS + ("source",)


def validate_payload(
    payload: object,
    domain_id: str,
    stage: str = "raw",
    minimum_impact_factor: float = 6.0,
) -> list[str]:
    errors: list[str] = []
    domain_id = (domain_id or "").strip().lower()
    stage = (stage or "").strip().lower()
    if stage not in {"raw", "enriched", "final"}:
        return [f'unsupported validation stage "{stage}"']
    if (
        isinstance(minimum_impact_factor, bool)
        or not isinstance(minimum_impact_factor, (int, float))
        or not math.isfinite(minimum_impact_factor)
    ):
        return ["minimum_impact_factor must be a finite number"]
    required_fields = required_fields_for_domain(domain_id)

    if not isinstance(payload, dict):
        return ["top-level JSON must be an object"]

    top_date = payload.get("date", "")
    if not is_non_empty_str(top_date):
        errors.append('top-level field "date" must be a non-empty string')
    elif not is_valid_date(top_date.strip()):
        errors.append('top-level field "date" must match YYYY-MM-DD')

    articles = payload.get("articles")
    if not isinstance(articles, list):
        errors.append('top-level field "articles" must be an array')
        return errors

    seen_pairs: dict[tuple[str, str], int] = {}
    seen_urls: dict[str, dict[str, object]] = {}

    for idx, article in enumerate(articles, start=1):
        if not isinstance(article, dict):
            errors.append(f"article #{idx}: must be an object")
            continue

        for field in required_fields:
            value = article.get(field)
            if not is_non_empty_str(value):
                errors.append(f'article #{idx}: field "{field}" must be a non-empty string')

        title = str(article.get("title", "")).strip()
        url = str(article.get("url", "")).strip()
        article_date = str(article.get("date", "")).strip()
        published_date = str(article.get("published_date", "")).strip()
        category = str(article.get("category", "")).strip()

        if published_date and not is_valid_date(published_date):
            errors.append(f"article #{idx}: field \"published_date\" must match YYYY-MM-DD")
        if article_date and not is_valid_date(article_date):
            errors.append(f"article #{idx}: field \"date\" must match YYYY-MM-DD")
        if top_date and article_date and article_date != top_date:
            errors.append(
                f"article #{idx}: field \"date\" ({article_date}) must equal top-level date ({top_date})"
            )

        if url and not is_valid_http_url(url):
            errors.append(f"article #{idx}: field \"url\" must be a valid http/https URL")

        expected_category = DOMAIN_CATEGORIES.get(domain_id)
        if expected_category and category and category != expected_category:
            errors.append(
                f'article #{idx}: category for domain "{domain_id}" must be '
                f'"{expected_category}" (got "{category}")'
            )

        if stage in ENRICHED_STAGES:
            for field in IF_REQUIRED_FIELDS:
                if field not in article:
                    errors.append(f'article #{idx}: missing enriched field "{field}"')

            status = article.get("impact_factor_status")
            impact_factor = article.get("impact_factor")
            if status == "available":
                if (
                    isinstance(impact_factor, bool)
                    or not isinstance(impact_factor, (int, float))
                    or not math.isfinite(impact_factor)
                    or impact_factor <= 0
                ):
                    errors.append(
                        f'article #{idx}: available status requires a positive finite numeric impact_factor'
                    )
                elif stage == "final" and impact_factor < minimum_impact_factor:
                    errors.append(
                        f"article #{idx}: impact_factor {impact_factor} is below minimum "
                        f"{minimum_impact_factor}"
                    )
                if not is_non_empty_str(article.get("impact_factor_source")):
                    errors.append(
                        f'article #{idx}: available status requires non-empty impact_factor_source'
                    )
                if not is_non_empty_str(article.get("impact_factor_matched_journal")):
                    errors.append(
                        f'article #{idx}: available status requires non-empty impact_factor_matched_journal'
                    )
            elif status in UNKNOWN_IF_STATUSES:
                if impact_factor is not None:
                    errors.append(
                        f'article #{idx}: {status} status requires null impact_factor'
                    )
                if status in {"unresolved", "lookup_error"} and not is_non_empty_str(
                    article.get("impact_factor_reason")
                ):
                    errors.append(
                        f'article #{idx}: {status} status requires impact_factor_reason'
                    )
            else:
                errors.append(
                    f'article #{idx}: unsupported impact_factor_status {status!r}'
                )

            year = article.get("impact_factor_year")
            if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
                errors.append(
                    f'article #{idx}: impact_factor_year must be an integer or null'
                )
            if not is_non_empty_str(article.get("impact_factor_match_method")):
                errors.append(
                    f'article #{idx}: impact_factor_match_method must be a non-empty string'
                )

        if title and url:
            normalized_url = normalize_url(url)
            normalized_title = normalize_title(title)
            pair_key = (normalized_url, normalized_title)

            if pair_key in seen_pairs:
                first_idx = seen_pairs[pair_key]
                errors.append(
                    f"article #{idx}: duplicate article key (url+title), first seen at article #{first_idx}"
                )
            else:
                seen_pairs[pair_key] = idx

            prev_for_url = seen_urls.get(normalized_url)
            if prev_for_url is not None:
                first_idx = int(prev_for_url["index"])
                first_title = str(prev_for_url["title"])
                errors.append(
                    "article "
                    f"#{idx}: duplicate URL, first seen at article #{first_idx} ({first_title})"
                )
            else:
                seen_urls[normalized_url] = {"index": idx, "title": title}

    return errors


def validate_file(
    path: Path,
    domain_id: str,
    stage: str = "raw",
    minimum_impact_factor: float = 6.0,
) -> list[str]:
    path = Path(path)
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid JSON: {exc}"]

    errors = validate_payload(
        payload,
        domain_id,
        stage=stage,
        minimum_impact_factor=minimum_impact_factor,
    )
    match = FILENAME_RE.match(path.name)
    if not match:
        errors.append("filename must match YYYY-MM-DD-<domain>.json")
        return errors

    filename_date, filename_domain = match.groups()
    top_date = payload.get("date") if isinstance(payload, dict) else None
    if isinstance(top_date, str) and top_date and filename_date != top_date:
        errors.append(
            f'filename date ({filename_date}) must equal top-level date ({top_date})'
        )
    normalized_domain = (domain_id or "").strip().lower()
    if normalized_domain and filename_domain.lower() != normalized_domain:
        errors.append(
            f'filename domain ({filename_domain}) must equal requested domain ({normalized_domain})'
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate fetched data JSON quality")
    parser.add_argument("file", help="Path to JSON file")
    parser.add_argument(
        "domain_id",
        nargs="?",
        default="",
        help="Domain id (e.g. ai, brainmri). If omitted, inferred from filename.",
    )
    parser.add_argument(
        "--stage",
        choices=("raw", "enriched", "final"),
        default="raw",
        help="Validation stage (default: raw)",
    )
    parser.add_argument(
        "--minimum-impact-factor",
        type=float,
        default=6.0,
        help="Inclusive minimum known IF for final-stage validation",
    )
    args = parser.parse_args()

    path = Path(args.file)
    domain_id = args.domain_id.strip().lower() or infer_domain_id(path)
    errors = validate_file(
        path,
        domain_id,
        stage=args.stage,
        minimum_impact_factor=args.minimum_impact_factor,
    )
    if errors:
        print(f"[ERROR] Data quality validation failed: {path}")
        for err in errors:
            print(f"  - {err}")
        return 1

    payload = json.loads(path.read_text(encoding="utf-8"))
    articles_len = len(payload.get("articles", [])) if isinstance(payload, dict) else 0
    print(
        f"Data quality validated: {path} "
        f"(domain={domain_id or 'unknown'}, articles={articles_len})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
