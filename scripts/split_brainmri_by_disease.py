#!/usr/bin/env python3
"""Split one Brain MRI fetch into disease-specific daily data files."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from pathlib import Path


DOMAIN_CATEGORIES = {
    "brainmri": "Brain MRI",
    "autism": "Autism",
    "depression": "Depression",
    "adhd": "ADHD",
    "ad": "Alzheimer",
    "pd": "Parkinson",
}

DISEASE_DOMAINS = ("autism", "depression", "adhd", "ad", "pd")

DISEASE_PATTERNS = {
    "autism": (
        re.compile(r"\bautis(?:m|tic)\b", re.IGNORECASE),
        re.compile(r"\bASD\b", re.IGNORECASE),
        re.compile(r"\bautism spectrum\b", re.IGNORECASE),
    ),
    "depression": (
        re.compile(r"\bdepress(?:ion|ive|ed)\b", re.IGNORECASE),
        re.compile(r"\bmajor depressive\b", re.IGNORECASE),
        re.compile(r"\bMDD\b", re.IGNORECASE),
    ),
    "adhd": (
        re.compile(r"\bADHD\b", re.IGNORECASE),
        re.compile(r"\battention[- ]deficit\b", re.IGNORECASE),
        re.compile(r"\bhyperactivity disorder\b", re.IGNORECASE),
    ),
    "ad": (
        re.compile(r"\balzheimer(?:'s)?\b", re.IGNORECASE),
        re.compile(r"\bamyloid\b", re.IGNORECASE),
        re.compile(r"\btau\b", re.IGNORECASE),
        re.compile(r"\bmild cognitive impairment\b", re.IGNORECASE),
        re.compile(r"\bdementia\b", re.IGNORECASE),
    ),
    "pd": (
        re.compile(r"\bparkinson(?:'s|ian)?\b", re.IGNORECASE),
        re.compile(r"\bLewy bod(?:y|ies)\b", re.IGNORECASE),
    ),
}


def article_text(article: dict) -> str:
    return " ".join(
        str(article.get(key, ""))
        for key in ("title", "summary", "category", "source", "journal")
    )


def matched_domains(article: dict) -> list[str]:
    text = article_text(article)
    matches = [
        domain_id
        for domain_id, patterns in DISEASE_PATTERNS.items()
        if any(pattern.search(text) for pattern in patterns)
    ]

    if re.search(r"\bPD\b", text, re.IGNORECASE) and re.search(
        r"\b(tremor|dopamin|basal ganglia|motor symptom|parkinson)\b",
        text,
        re.IGNORECASE,
    ):
        if "pd" not in matches:
            matches.append("pd")

    return matches


def with_category(article: dict, domain_id: str) -> dict:
    copied = copy.deepcopy(article)
    copied["category"] = DOMAIN_CATEGORIES[domain_id]
    return copied


def split_payload(payload: dict) -> dict[str, dict]:
    if not isinstance(payload, dict):
        raise ValueError("Top-level JSON payload must be an object")

    date = str(payload.get("date", "")).strip()
    articles = payload.get("articles", [])
    if not isinstance(articles, list):
        raise ValueError('Top-level field "articles" must be an array')

    result = {
        domain_id: {"date": date, "articles": []}
        for domain_id in ("brainmri", *DISEASE_DOMAINS)
    }

    for article in articles:
        if not isinstance(article, dict):
            continue
        domains = matched_domains(article)
        if not domains:
            result["brainmri"]["articles"].append(with_category(article, "brainmri"))
            continue
        for domain_id in domains:
            result[domain_id]["articles"].append(with_category(article, domain_id))

    return result


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)


def write_split_files(input_path: Path, output_dir: Path | None = None) -> dict[str, int]:
    input_path = Path(input_path)
    output_dir = Path(output_dir) if output_dir is not None else input_path.parent

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    split = split_payload(payload)
    date = str(payload.get("date", "")).strip()
    if not date:
        raise ValueError('Top-level field "date" must be a non-empty string')

    counts = {}
    for domain_id, domain_payload in split.items():
        out_path = output_dir / f"{date}-{domain_id}.json"
        write_json(out_path, domain_payload)
        counts[domain_id] = len(domain_payload["articles"])

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split a YYYY-MM-DD-brainmri.json file into disease-specific daily files."
    )
    parser.add_argument("input", help="Path to the Brain MRI JSON file")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for split JSON files. Defaults to the input file directory.",
    )
    args = parser.parse_args()

    counts = write_split_files(
        Path(args.input),
        Path(args.output_dir) if args.output_dir else None,
    )
    print(
        "Split Brain MRI articles: "
        + ", ".join(f"{domain}={count}" for domain, count in counts.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
