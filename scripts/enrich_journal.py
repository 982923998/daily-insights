#!/usr/bin/env python3
"""Enrich academic articles with journal names and maintain IF registry JSON."""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.parse
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from bs4 import BeautifulSoup


PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
IF_REGISTRY_FILENAME = "journal_impact_factors.json"
UNRESOLVED_IF_FILENAME = "if_unresolved_journals.json"
LETPUB_DB_PATH = Path("letpub") / "letpub_life_med_unique.json"
IF_STATUS_AVAILABLE = "available"
IF_STATUS_NOT_AVAILABLE_YET = "not_available_yet"
IF_STATUS_NOT_FOUND = "not_found"


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def extract_pmid(url: str) -> str:
    if not url:
        return ""
    match = PMID_RE.search(url)
    return match.group(1) if match else ""


def normalize_journal_key(name: str) -> str:
    """Normalize journal names for robust matching across abbreviations/cases/punctuation."""
    cleaned = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    return cleaned


def normalize_issn(value: str) -> str:
    """Normalize ISSN strings to 8-char uppercase token without hyphen."""
    token = re.sub(r"[^0-9xX]", "", (value or ""))
    return token.upper()


def format_issn(value: str) -> str:
    """Format normalized ISSN token as ####-#### for readability."""
    token = normalize_issn(value)
    if len(token) == 8:
        return f"{token[:4]}-{token[4:]}"
    return token


def normalize_if_value(value):
    if value in (None, ""):
        return None
    try:
        num = float(value)
        if not math.isfinite(num):
            return None
        if num <= 0:
            return None
        return num
    except (TypeError, ValueError):
        return None


def normalize_if_value_allow_zero(value):
    if value in (None, ""):
        return None
    try:
        num = float(value)
        if not math.isfinite(num):
            return None
        if num < 0:
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


def infer_capture_date(path: Path) -> str:
    match = DATE_PREFIX_RE.match(path.stem)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def fetch_pubmed_summaries(pmids: list[str]) -> dict[str, dict]:
    if not pmids:
        return {}
    unique = list(dict.fromkeys(pmids))
    out: dict[str, dict] = {}
    chunk_size = 100
    for i in range(0, len(unique), chunk_size):
        chunk = unique[i : i + chunk_size]
        query = urllib.parse.urlencode(
            {"db": "pubmed", "id": ",".join(chunk), "retmode": "json"}
        )
        url = f"{ESUMMARY_URL}?{query}"
        payload = None
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(url, timeout=20) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError):
                if attempt < 3:
                    time.sleep(0.8 * attempt)
                else:
                    payload = {"result": {}}
        result = payload.get("result", {})
        for pmid in chunk:
            info = result.get(pmid) or result.get(str(int(pmid))) or {}
            journal = str(info.get("source", "")).strip()
            # PubMed esummary often leaves "issn" empty for online-only journals.
            # Fallback to "essn" to improve ISSN coverage.
            issn = normalize_issn(str(info.get("issn", "")).strip())
            if not issn:
                issn = normalize_issn(str(info.get("essn", "")).strip())
            out[pmid] = {"journal": journal, "issn": issn}
    return out


def default_registry() -> dict:
    return {
        "schema_version": 1,
        "updated_at": now_iso_utc(),
        "journals": {},
    }


def load_registry(path: Path) -> dict:
    if not path.exists():
        return default_registry()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return default_registry()

    journals = raw.get("journals", {})
    if not isinstance(journals, dict):
        journals = {}

    return {
        "schema_version": int(raw.get("schema_version", 1)),
        "updated_at": str(raw.get("updated_at", now_iso_utc())),
        "journals": journals,
    }


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


def load_letpub_if_index(data_dir: Path) -> dict[str, dict]:
    """
    Load LetPub journal IF database and build a normalized lookup index.
    Keys include both full and short journal names.
    """
    path = data_dir / LETPUB_DB_PATH
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    journals = payload.get("journals", [])
    if not isinstance(journals, list):
        return {}

    by_name: dict[str, dict] = {}
    by_issn: dict[str, dict] = {}
    for item in journals:
        if not isinstance(item, dict):
            continue
        impact_factor_raw = normalize_if_value_allow_zero(item.get("impact_factor"))
        if impact_factor_raw is None:
            continue
        impact_factor = (
            impact_factor_raw if impact_factor_raw > 0 else None
        )
        if_status = (
            IF_STATUS_AVAILABLE
            if impact_factor_raw > 0
            else IF_STATUS_NOT_AVAILABLE_YET
        )

        if_year = normalize_if_year(item.get("impact_factor_year"))
        candidates = [
            str(item.get("journal_name", "")).strip(),
            str(item.get("journal_name_short", "")).strip(),
        ]
        for candidate in candidates:
            key = normalize_journal_key(candidate)
            if not key:
                continue
            current = by_name.get(key)
            current_if = normalize_if_value_allow_zero(current.get("impact_factor")) if current else None
            if current_if is None:
                current_if = -1
            # If duplicate keys exist, prefer available IF over zero, then higher IF.
            if impact_factor_raw > current_if:
                by_name[key] = {
                    "impact_factor": impact_factor,
                    "impact_factor_year": if_year,
                    "if_status": if_status,
                    "source": "letpub",
                }
        issn_key = normalize_issn(str(item.get("issn", "")).strip())
        if issn_key:
            current_issn = by_issn.get(issn_key)
            current_issn_if = normalize_if_value_allow_zero(current_issn.get("impact_factor")) if current_issn else None
            if current_issn_if is None:
                current_issn_if = -1
            if impact_factor_raw > current_issn_if:
                by_issn[issn_key] = {
                    "impact_factor": impact_factor,
                    "impact_factor_year": if_year,
                    "if_status": if_status,
                    "source": "letpub",
                }

    return {"by_name": by_name, "by_issn": by_issn}


def parse_letpub_search_html(html: str, target_issn: str) -> dict | None:
    """Parse LetPub search result table and return first matched row for ISSN."""
    issn_token = normalize_issn(target_issn)
    if not issn_token:
        return None
    soup = BeautifulSoup(html, "html.parser")
    issn_th = soup.find("th", string=lambda s: bool(s and "ISSN" in s))
    if not issn_th:
        return None
    table = issn_th.find_parent("table")
    if table is None:
        return None

    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != 12:
            continue
        row_issn_raw = str(tds[0].get_text(" ", strip=True))
        row_issn = normalize_issn(row_issn_raw)
        if row_issn and row_issn != issn_token:
            continue
        journal_link = tds[1].find("a")
        journal_name = str(journal_link.get_text(" ", strip=True)) if journal_link else ""
        journal_name_short_tag = tds[1].find("font")
        journal_name_short = (
            str(journal_name_short_tag.get_text(" ", strip=True))
            if journal_name_short_tag
            else ""
        )
        detail_href = str(journal_link.get("href", "")) if journal_link else ""
        jid_match = re.search(r"journalid=(\d+)", detail_href)
        journal_id = int(jid_match.group(1)) if jid_match else None
        metrics_text = str(tds[3].get_text(" ", strip=True))
        m_if = re.search(r"IF:\s*([0-9]+(?:\.[0-9]+)?)", metrics_text, re.I)
        if_raw = float(m_if.group(1)) if m_if else None
        if_status = (
            IF_STATUS_AVAILABLE
            if if_raw is not None and if_raw > 0
            else IF_STATUS_NOT_AVAILABLE_YET
            if if_raw == 0
            else IF_STATUS_NOT_FOUND
        )
        return {
            "journal_id": journal_id,
            "journal_name": journal_name,
            "journal_name_short": journal_name_short,
            "issn": row_issn,
            "impact_factor": if_raw if if_raw and if_raw > 0 else None,
            "if_status": if_status,
            "source": "letpub_issn_lookup",
        }
    return None


def lookup_letpub_by_issn_online(issn: str, retries: int = 3, timeout: int = 25) -> dict | None:
    """Query LetPub search endpoint by ISSN and parse first matched result."""
    issn_fmt = format_issn(issn)
    if not normalize_issn(issn_fmt):
        return None
    url = (
        "https://letpub.com.cn/index.php?page=journalapp&view=search"
        f"&searchname=&searchissn={quote_plus(issn_fmt)}"
        "&searchfield=&searchimpactlow=&searchimpacthigh="
        "&searchimpacttrend=&searchscitype=&searchcategory1=&searchcategory2="
        "&searchjcrkind=&searchopenaccess=&searchsort="
    )
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
    last_err: Exception | None = None
    for i in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            result = parse_letpub_search_html(html, issn_fmt)
            if result:
                return result
            return None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError) as exc:
            last_err = exc
            if i < retries:
                time.sleep(0.8 * i)
    if last_err:
        return None
    return None


def normalize_registry_entry(entry: dict, capture_date: str) -> dict:
    if not isinstance(entry, dict):
        entry = {}
    impact_factor = normalize_if_value(entry.get("impact_factor", None))
    if_status = str(entry.get("if_status", "")).strip()
    if impact_factor not in (None, ""):
        if_status = IF_STATUS_AVAILABLE
    elif if_status not in (
        IF_STATUS_AVAILABLE,
        IF_STATUS_NOT_AVAILABLE_YET,
        IF_STATUS_NOT_FOUND,
    ):
        if_status = IF_STATUS_NOT_FOUND
    return {
        "impact_factor": impact_factor,
        "if_year": normalize_if_year(entry.get("if_year", None)),
        "if_status": if_status,
        "notes": str(entry.get("notes", "")),
        "first_seen": str(entry.get("first_seen", capture_date)),
        "last_seen": str(entry.get("last_seen", capture_date)),
        "seen_count": int(entry.get("seen_count", 0) or 0),
    }


def resolve_journal_key(journals: dict, key_index: dict, journal_name: str) -> str:
    normalized = journal_name.strip()
    lowered = normalized.lower()
    existing = key_index.get(lowered)
    if existing:
        return existing
    journals[normalized] = journals.get(normalized, {})
    key_index[lowered] = normalized
    return normalized


def enrich_file(path: Path) -> tuple[int, int, int, Path]:
    data = json.loads(path.read_text(encoding="utf-8"))
    articles = data.get("articles", [])
    if not isinstance(articles, list):
        return (0, 0, 0, path.parent / IF_REGISTRY_FILENAME)

    pmids = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        if str(article.get("source", "")).lower() != "pubmed":
            continue
        pmid = extract_pmid(str(article.get("url", "")))
        if pmid:
            pmids.append(pmid)

    summary_by_pmid = fetch_pubmed_summaries(pmids)
    updated_journal_field = 0
    inspected = 0
    for article in articles:
        if not isinstance(article, dict):
            continue
        if str(article.get("source", "")).lower() != "pubmed":
            continue
        inspected += 1
        pmid = extract_pmid(str(article.get("url", "")))
        summary = summary_by_pmid.get(pmid, {})
        journal = str(summary.get("journal", "")).strip()
        article_issn = normalize_issn(str(summary.get("issn", "")).strip())
        if article_issn:
            article["journal_issn"] = format_issn(article_issn)
        else:
            article.pop("journal_issn", None)
        if article.get("journal"):
            continue
        if journal:
            article["journal"] = journal
            updated_journal_field += 1

    capture_date = infer_capture_date(path)
    registry_path = path.parent / IF_REGISTRY_FILENAME
    registry = load_registry(registry_path)
    letpub_if_index = load_letpub_if_index(path.parent)
    journals = registry.get("journals", {})
    key_index = {k.strip().lower(): k for k in journals if isinstance(k, str) and k.strip()}
    journal_hits = Counter()
    registry_new_count = 0
    letpub_by_name = letpub_if_index.get("by_name", {})
    letpub_by_issn = letpub_if_index.get("by_issn", {})
    issn_lookup_cache: dict[str, dict | None] = {}
    unresolved_observed: dict[str, dict[str, str]] = {}
    resolved_keys: set[str] = set()

    for article in articles:
        if not isinstance(article, dict):
            continue
        journal_name = str(article.get("journal", "")).strip()
        if not journal_name:
            # Keep stale IF fields out of records with no journal.
            article.pop("impact_factor", None)
            article.pop("impact_factor_year", None)
            article.pop("impact_factor_status", None)
            continue

        if journal_name.lower() not in key_index:
            registry_new_count += 1
        key = resolve_journal_key(journals, key_index, journal_name)
        entry = normalize_registry_entry(journals.get(key, {}), capture_date)

        # Fallback: auto-seed IF from LetPub DB when manual registry value is missing.
        if entry.get("impact_factor") in (None, "") and entry.get("if_status") != IF_STATUS_NOT_AVAILABLE_YET:
            pmid = extract_pmid(str(article.get("url", "")))
            summary = summary_by_pmid.get(pmid, {})
            article_issn = normalize_issn(
                str(article.get("journal_issn") or summary.get("issn", "")).strip()
            )

            match = None
            if article_issn:
                match = letpub_by_issn.get(article_issn)
            if not match:
                match = letpub_by_name.get(normalize_journal_key(journal_name))
            # Final fallback: online ISSN query against LetPub.
            if not match and article_issn:
                if article_issn not in issn_lookup_cache:
                    issn_lookup_cache[article_issn] = lookup_letpub_by_issn_online(article_issn)
                match = issn_lookup_cache.get(article_issn)
            if match:
                entry["impact_factor"] = match.get("impact_factor")
                entry["if_status"] = match.get("if_status", IF_STATUS_NOT_FOUND)
                if match.get("impact_factor_year") not in (None, ""):
                    entry["if_year"] = match.get("impact_factor_year")
                if not entry.get("notes"):
                    if entry.get("if_status") == IF_STATUS_NOT_AVAILABLE_YET:
                        entry["notes"] = "尚无影响因子（来源：LetPub）"
                    else:
                        entry["notes"] = "Auto-filled from LetPub database"
            elif entry.get("if_status") not in (IF_STATUS_NOT_AVAILABLE_YET,):
                entry["if_status"] = IF_STATUS_NOT_FOUND

        journals[key] = entry

        journal_hits[key] += 1

        # Apply manual IF data (if provided in registry) into article for frontend display.
        impact_factor = entry.get("impact_factor", None)
        if_status = entry.get("if_status", IF_STATUS_NOT_FOUND)
        if_year = entry.get("if_year", None)
        if impact_factor in (None, ""):
            article.pop("impact_factor", None)
            article.pop("impact_factor_year", None)
            if if_status == IF_STATUS_NOT_AVAILABLE_YET:
                article["impact_factor_status"] = "尚无影响因子"
            else:
                article["impact_factor_status"] = "未查到影响因子"
        else:
            article["impact_factor"] = impact_factor
            if if_year not in (None, ""):
                article["impact_factor_year"] = if_year
            else:
                article.pop("impact_factor_year", None)
            article["impact_factor_status"] = "已收录影响因子"

        if if_status == IF_STATUS_NOT_FOUND:
            unresolved_observed[key] = {
                "journal_name": key,
                "journal_issn": str(article.get("journal_issn", "")).strip(),
            }
        else:
            resolved_keys.add(key)

    for key, hit_count in journal_hits.items():
        entry = normalize_registry_entry(journals.get(key, {}), capture_date)
        entry["last_seen"] = capture_date
        entry["seen_count"] = int(entry.get("seen_count", 0)) + hit_count
        journals[key] = entry

    # Keep registry deterministic and easy to edit manually.
    sorted_journals = {k: journals[k] for k in sorted(journals.keys(), key=lambda s: s.lower())}
    registry["journals"] = sorted_journals
    registry["updated_at"] = now_iso_utc()

    # Maintain unresolved IF list for manual intervention (e.g., user provides full journal name).
    unresolved_path = path.parent / UNRESOLVED_IF_FILENAME
    unresolved = load_unresolved_registry(unresolved_path)
    unresolved_journals = unresolved.get("journals", {})

    for key in resolved_keys:
        unresolved_journals.pop(key, None)

    for key, meta in unresolved_observed.items():
        entry = unresolved_journals.get(key, {})
        if not isinstance(entry, dict):
            entry = {}
        first_seen = str(entry.get("first_seen", capture_date))
        seen_count_prev = int(entry.get("seen_count", 0) or 0)
        hit_count = int(journal_hits.get(key, 1) or 1)
        journal_issn = str(meta.get("journal_issn", "")).strip() or str(entry.get("journal_issn", "")).strip()
        unresolved_journals[key] = {
            "journal_name": key,
            "journal_issn": journal_issn,
            "first_seen": first_seen,
            "last_seen": capture_date,
            "seen_count": seen_count_prev + hit_count,
            "last_file": path.name,
            "manual_full_name": str(entry.get("manual_full_name", "")),
            "notes": str(entry.get("notes", "未查到影响因子，待人工补充期刊全称或外部来源")),
        }

    unresolved["journals"] = {
        k: unresolved_journals[k] for k in sorted(unresolved_journals.keys(), key=lambda s: s.lower())
    }
    unresolved["updated_at"] = now_iso_utc()

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    unresolved_path.write_text(json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return (inspected, updated_journal_field, registry_new_count, registry_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich data file with journal names")
    parser.add_argument("file", help="Path to target JSON data file")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")

    inspected, updated, registry_new_count, registry_path = enrich_file(path)
    print(
        f"Journal enriched: {path} "
        f"(inspected={inspected}, updated={updated}, registry_new={registry_new_count}, "
        f"registry={registry_path})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
