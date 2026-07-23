#!/usr/bin/env python3
"""Sync impact factors using LetPub data only.

This script does not rely on journal_impact_factors.json.
It reads IF from data/letpub, updates unresolved journals, and supports
manual journal-name inputs grouped by reference buckets.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


LET_PUB_SEARCH_URL = "https://letpub.com.cn/index.php?page=journalapp&view=search"
LET_PUB_BASE_URL = "https://letpub.com.cn/"
LETPUB_REFERENCE_DIRNAME = "references"
IF_STATUS_AVAILABLE = "available"
IF_STATUS_NOT_AVAILABLE_YET = "not_available_yet"
IF_STATUS_UNRESOLVED = "unresolved"
IF_STATUS_LOOKUP_ERROR = "lookup_error"

IF_RESULT_FIELDS = (
    "impact_factor",
    "impact_factor_year",
    "impact_factor_status",
    "impact_factor_source",
    "impact_factor_match_method",
    "impact_factor_matched_journal",
    "impact_factor_reason",
)

SOURCE_PRIORITIES = {
    "ordinary_raw": 100,
    "letpub": 100,
    "letpub_raw": 100,
    "unique_base": 200,
    "letpub_unique_base": 200,
    "legacy_crawler_supplement": 300,
    "letpub_unresolved_crawler": 300,
    "manual_override": 400,
}


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sanitize_reference(value: str) -> str:
    ref = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip().lower()).strip("-_")
    return ref or "default"


def normalize_journal_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def normalize_issn(value: str) -> str:
    token = re.sub(r"[^0-9xX]", "", (value or ""))
    return token.upper()


def format_issn(value: str) -> str:
    token = normalize_issn(value)
    if len(token) == 8:
        return f"{token[:4]}-{token[4:]}"
    return token


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


def normalize_if_year(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def default_unresolved_registry() -> dict:
    return {
        "schema_version": 1,
        "updated_at": now_iso_utc(),
        "journals": {},
    }


def load_unresolved_registry(path: Path) -> dict:
    if not path.exists():
        return default_unresolved_registry()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return default_unresolved_registry()
    journals = raw.get("journals", {})
    if not isinstance(journals, dict):
        journals = {}
    return {
        "schema_version": int(raw.get("schema_version", 1)),
        "updated_at": str(raw.get("updated_at", now_iso_utc())),
        "journals": journals,
    }


def load_letpub_journal_list(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"LetPub catalog not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid LetPub catalog JSON: {path}") from exc
    if isinstance(payload, dict):
        if "journals" in payload:
            journals = payload["journals"]
            if not isinstance(journals, list):
                raise ValueError(f'LetPub catalog field "journals" must be an array: {path}')
            return journals
        if "rows" in payload:
            rows = payload["rows"]
            if not isinstance(rows, list):
                raise ValueError(f'LetPub catalog field "rows" must be an array: {path}')
            return rows
        raise ValueError(f'LetPub catalog must contain "journals" or "rows": {path}')
    if isinstance(payload, list):
        return payload
    raise ValueError(f"LetPub catalog must be an object or array: {path}")


def payload_journal_entries(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    if "rows" in payload and isinstance(payload.get("rows"), list):
        return payload["rows"]
    if "journals" in payload and isinstance(payload.get("journals"), list):
        return payload["journals"]
    return []


def default_raw_letpub_payload() -> dict:
    return {
        "scraped_at": now_iso_utc(),
        "source": LET_PUB_SEARCH_URL,
        "fields": {},
        "raw_total": 0,
        "rows": [],
    }


def load_raw_letpub_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"LetPub raw catalog not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid LetPub raw catalog JSON: {path}") from exc
    if isinstance(payload, list):
        out = default_raw_letpub_payload()
        out["rows"] = payload
        out["raw_total"] = len(payload)
        return out
    if not isinstance(payload, dict):
        raise ValueError(f"LetPub raw catalog must be an object or array: {path}")
    out = dict(payload)
    rows = out.get("rows")
    if rows is not None and not isinstance(rows, list):
        raise ValueError(f'LetPub raw catalog field "rows" must be an array: {path}')
    if rows is None:
        journals = out.get("journals")
        if isinstance(journals, list):
            rows = journals
        else:
            raise ValueError(f'LetPub raw catalog must contain "rows" or "journals": {path}')
    out["rows"] = rows
    if "source" not in out or not isinstance(out.get("source"), str) or not out.get("source"):
        out["source"] = LET_PUB_SEARCH_URL
    if "scraped_at" not in out or not isinstance(out.get("scraped_at"), str) or not out.get("scraped_at"):
        out["scraped_at"] = now_iso_utc()
    out["raw_total"] = len(rows)
    return out


def default_supplement_payload() -> dict:
    return {
        "schema_version": 1,
        "source": "manual_override",
        "updated_at": now_iso_utc(),
        "journals": [],
    }


def load_supplement_payload(path: Path) -> dict:
    if not path.exists():
        return default_supplement_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid manual override JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"manual override catalog must be an object: {path}")
    journals = payload.get("journals", [])
    if not isinstance(journals, list):
        raise ValueError(f'manual override field "journals" must be an array: {path}')
    return {
        "schema_version": int(payload.get("schema_version", 1)),
        "source": str(payload.get("source", "manual_override")),
        "updated_at": str(payload.get("updated_at", now_iso_utc())),
        "journals": journals,
    }


def default_reference_payload(reference: str) -> dict:
    return {
        "schema_version": 1,
        "reference": sanitize_reference(reference),
        "source": "letpub_reference_task",
        "updated_at": now_iso_utc(),
        "journals": [],
    }


def load_reference_payload(path: Path, reference: str) -> dict:
    if not path.exists():
        return default_reference_payload(reference)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_reference_payload(reference)
    if not isinstance(payload, dict):
        return default_reference_payload(reference)
    journals = payload.get("journals", [])
    if not isinstance(journals, list):
        journals = []
    return {
        "schema_version": int(payload.get("schema_version", 1)),
        "reference": sanitize_reference(str(payload.get("reference", reference))),
        "source": str(payload.get("source", "letpub_reference_task")),
        "updated_at": str(payload.get("updated_at", now_iso_utc())),
        "journals": journals,
    }


def parse_manual_journal_line(raw: str) -> dict | None:
    line = (raw or "").strip()
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.split("|")]
    if len(parts) == 1:
        if not parts[0]:
            return None
        return {
            "journal_name": parts[0],
            "journal_issn": "",
            "manual_full_name": parts[0],
        }
    if len(parts) == 2:
        if not parts[0]:
            return None
        second = parts[1]
        if normalize_issn(second):
            return {
                "journal_name": parts[0],
                "journal_issn": second,
                "manual_full_name": parts[0],
            }
        return {
            "journal_name": parts[0],
            "journal_issn": "",
            "manual_full_name": second or parts[0],
        }
    if not parts[0]:
        return None
    return {
        "journal_name": parts[0],
        "journal_issn": parts[1],
        "manual_full_name": parts[2] if len(parts) > 2 and parts[2] else parts[0],
    }


def load_manual_journal_specs(journal_args: list[str], files: list[str], project_dir: Path) -> list[dict]:
    specs: list[dict] = []
    for item in journal_args:
        spec = parse_manual_journal_line(item)
        if spec:
            specs.append(spec)

    for file_arg in files:
        p = Path(file_arg)
        if not p.is_absolute():
            p = (project_dir / p).resolve()
        if not p.exists():
            continue
        if p.is_dir():
            continue
        if p.suffix.lower() == ".json":
            try:
                payload = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                payload = None
            items = []
            if isinstance(payload, dict):
                journals = payload.get("journals", [])
                if isinstance(journals, list):
                    items = journals
            elif isinstance(payload, list):
                items = payload
            for obj in items:
                if isinstance(obj, str):
                    spec = parse_manual_journal_line(obj)
                elif isinstance(obj, dict):
                    journal_name = str(obj.get("journal_name") or obj.get("name") or "").strip()
                    manual_full_name = str(obj.get("manual_full_name") or obj.get("full_name") or journal_name).strip()
                    journal_issn = str(obj.get("journal_issn") or obj.get("issn") or "").strip()
                    spec = {
                        "journal_name": journal_name,
                        "journal_issn": journal_issn,
                        "manual_full_name": manual_full_name,
                    } if journal_name else None
                else:
                    spec = None
                if spec:
                    specs.append(spec)
            continue

        for line in p.read_text(encoding="utf-8").splitlines():
            spec = parse_manual_journal_line(line)
            if spec:
                specs.append(spec)

    return dedupe_manual_specs(specs)


def dedupe_manual_specs(specs: list[dict]) -> list[dict]:
    dedup: dict[str, dict] = {}
    for spec in specs:
        key = "|".join(
            [
                normalize_journal_key(spec.get("journal_name", "")),
                normalize_issn(spec.get("journal_issn", "")),
                normalize_journal_key(spec.get("manual_full_name", "")),
            ]
        )
        dedup[key] = spec
    return list(dedup.values())


def load_unresolved_as_manual_specs(unresolved: dict) -> list[dict]:
    journals = unresolved.get("journals", {})
    if not isinstance(journals, dict):
        return []
    specs: list[dict] = []
    for key, entry in journals.items():
        if not isinstance(entry, dict):
            continue
        journal_name = str(entry.get("journal_name") or key).strip()
        if not journal_name:
            continue
        specs.append(
            {
                "journal_name": journal_name,
                "journal_issn": str(entry.get("journal_issn", "")).strip(),
                "manual_full_name": str(entry.get("manual_full_name") or journal_name).strip() or journal_name,
            }
        )
    return dedupe_manual_specs(specs)


def _source_priority(source: str) -> int:
    return SOURCE_PRIORITIES.get(source, SOURCE_PRIORITIES["ordinary_raw"])


def _candidate_from_row(item: dict) -> dict | None:
    source = str(item.get("source") or "ordinary_raw").strip() or "ordinary_raw"
    if source == "reference_audit" or item.get("audit_role") == "reference_only":
        return None

    explicit_status = str(item.get("impact_factor_status") or item.get("if_status") or "").strip()
    raw_value = normalize_if_value_allow_zero(item.get("impact_factor"))
    if raw_value is None:
        if explicit_status != IF_STATUS_UNRESOLVED:
            return None
        status = IF_STATUS_UNRESOLVED
        impact_factor = None
    elif raw_value == 0:
        status = IF_STATUS_NOT_AVAILABLE_YET
        impact_factor = None
    else:
        status = IF_STATUS_AVAILABLE
        impact_factor = raw_value

    year = normalize_if_year(item.get("impact_factor_year"))
    if year is None:
        year = normalize_if_year(item.get("if_year"))
    matched_journal = str(
        item.get("journal_name")
        or item.get("manual_full_name")
        or item.get("journal_name_short")
        or ""
    ).strip()
    return {
        "impact_factor": impact_factor,
        "impact_factor_year": year,
        "impact_factor_status": status,
        "impact_factor_source": source,
        "impact_factor_matched_journal": matched_journal,
        "_matched_issn": format_issn(item.get("issn") or item.get("journal_issn") or ""),
        "_source_priority": _source_priority(source),
    }


def _candidate_identity(candidate: dict) -> tuple:
    return (
        candidate["impact_factor"],
        candidate["impact_factor_year"],
        candidate["impact_factor_status"],
        candidate["impact_factor_source"],
        candidate["impact_factor_matched_journal"],
        candidate["_matched_issn"],
    )


def _choose_catalog_candidate(candidates: list[dict]) -> dict:
    unique = {_candidate_identity(candidate): candidate for candidate in candidates}
    pool = list(unique.values())
    top_priority = max(candidate["_source_priority"] for candidate in pool)
    pool = [candidate for candidate in pool if candidate["_source_priority"] == top_priority]
    if len(pool) == 1:
        return dict(pool[0])

    years = [candidate["impact_factor_year"] for candidate in pool]
    if any(year is None for year in years):
        selected = None
    else:
        newest_year = max(years)
        newest = [candidate for candidate in pool if candidate["impact_factor_year"] == newest_year]
        semantic = {
            (candidate["impact_factor"], candidate["impact_factor_status"])
            for candidate in newest
        }
        selected = min(
            newest,
            key=lambda candidate: candidate["impact_factor_matched_journal"].lower(),
        ) if len(semantic) == 1 else None
    if selected is not None:
        return dict(selected)

    sources = sorted({candidate["impact_factor_source"] for candidate in pool})
    journals = sorted({candidate["impact_factor_matched_journal"] for candidate in pool})
    return {
        "impact_factor": None,
        "impact_factor_year": None,
        "impact_factor_status": IF_STATUS_UNRESOLVED,
        "impact_factor_source": sources[0] if len(sources) == 1 else "+".join(sources),
        "impact_factor_matched_journal": journals[0] if len(journals) == 1 else "; ".join(journals),
        "impact_factor_reason": "conflict",
        "_source_priority": top_priority,
    }


def build_letpub_if_index(journals: list[dict]) -> dict[str, dict]:
    """Build a deterministic fact index without using reference-audit rows."""
    if not isinstance(journals, list):
        raise ValueError("LetPub journals must be an array")

    candidate_maps: dict[str, dict[str, list[dict]]] = {
        "by_issn": {},
        "by_name": {},
        "by_abbreviation": {},
    }
    for item in journals:
        if not isinstance(item, dict):
            raise ValueError("each LetPub journal row must be an object")
        candidate = _candidate_from_row(item)
        if candidate is None:
            continue

        issn = normalize_issn(str(item.get("issn") or item.get("journal_issn") or ""))
        if issn:
            candidate_maps["by_issn"].setdefault(issn, []).append(candidate)

        for name in (item.get("journal_name"), item.get("manual_full_name")):
            key = normalize_journal_key(str(name or ""))
            if key:
                candidate_maps["by_name"].setdefault(key, []).append(candidate)

        abbreviation = normalize_journal_key(str(item.get("journal_name_short") or ""))
        if abbreviation:
            candidate_maps["by_abbreviation"].setdefault(abbreviation, []).append(candidate)

    return {
        map_name: {
            key: _choose_catalog_candidate(candidates)
            for key, candidates in sorted(candidate_map.items())
        }
        for map_name, candidate_map in candidate_maps.items()
    }


def _unresolved_result(reason: str, *, status: str = IF_STATUS_UNRESOLVED) -> dict:
    return {
        "impact_factor": None,
        "impact_factor_year": None,
        "impact_factor_status": status,
        "impact_factor_source": None,
        "impact_factor_match_method": "none",
        "impact_factor_matched_journal": None,
        "impact_factor_reason": reason,
    }


def resolve_article_if(article: dict, letpub_index: dict[str, dict]) -> dict:
    """Resolve one article from local catalogs only."""
    journal_name = str(article.get("journal") or "").strip()
    if not journal_name:
        return _unresolved_result("missing_journal")

    matches = (
        (
            "exact_issn",
            letpub_index.get("by_issn", {}).get(
                normalize_issn(str(article.get("journal_issn") or article.get("issn") or ""))
            ),
        ),
        ("canonical_name", letpub_index.get("by_name", {}).get(normalize_journal_key(journal_name))),
        (
            "abbreviation",
            letpub_index.get("by_abbreviation", {}).get(normalize_journal_key(journal_name)),
        ),
    )
    for method, match in matches:
        if not match:
            continue
        result = {key: value for key, value in match.items() if not key.startswith("_")}
        result["impact_factor_match_method"] = method
        if result["impact_factor_status"] == IF_STATUS_UNRESOLVED:
            result.setdefault("impact_factor_reason", "catalog_unresolved")
        return result
    return _unresolved_result("no_match")


def apply_if_result(article: dict, result: dict) -> dict:
    """Return an article copy with only IF machine-state/provenance fields changed."""
    updated = dict(article)
    for field in IF_RESULT_FIELDS:
        updated.pop(field, None)
    for field in IF_RESULT_FIELDS:
        if field in result:
            updated[field] = result[field]
    return updated


def _letpub_request_url(searchname: str = "", searchissn: str = "") -> str:
    params = {
        "searchname": searchname,
        "searchissn": searchissn,
        "searchfield": "",
        "searchimpactlow": "",
        "searchimpacthigh": "",
        "searchimpacttrend": "",
        "searchscitype": "",
        "searchcategory1": "",
        "searchcategory2": "",
        "searchjcrkind": "",
        "searchopenaccess": "",
        "searchsort": "",
    }
    return f"{LET_PUB_SEARCH_URL}&{urllib.parse.urlencode(params)}"


def fetch_letpub_html(searchname: str = "", searchissn: str = "", timeout: int = 25) -> str:
    url = _letpub_request_url(searchname=searchname, searchissn=searchissn)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_letpub_rows(html: str) -> list[dict]:
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 is required for online LetPub parsing")
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != 12:
            continue
        issn_raw = str(tds[0].get_text(" ", strip=True))
        journal_link = tds[1].find("a")
        journal_name = str(journal_link.get_text(" ", strip=True)) if journal_link else ""
        journal_short_tag = tds[1].find("font")
        journal_name_short = str(journal_short_tag.get_text(" ", strip=True)) if journal_short_tag else ""
        detail_href = str(journal_link.get("href", "")) if journal_link else ""
        detail_url = urljoin(LET_PUB_BASE_URL, detail_href) if detail_href else ""
        jid_match = re.search(r"journalid=(\d+)", detail_href)
        journal_id = int(jid_match.group(1)) if jid_match else None
        metrics_text = str(tds[3].get_text(" ", strip=True))
        m_if = re.search(r"IF:\s*([0-9]+(?:\.[0-9]+)?)", metrics_text, re.I)
        m_h = re.search(r"h-index:\s*([0-9]+)", metrics_text, re.I)
        m_cs = re.search(r"CiteScore:\s*([0-9]+(?:\.[0-9]+)?)", metrics_text, re.I)
        if_value = float(m_if.group(1)) if m_if else None
        h_index = int(m_h.group(1)) if m_h else None
        citescore = float(m_cs.group(1)) if m_cs else None
        name_cell_text = str(tds[1].get_text(" ", strip=True))
        m_score = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*$", name_cell_text)
        overall_score = float(m_score.group(1)) if m_score else None
        rows.append(
            {
                "issn": format_issn(issn_raw),
                "journal_name": journal_name.strip(),
                "journal_name_short": journal_name_short.strip(),
                "journal_id": journal_id,
                "detail_url": detail_url,
                "article_url": (
                    f"https://letpub.com.cn/index.php?page=journalapp&view=detail&journalid={journal_id}&xuanxiangk_id=2#xuanxk_3"
                    if journal_id is not None
                    else detail_url
                ),
                "impact_factor": if_value,
                "h_index": h_index,
                "citescore": citescore,
                "overall_score": overall_score,
                "source": "letpub_unresolved_crawler",
            }
        )
    return rows


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def choose_best_row(rows: list[dict], journal_name: str, manual_full_name: str, journal_issn: str) -> dict | None:
    if not rows:
        return None
    target_issn = normalize_issn(journal_issn)
    targets = [manual_full_name, journal_name]
    dedup: dict[str, dict] = {}
    for row in rows:
        key = "|".join(
            [
                normalize_issn(str(row.get("issn", ""))),
                str(row.get("journal_id", "")),
                normalize_journal_key(str(row.get("journal_name", ""))),
            ]
        )
        dedup[key] = row
    unique_rows = list(dedup.values())
    best = None
    best_score = -1.0
    for row in unique_rows:
        score = 0.0
        row_issn = normalize_issn(str(row.get("issn", "")))
        if target_issn and row_issn and row_issn == target_issn:
            score += 1000
        row_names = [
            normalize_journal_key(str(row.get("journal_name", ""))),
            normalize_journal_key(str(row.get("journal_name_short", ""))),
        ]
        for target in targets:
            t = normalize_journal_key(target)
            if not t:
                continue
            score = max(score, max(_similarity(t, rn) for rn in row_names if rn) * 100)
        if row.get("impact_factor") is not None:
            score += 0.5
        if score > best_score:
            best_score = score
            best = row
    if best is None:
        return None
    if target_issn and normalize_issn(str(best.get("issn", ""))) == target_issn:
        return best
    if len(unique_rows) == 1:
        return best
    if best_score >= 70:
        return best
    return None


def choose_lookup_candidate(journal_name: str, journal_issn: str, manual_full_name: str) -> tuple[str, str] | None:
    issn = format_issn(journal_issn)
    if normalize_issn(issn):
        return ("issn", issn)
    manual = (manual_full_name or "").strip()
    if manual:
        return ("name", manual)
    name = (journal_name or "").strip()
    if name:
        return ("name", name)
    return None


def lookup_letpub_for_journal(
    journal_name: str,
    journal_issn: str,
    manual_full_name: str,
    cache: dict[str, list[dict]],
    timeout: int,
) -> tuple[dict | None, str]:
    candidate = choose_lookup_candidate(journal_name=journal_name, journal_issn=journal_issn, manual_full_name=manual_full_name)
    if not candidate:
        return None, ""
    qtype, qvalue = candidate
    cache_key = f"{qtype}:{qvalue.lower()}"
    if cache_key in cache:
        rows = cache[cache_key]
    else:
        if qtype == "issn":
            html = fetch_letpub_html(searchissn=qvalue, timeout=timeout)
        else:
            html = fetch_letpub_html(searchname=qvalue, timeout=timeout)
        rows = parse_letpub_rows(html)
        cache[cache_key] = rows

    best = choose_best_row(rows, journal_name=journal_name, manual_full_name=manual_full_name, journal_issn=journal_issn)
    return best, f"{qtype}:{qvalue}"


def supplement_identity_key(entry: dict) -> str:
    issn = normalize_issn(str(entry.get("issn", "")))
    if issn:
        return f"issn:{issn}"
    name_key = normalize_journal_key(str(entry.get("journal_name", "")))
    if name_key:
        return f"name:{name_key}"
    short_key = normalize_journal_key(str(entry.get("journal_name_short", "")))
    if short_key:
        return f"short:{short_key}"
    return ""


def make_supplement_entry(
    row: dict,
    journal_name: str,
    manual_full_name: str,
    journal_issn: str,
    query_trace: str,
    reference: str,
) -> dict:
    impact_factor = row.get("impact_factor")
    if impact_factor is None:
        impact_factor = 0.0
    ref = sanitize_reference(reference)
    return {
        "field": "manual_supplement",
        "field_tag": -1,
        "page": 0,
        "issn": format_issn(row.get("issn") or journal_issn),
        "journal_name": str(row.get("journal_name") or manual_full_name or journal_name).strip(),
        "journal_name_short": str(journal_name or row.get("journal_name_short") or "").strip(),
        "journal_id": row.get("journal_id"),
        "detail_url": str(row.get("detail_url", "")).strip(),
        "overall_score": row.get("overall_score"),
        "impact_factor": impact_factor,
        "impact_factor_year": normalize_if_year(row.get("impact_factor_year")),
        "h_index": row.get("h_index"),
        "citescore": row.get("citescore"),
        "cas_quartile": "",
        "big_category": "",
        "sub_category": "",
        "sci_indexed": "",
        "oa_status": "",
        "acceptance_rate": "",
        "review_cycle": "",
        "article_url": str(row.get("article_url", "")).strip(),
        "views": 0,
        "fields": ["manual_supplement"],
        "manual_full_name": str(manual_full_name or "").strip(),
        "reference": ref,
        "references": [ref],
        "matched_query": query_trace,
        "source": "manual_override",
        "updated_at": now_iso_utc(),
    }


def upsert_supplement_entry(payload: dict, new_entry: dict) -> bool:
    journals = payload.get("rows")
    target_key = "rows"
    if not isinstance(journals, list):
        journals = payload.get("journals")
        target_key = "journals"
    if not isinstance(journals, list):
        journals = []
    payload[target_key] = journals
    key = supplement_identity_key(new_entry)
    if not key:
        return False
    for i, old in enumerate(journals):
        if not isinstance(old, dict):
            continue
        if supplement_identity_key(old) == key:
            refs = set()
            for r in old.get("references", []):
                if isinstance(r, str) and r.strip():
                    refs.add(sanitize_reference(r))
            if isinstance(old.get("reference"), str) and old.get("reference", "").strip():
                refs.add(sanitize_reference(old["reference"]))
            for r in new_entry.get("references", []):
                if isinstance(r, str) and r.strip():
                    refs.add(sanitize_reference(r))
            if isinstance(new_entry.get("reference"), str) and new_entry.get("reference", "").strip():
                refs.add(sanitize_reference(new_entry["reference"]))
            merged = dict(old)
            merged.update(new_entry)
            merged["references"] = sorted(refs)
            old_without_time = {k: v for k, v in old.items() if k != "updated_at"}
            merged_without_time = {k: v for k, v in merged.items() if k != "updated_at"}
            if old_without_time == merged_without_time:
                return False
            journals[i] = merged
            return True
    journals.append(new_entry)
    return True


def update_unresolved_registry(
    unresolved: dict,
    unresolved_observed: dict[str, dict[str, object]],
    resolved_keys: set[str],
    capture_date: str,
    last_file: str,
):
    before_journals = json.dumps(unresolved.get("journals", {}), ensure_ascii=False, sort_keys=True)
    unresolved_journals = unresolved.get("journals", {})
    if not isinstance(unresolved_journals, dict):
        unresolved_journals = {}
    for key, existing in list(unresolved_journals.items()):
        if not isinstance(existing, dict):
            continue
        legacy_last_file = str(existing.get("last_file", "")).strip()
        if not legacy_last_file:
            continue
        files = {
            str(file_name).strip()
            for file_name in existing.get("files", [])
            if isinstance(file_name, str) and str(file_name).strip()
        }
        files.add(legacy_last_file)
        migrated = dict(existing)
        migrated.pop("last_file", None)
        migrated["files"] = sorted(files)
        unresolved_journals[key] = migrated
    for key in resolved_keys:
        unresolved_journals.pop(key, None)
    for key, meta in unresolved_observed.items():
        existing = unresolved_journals.get(key, {})
        if not isinstance(existing, dict):
            existing = {}
        seen_count_prev = int(existing.get("seen_count", 0) or 0)
        files = {
            str(file_name).strip()
            for file_name in existing.get("files", [])
            if isinstance(file_name, str) and str(file_name).strip()
        }
        legacy_last_file = str(existing.get("last_file", "")).strip()
        if legacy_last_file:
            files.add(legacy_last_file)
        is_new_file = bool(last_file and last_file not in files)
        if last_file:
            files.add(last_file)
        manual_full_name = str(meta.get("manual_full_name", "")).strip() or str(existing.get("manual_full_name", "")).strip()
        notes = (
            str(meta.get("notes", "")).strip()
            or str(existing.get("notes", "")).strip()
            or "未查到影响因子，待人工补充期刊全称或外部来源"
        )
        unresolved_journals[key] = {
            "journal_name": key,
            "journal_issn": str(meta.get("journal_issn", "")).strip() or str(existing.get("journal_issn", "")).strip(),
            "first_seen": str(existing.get("first_seen", capture_date)),
            "last_seen": max(str(existing.get("last_seen", capture_date)), capture_date),
            "seen_count": seen_count_prev + (1 if is_new_file else 0),
            "files": sorted(files),
            "manual_full_name": manual_full_name,
            "notes": notes,
        }
    unresolved["journals"] = {
        k: unresolved_journals[k] for k in sorted(unresolved_journals.keys(), key=lambda s: s.lower())
    }
    after_journals = json.dumps(unresolved["journals"], ensure_ascii=False, sort_keys=True)
    if after_journals != before_journals:
        unresolved["updated_at"] = now_iso_utc()


def infer_capture_date(path: Path) -> str:
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-", path.name)
    if m:
        return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def _atomic_write_json(path: Path, payload: dict) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _annotate_catalog_source(entries: list[dict], default_source: str) -> list[dict]:
    annotated = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each LetPub journal row must be an object")
        row = dict(entry)
        source = str(row.get("source") or "").strip()
        if default_source == "ordinary_raw" and source == "letpub_unresolved_crawler":
            row["source"] = "legacy_crawler_supplement"
        else:
            row["source"] = default_source
        annotated.append(row)
    return annotated


def _if_projection(article: dict) -> dict:
    return {field: article.get(field) for field in IF_RESULT_FIELDS if field in article}


def process_data_file(
    path: Path,
    base_entries: list[dict],
    letpub_index: dict[str, dict],
    unresolved: dict,
    supplement_payload: dict,
    reference_payload: dict,
    reference: str,
    crawl_online: bool,
    timeout: int,
    query_cache: dict[str, list[dict]],
) -> tuple[int, int]:
    if not path.exists():
        return (0, 0)
    data = json.loads(path.read_text(encoding="utf-8"))
    articles = data.get("articles", [])
    if not isinstance(articles, list):
        return (0, 0)

    unresolved_journals = unresolved.get("journals", {})
    if not isinstance(unresolved_journals, dict):
        unresolved_journals = {}
        unresolved["journals"] = unresolved_journals
    unresolved_key_index = {
        str(k).strip().lower(): str(k).strip()
        for k in unresolved_journals.keys()
        if isinstance(k, str) and str(k).strip()
    }
    unresolved_observed: dict[str, dict[str, object]] = {}
    resolved_keys: set[str] = set()
    supplement_changed = 0
    capture_date = infer_capture_date(path)

    def resolve_key(journal_name: str) -> str:
        existing = unresolved_key_index.get(journal_name.strip().lower())
        if existing:
            return existing
        unresolved_key_index[journal_name.strip().lower()] = journal_name.strip()
        return journal_name.strip()

    before_articles = [dict(article) if isinstance(article, dict) else article for article in articles]
    updated_articles = []
    for article in articles:
        if not isinstance(article, dict):
            updated_articles.append(article)
            continue
        journal_name = str(article.get("journal", "")).strip()
        if not journal_name:
            updated_articles.append(apply_if_result(article, _unresolved_result("missing_journal")))
            continue
        key = resolve_key(journal_name)
        article_issn = normalize_issn(str(article.get("journal_issn", "")).strip())
        unresolved_entry = unresolved_journals.get(key, {})
        manual_full_name = ""
        if isinstance(unresolved_entry, dict):
            manual_full_name = str(unresolved_entry.get("manual_full_name", "")).strip()
        resolution_article = dict(article)
        if manual_full_name and normalize_journal_key(journal_name) not in letpub_index.get("by_name", {}):
            resolution_article["journal"] = manual_full_name
        result = resolve_article_if(resolution_article, letpub_index)

        if result.get("impact_factor_reason") == "no_match" and crawl_online:
            try:
                row, trace = lookup_letpub_for_journal(
                    journal_name=journal_name,
                    journal_issn=article_issn,
                    manual_full_name=manual_full_name,
                    cache=query_cache,
                    timeout=timeout,
                )
            except Exception:
                row = None
                trace = ""
                result = _unresolved_result(
                    "network_or_parse_error",
                    status=IF_STATUS_LOOKUP_ERROR,
                )
            if row:
                new_entry = make_supplement_entry(
                    row=row,
                    journal_name=journal_name,
                    manual_full_name=manual_full_name,
                    journal_issn=article_issn,
                    query_trace=trace,
                    reference=reference,
                )
                if upsert_supplement_entry(supplement_payload, new_entry):
                    supplement_changed += 1
                audit_entry = dict(new_entry)
                audit_entry["source"] = "reference_audit"
                audit_entry["audit_role"] = "reference_only"
                if upsert_supplement_entry(reference_payload, audit_entry):
                    supplement_changed += 1
                letpub_index = build_letpub_if_index(
                    base_entries
                    + _annotate_catalog_source(
                        payload_journal_entries(supplement_payload),
                        "manual_override",
                    )
                )
                result = resolve_article_if(resolution_article, letpub_index)

        updated_article = apply_if_result(article, result)
        updated_articles.append(updated_article)
        if result["impact_factor_status"] in (IF_STATUS_AVAILABLE, IF_STATUS_NOT_AVAILABLE_YET):
            resolved_keys.add(key)
        else:
            unresolved_observed[key] = {
                "journal_issn": format_issn(article_issn),
                "hit_count": 1,
                "manual_full_name": manual_full_name,
                "notes": f"impact_factor_reason={result.get('impact_factor_reason', 'unresolved')}",
            }

    data["articles"] = updated_articles
    _atomic_write_json(path, data)
    readback = json.loads(path.read_text(encoding="utf-8"))
    readback_articles = readback.get("articles", [])
    changed_count = sum(
        1
        for before, after in zip(before_articles, readback_articles)
        if isinstance(before, dict)
        and isinstance(after, dict)
        and _if_projection(before) != _if_projection(after)
    )

    update_unresolved_registry(
        unresolved=unresolved,
        unresolved_observed=unresolved_observed,
        resolved_keys=resolved_keys,
        capture_date=capture_date,
        last_file=path.name,
    )
    return (changed_count, supplement_changed)


def collect_default_files(data_dir: Path, unresolved: dict) -> list[Path]:
    journals = unresolved.get("journals", {})
    if not isinstance(journals, dict):
        return []
    files = []
    for entry in journals.values():
        if not isinstance(entry, dict):
            continue
        registered_files = entry.get("files", [])
        if not isinstance(registered_files, list):
            registered_files = []
        legacy_last_file = str(entry.get("last_file", "")).strip()
        if legacy_last_file:
            registered_files = [*registered_files, legacy_last_file]
        for file_name in registered_files:
            file_name = str(file_name).strip()
            if not file_name.lower().endswith(".json"):
                continue
            p = data_dir / file_name
            if p.exists():
                files.append(p)
    dedup = sorted({str(p): p for p in files}.values(), key=lambda p: p.name)
    return dedup


def _manual_unresolved_entry(
    existing: dict,
    journal_name: str,
    journal_issn: str,
    manual_full_name: str,
    today: str,
    reference: str,
) -> dict:
    files = {
        str(file_name).strip()
        for file_name in existing.get("files", [])
        if isinstance(file_name, str) and str(file_name).strip()
    }
    legacy_last_file = str(existing.get("last_file", "")).strip()
    if legacy_last_file:
        files.add(legacy_last_file)
    return {
        "journal_name": journal_name,
        "journal_issn": format_issn(journal_issn)
        or str(existing.get("journal_issn", "")).strip(),
        "first_seen": str(existing.get("first_seen", today)),
        "last_seen": max(str(existing.get("last_seen", today)), today),
        "seen_count": max(1, int(existing.get("seen_count", 0) or 0)),
        "files": sorted(files),
        "manual_full_name": manual_full_name,
        "notes": str(
            existing.get(
                "notes",
                f"手动输入期刊（reference={sanitize_reference(reference)}）未在 LetPub 命中",
            )
        ),
    }


def process_manual_journal_specs(
    specs: list[dict],
    letpub_index: dict[str, dict],
    unresolved: dict,
    supplement_payload: dict,
    reference_payload: dict,
    reference: str,
    crawl_online: bool,
    timeout: int,
    workers: int,
    query_cache: dict[str, list[dict]],
) -> tuple[int, int, int]:
    found = 0
    updated = 0
    unresolved_added = 0
    if not specs:
        return (0, 0, 0)

    before_journals = json.dumps(unresolved.get("journals", {}), ensure_ascii=False, sort_keys=True)
    unresolved_journals = unresolved.get("journals", {})
    if not isinstance(unresolved_journals, dict):
        unresolved_journals = {}
        unresolved["journals"] = unresolved_journals

    today = datetime.now().strftime("%Y-%m-%d")
    by_name = letpub_index.get("by_name", {})
    by_issn = letpub_index.get("by_issn", {})
    online_specs: list[dict] = []
    start_ts = time.time()
    for spec in specs:
        journal_name = str(spec.get("journal_name", "")).strip()
        manual_full_name = str(spec.get("manual_full_name", "")).strip() or journal_name
        journal_issn = str(spec.get("journal_issn", "")).strip()
        if not journal_name:
            continue
        local_match = None
        norm_issn = normalize_issn(journal_issn)
        if norm_issn:
            local_match = by_issn.get(norm_issn)
        if not local_match:
            local_match = by_name.get(normalize_journal_key(manual_full_name)) or by_name.get(normalize_journal_key(journal_name))

        if local_match and local_match.get("impact_factor_status") not in (
            IF_STATUS_AVAILABLE,
            IF_STATUS_NOT_AVAILABLE_YET,
        ):
            existing = unresolved_journals.get(journal_name, {})
            if not isinstance(existing, dict):
                existing = {}
            unresolved_entry = _manual_unresolved_entry(
                existing,
                journal_name,
                journal_issn,
                manual_full_name,
                today,
                reference,
            )
            unresolved_entry["impact_factor_status"] = IF_STATUS_UNRESOLVED
            unresolved_entry["impact_factor_reason"] = str(
                local_match.get("impact_factor_reason") or "catalog_unresolved"
            )
            unresolved_journals[journal_name] = unresolved_entry
            unresolved_added += 1
            continue

        if local_match:
            row = {
                "issn": format_issn(local_match.get("_matched_issn") or journal_issn),
                "journal_name": str(
                    local_match.get("impact_factor_matched_journal")
                    or manual_full_name
                    or journal_name
                ).strip(),
                "journal_name_short": journal_name,
                "impact_factor": local_match.get("impact_factor"),
                "impact_factor_year": local_match.get("impact_factor_year"),
                "source": local_match.get("impact_factor_source", "letpub_local_index"),
            }
            found += 1
            new_entry = make_supplement_entry(
                row=row,
                journal_name=journal_name,
                manual_full_name=manual_full_name,
                journal_issn=journal_issn,
                query_trace="local-index",
                reference=reference,
            )
            if local_match.get("impact_factor_source") == "manual_override":
                new_key = supplement_identity_key(new_entry)
                existing_entry = next(
                    (
                        entry
                        for entry in payload_journal_entries(supplement_payload)
                        if isinstance(entry, dict)
                        and supplement_identity_key(entry) == new_key
                        and sanitize_reference(str(entry.get("reference", "")))
                        == sanitize_reference(reference)
                    ),
                    None,
                )
                if existing_entry is not None:
                    new_entry = dict(existing_entry)
            if upsert_supplement_entry(supplement_payload, new_entry):
                updated += 1
            audit_entry = dict(new_entry)
            audit_entry["source"] = "reference_audit"
            audit_entry["audit_role"] = "reference_only"
            if upsert_supplement_entry(reference_payload, audit_entry):
                updated += 1
            unresolved_journals.pop(journal_name, None)
            continue
        online_specs.append(
            {
                "journal_name": journal_name,
                "manual_full_name": manual_full_name,
                "journal_issn": journal_issn,
            }
        )

    if crawl_online and online_specs:
        total = len(online_specs)
        max_workers = max(1, min(int(workers or 1), total))
        print(f"[INFO] online lookup start: total={total}, workers={max_workers}, timeout={timeout}s, mode=single-pass", flush=True)

        def _task(spec: dict) -> tuple[dict, dict | None, str]:
            row, trace = lookup_letpub_for_journal(
                journal_name=spec["journal_name"],
                journal_issn=spec["journal_issn"],
                manual_full_name=spec["manual_full_name"],
                cache={},
                timeout=timeout,
            )
            return spec, row, trace

        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(_task, spec): spec for spec in online_specs}
            for future in concurrent.futures.as_completed(future_map):
                done += 1
                spec = future_map[future]
                journal_name = spec["journal_name"]
                manual_full_name = spec["manual_full_name"]
                journal_issn = spec["journal_issn"]
                lookup_failed = False
                try:
                    _, row, trace = future.result()
                except Exception as exc:
                    row = None
                    trace = f"error:{exc}"
                    lookup_failed = True

                if row:
                    found += 1
                    new_entry = make_supplement_entry(
                        row=row,
                        journal_name=journal_name,
                        manual_full_name=manual_full_name,
                        journal_issn=journal_issn,
                        query_trace=trace,
                        reference=reference,
                    )
                    if upsert_supplement_entry(supplement_payload, new_entry):
                        updated += 1
                    audit_entry = dict(new_entry)
                    audit_entry["source"] = "reference_audit"
                    audit_entry["audit_role"] = "reference_only"
                    if upsert_supplement_entry(reference_payload, audit_entry):
                        updated += 1
                    unresolved_journals.pop(journal_name, None)
                    print(f"[PROGRESS] {done}/{total} found: {journal_name}", flush=True)
                    continue

                key = journal_name
                existing = unresolved_journals.get(key, {})
                if not isinstance(existing, dict):
                    existing = {}
                unresolved_entry = _manual_unresolved_entry(
                    existing,
                    key,
                    journal_issn,
                    manual_full_name,
                    today,
                    reference,
                )
                unresolved_entry["impact_factor_status"] = (
                    IF_STATUS_LOOKUP_ERROR if lookup_failed else IF_STATUS_UNRESOLVED
                )
                unresolved_entry["impact_factor_reason"] = (
                    "network_or_parse_error" if lookup_failed else "no_match"
                )
                unresolved_journals[key] = unresolved_entry
                unresolved_added += 1
                state = "lookup_error" if lookup_failed else "not_found"
                print(f"[PROGRESS] {done}/{total} {state}: {journal_name}", flush=True)
    elif online_specs:
        for spec in online_specs:
            journal_name = spec["journal_name"]
            manual_full_name = spec["manual_full_name"]
            journal_issn = spec["journal_issn"]
            key = journal_name
            existing = unresolved_journals.get(key, {})
            if not isinstance(existing, dict):
                existing = {}
            unresolved_journals[key] = _manual_unresolved_entry(
                existing,
                key,
                journal_issn,
                manual_full_name,
                today,
                reference,
            )
            unresolved_added += 1

    unresolved["journals"] = {
        k: unresolved_journals[k] for k in sorted(unresolved_journals.keys(), key=lambda s: s.lower())
    }
    after_journals = json.dumps(unresolved["journals"], ensure_ascii=False, sort_keys=True)
    if after_journals != before_journals:
        unresolved["updated_at"] = now_iso_utc()
    elapsed = time.time() - start_ts
    print(f"[INFO] manual lookup elapsed={elapsed:.1f}s", flush=True)
    return (found, updated, unresolved_added)


def _semantic_payload(payload: dict) -> str:
    stable = {key: value for key, value in payload.items() if key != "updated_at"}
    return json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_payload_if_changed(path: Path, payload: dict, before_semantic: str) -> bool:
    if _semantic_payload(payload) == before_semantic:
        return False
    payload["updated_at"] = now_iso_utc()
    _atomic_write_json(path, payload)
    return True


def run(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    data_dir = (project_dir / "data").resolve()
    unresolved_path = data_dir / "if_unresolved_journals.json"
    letpub_dir = data_dir / "letpub"
    reference_dir = letpub_dir / LETPUB_REFERENCE_DIRNAME
    base_letpub_path = letpub_dir / "letpub_life_med_unique.json"
    raw_letpub_path = letpub_dir / "letpub_life_med_raw.json"
    manual_override_path = letpub_dir / "letpub_manual_overrides.json"
    reference = sanitize_reference(args.reference)
    reference_path = reference_dir / f"{reference}.json"

    if BeautifulSoup is None and not args.no_crawl:
        print(
            "[WARN] beautifulsoup4 is not installed; disable online crawling "
            "and fallback to local LetPub data only.",
            flush=True,
        )
        args.no_crawl = True
    if args.retries is not None:
        print("[WARN] --retries is deprecated and ignored; each journal is queried only once.")

    unresolved = load_unresolved_registry(unresolved_path)
    raw_payload = load_raw_letpub_payload(raw_letpub_path)
    supplement_payload = load_supplement_payload(manual_override_path)
    reference_payload = load_reference_payload(reference_path, reference)
    base_entries = load_letpub_journal_list(base_letpub_path)
    local_catalog_entries = (
        _annotate_catalog_source(base_entries, "unique_base")
        + _annotate_catalog_source(payload_journal_entries(raw_payload), "ordinary_raw")
    )
    manual_before = _semantic_payload(supplement_payload)
    reference_before = _semantic_payload(reference_payload)
    unresolved_before = _semantic_payload(unresolved)

    for file_arg in args.journals_file:
        p = Path(file_arg)
        if not p.is_absolute():
            p = (project_dir / p).resolve()
        if p.exists() and p.is_dir():
            print(f"[ERROR] --journals-file expects a file, got directory: {p}")
            return 1

    manual_specs = load_manual_journal_specs(args.journal, args.journals_file, project_dir)
    files = [Path(f).resolve() if Path(f).is_absolute() else (project_dir / f).resolve() for f in args.files]
    if not files:
        files = collect_default_files(data_dir, unresolved)

    if not files and not manual_specs:
        manual_specs = load_unresolved_as_manual_specs(unresolved)
        if manual_specs:
            print(
                f"[INFO] No target data files found; fallback to direct unresolved lookup (count={len(manual_specs)}).",
                flush=True,
            )
        else:
            print("[INFO] No target data files and no unresolved journals found; nothing to crawl.", flush=True)

    query_cache: dict[str, list[dict]] = {}
    total_applied = 0
    total_supplement = 0
    manual_found = 0
    manual_unresolved = 0

    if manual_specs:
        manual_index = build_letpub_if_index(
            local_catalog_entries
            + _annotate_catalog_source(
                payload_journal_entries(supplement_payload),
                "manual_override",
            )
        )
        mf, mu, mu_unresolved = process_manual_journal_specs(
            specs=manual_specs,
            letpub_index=manual_index,
            unresolved=unresolved,
            supplement_payload=supplement_payload,
            reference_payload=reference_payload,
            reference=reference,
            crawl_online=(not args.no_crawl),
            timeout=args.timeout,
            workers=args.workers,
            query_cache=query_cache,
        )
        manual_found += mf
        total_supplement += mu
        manual_unresolved += mu_unresolved
        print(
            f"[OK] manual journals processed: total={len(manual_specs)}, found={manual_found}, "
            f"unresolved_added={manual_unresolved}, letpub_updates={mu}"
        )

    for file_path in files:
        letpub_index = build_letpub_if_index(
            local_catalog_entries
            + _annotate_catalog_source(
                payload_journal_entries(supplement_payload),
                "manual_override",
            )
        )
        applied, changed = process_data_file(
            path=file_path,
            base_entries=local_catalog_entries,
            letpub_index=letpub_index,
            unresolved=unresolved,
            supplement_payload=supplement_payload,
            reference_payload=reference_payload,
            reference=reference,
            crawl_online=(not args.no_crawl),
            timeout=args.timeout,
            query_cache=query_cache,
        )
        total_applied += applied
        total_supplement += changed
        print(f"[OK] IF synced: {file_path} (applied={applied}, letpub_updates={changed})")

    manual_entries = payload_journal_entries(supplement_payload)
    if isinstance(manual_entries, list):
        manual_entries.sort(
            key=lambda x: normalize_journal_key(str((x or {}).get("journal_name", "")))
        )
    ref_journals = reference_payload.get("journals", [])
    if isinstance(ref_journals, list):
        ref_journals.sort(key=lambda x: normalize_journal_key(str((x or {}).get("journal_name", ""))))
    letpub_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)
    _write_payload_if_changed(manual_override_path, supplement_payload, manual_before)
    _write_payload_if_changed(reference_path, reference_payload, reference_before)
    _write_payload_if_changed(unresolved_path, unresolved, unresolved_before)

    unresolved_count = len((unresolved.get("journals") or {}))
    supplement_count = len(payload_journal_entries(supplement_payload))
    reference_count = len((reference_payload.get("journals") or []))
    print(
        f"[DONE] reference={reference}, unresolved={unresolved_count}, "
        f"manual_overrides={supplement_count}, letpub_reference={reference_count}, "
        f"total_applied={total_applied}, total_letpub_updates={total_supplement}, "
        f"manual_found={manual_found}, manual_unresolved_added={manual_unresolved}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync impact factors from LetPub folder + unresolved crawl")
    parser.add_argument(
        "files",
        nargs="*",
        help="Target data JSON files. If omitted, uses files entries from if_unresolved_journals.json.",
    )
    parser.add_argument("--project-dir", default=".", help="Project root directory")
    parser.add_argument(
        "--journal",
        action="append",
        default=[],
        help="Manual journal input. Format: name OR name|issn OR name|issn|manual_full_name",
    )
    parser.add_argument(
        "--journals-file",
        action="append",
        default=[],
        help="Path to txt/json file for manual journal inputs",
    )
    parser.add_argument(
        "--reference",
        default="auto-unresolved",
        help="Reference bucket for this task (stored in data/letpub/references/<reference>.json)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Concurrent workers for online journal lookups (manual journal input mode)",
    )
    parser.add_argument("--no-crawl", action="store_true", help="Do not query LetPub online; use local letpub files only")
    parser.add_argument("--retries", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=25, help="Online query timeout (seconds)")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
