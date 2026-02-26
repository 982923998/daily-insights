#!/usr/bin/env python3
"""Generate personalized digest summary for a fetched JSON data file."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone


AI_MODEL_KEYWORDS = {
    "model",
    "llm",
    "foundation model",
    "open-weights",
    "checkpoint",
    "release",
    "released",
    "gpt",
    "claude",
    "gemini",
    "sonnet",
    "reasoning model",
}

AI_ARCH_KEYWORDS = {
    "architecture",
    "transformer",
    "moe",
    "mixture-of-experts",
    "agent",
    "multi-agent",
    "orchestrator",
    "framework",
    "sdk",
    "inference",
    "benchmark",
    "pipeline",
}

AI_BUSINESS_KEYWORDS = {
    "acquisition",
    "acquire",
    "acquired",
    "merger",
    "merge",
    "funding",
    "raised",
    "valuation",
    "ipo",
    "earnings",
    "revenue",
    "partnership",
    "lawsuit",
    "antitrust",
}

RESEARCH_ANALYSIS_KEYWORDS = {
    "mri",
    "fmri",
    "dti",
    "diffusion",
    "tensor",
    "voxel",
    "connectivity",
    "functional connectivity",
    "multimodal",
    "machine learning",
    "deep learning",
    "analysis",
    "perfusion",
    "spectroscopy",
    "resting-state",
    "graph",
    "biomarker",
}

RESEARCH_MECHANISM_KEYWORDS = {
    "mechanism",
    "pathophysiology",
    "neural",
    "circuit",
    "network",
    "disease",
    "alzheimer",
    "amyloid",
    "tau",
    "autism",
    "depression",
    "adhd",
    "parkinson",
    "schizophrenia",
    "cognitive decline",
}


def count_hits(text: str, keywords: set[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


def article_text(article: dict) -> str:
    return " ".join(
        str(article.get(k, ""))
        for k in ("title", "summary", "source", "subcategory", "category")
    ).lower()


def priority_from_score(score: int) -> str:
    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def infer_kind(domain_id: str, articles: list[dict]) -> str:
    if domain_id == "ai":
        return "ai"
    for article in articles:
        if str(article.get("category", "")).strip().lower() == "ai":
            return "ai"
    return "research"


def score_ai(article: dict) -> dict:
    text = article_text(article)
    model_hits = count_hits(text, AI_MODEL_KEYWORDS)
    arch_hits = count_hits(text, AI_ARCH_KEYWORDS)
    business_hits = count_hits(text, AI_BUSINESS_KEYWORDS)

    score = model_hits * 3 + arch_hits * 2 - business_hits * 3
    if model_hits == 0 and arch_hits == 0 and business_hits == 0:
        score = 1

    reasons = []
    if model_hits:
        reasons.append("mentions new models or releases")
    if arch_hits:
        reasons.append("contains architecture/agent/framework signals")
    if business_hits:
        reasons.append("business-heavy content (deprioritized)")
    if not reasons:
        reasons.append("general AI update")

    return {
        "score": score,
        "priority": priority_from_score(score),
        "reason": "; ".join(reasons),
        "model_hits": model_hits,
        "arch_hits": arch_hits,
        "business_hits": business_hits,
    }


def score_research(article: dict) -> dict:
    text = article_text(article)
    analysis_hits = count_hits(text, RESEARCH_ANALYSIS_KEYWORDS)
    mechanism_hits = count_hits(text, RESEARCH_MECHANISM_KEYWORDS)

    score = analysis_hits * 2 + mechanism_hits * 3
    if analysis_hits == 0 and mechanism_hits == 0:
        score = 1

    reasons = []
    if mechanism_hits:
        reasons.append("has disease/neural mechanism relevance")
    if analysis_hits:
        reasons.append("has imaging analysis/method relevance")
    if not reasons:
        reasons.append("general literature update")

    return {
        "score": score,
        "priority": priority_from_score(score),
        "reason": "; ".join(reasons),
        "analysis_hits": analysis_hits,
        "mechanism_hits": mechanism_hits,
    }


def build_digest(payload: dict, domain_id: str) -> dict:
    articles = payload.get("articles")
    if not isinstance(articles, list):
        articles = []

    kind = infer_kind(domain_id, articles)
    scored = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        metrics = score_ai(article) if kind == "ai" else score_research(article)
        scored.append({"article": article, "metrics": metrics})

    high = sum(1 for item in scored if item["metrics"]["priority"] == "high")
    medium = sum(1 for item in scored if item["metrics"]["priority"] == "medium")
    low = sum(1 for item in scored if item["metrics"]["priority"] == "low")

    topic_counts = Counter()
    if kind == "ai":
        topic_counts["new_model"] = sum(
            1 for item in scored if item["metrics"]["model_hits"] > 0
        )
        topic_counts["new_architecture"] = sum(
            1 for item in scored if item["metrics"]["arch_hits"] > 0
        )
        topic_counts["business_noise"] = sum(
            1 for item in scored if item["metrics"]["business_hits"] > 0
        )
    else:
        topic_counts["mechanism"] = sum(
            1 for item in scored if item["metrics"]["mechanism_hits"] > 0
        )
        topic_counts["analysis"] = sum(
            1 for item in scored if item["metrics"]["analysis_hits"] > 0
        )

    # Prefer high-score content; keep deterministic fallback.
    ranked = sorted(
        scored,
        key=lambda item: (
            item["metrics"]["score"],
            str(item["article"].get("published_date", "")),
            str(item["article"].get("title", "")),
        ),
        reverse=True,
    )
    recommendations = []
    for item in ranked:
        article = item["article"]
        metrics = item["metrics"]
        recommendations.append(
            {
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "published_date": article.get("published_date", ""),
                "priority": metrics["priority"],
                "reason": metrics["reason"],
            }
        )

    if kind == "ai":
        summary = (
            f"Captured {len(scored)} AI items. Preference focus is new models and "
            f"new technical architecture: {high} high-priority, {medium} medium-priority, "
            f"{low} low-priority. {topic_counts['business_noise']} business-heavy items "
            "were deprioritized."
        )
        preference = {
            "focus": ["new models", "new technical architecture"],
            "deprioritize": ["M&A and business-only updates"],
        }
        focus_topics = [
            {"topic": "new models", "count": topic_counts["new_model"]},
            {"topic": "new architecture", "count": topic_counts["new_architecture"]},
            {"topic": "business-heavy", "count": topic_counts["business_noise"]},
        ]
    else:
        summary = (
            f"Captured {len(scored)} research items. Preference focus is brain-imaging "
            f"analysis and disease mechanisms: {high} high-priority, {medium} medium-priority, "
            f"{low} low-priority. Mechanism-related items: {topic_counts['mechanism']}; "
            f"analysis-method items: {topic_counts['analysis']}."
        )
        preference = {
            "focus": ["brain imaging data analysis", "disease brain mechanisms"],
            "deprioritize": ["non-mechanism/non-analysis updates"],
        }
        focus_topics = [
            {"topic": "disease mechanism", "count": topic_counts["mechanism"]},
            {"topic": "imaging analysis", "count": topic_counts["analysis"]},
        ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": 1,
        "summary": summary,
        "preference": preference,
        "stats": {
            "total": len(scored),
            "high_priority": high,
            "medium_priority": medium,
            "low_priority": low,
        },
        "focus_topics": [t for t in focus_topics if t["count"] > 0],
        "recommendations": recommendations,
    }


def write_json(path: str, payload: dict) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate digest summary for fetched data")
    parser.add_argument("file", help="Target JSON data file")
    parser.add_argument("domain_id", nargs="?", default="", help="Domain id (e.g. ai, brainmri)")
    args = parser.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Top-level JSON payload must be an object")

    payload["digest"] = build_digest(payload, args.domain_id.strip().lower())
    write_json(args.file, payload)

    print(f"Digest generated: {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
