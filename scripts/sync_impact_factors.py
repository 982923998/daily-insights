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
import re
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
IF_STATUS_NOT_FOUND = "not_found"


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
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict):
        journals = payload.get("journals", [])
        if isinstance(journals, list):
            return journals
        rows = payload.get("rows", [])
        return rows if isinstance(rows, list) else []
    if isinstance(payload, list):
        return payload
    return []


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
        return default_raw_letpub_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_raw_letpub_payload()
    if isinstance(payload, list):
        out = default_raw_letpub_payload()
        out["rows"] = payload
        out["raw_total"] = len(payload)
        return out
    if not isinstance(payload, dict):
        return default_raw_letpub_payload()
    out = dict(payload)
    rows = out.get("rows")
    if not isinstance(rows, list):
        journals = out.get("journals")
        if isinstance(journals, list):
            rows = journals
        else:
            rows = []
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
        "source": "letpub_unresolved_crawler",
        "updated_at": now_iso_utc(),
        "journals": [],
    }


def load_supplement_payload(path: Path) -> dict:
    if not path.exists():
        return default_supplement_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_supplement_payload()
    if not isinstance(payload, dict):
        return default_supplement_payload()
    journals = payload.get("journals", [])
    if not isinstance(journals, list):
        journals = []
    return {
        "schema_version": int(payload.get("schema_version", 1)),
        "source": str(payload.get("source", "letpub_unresolved_crawler")),
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


def load_all_reference_entries(reference_dir: Path) -> list[dict]:
    if not reference_dir.exists():
        return []
    entries: list[dict] = []
    for p in sorted(reference_dir.glob("*.json")):
        payload = load_reference_payload(p, p.stem)
        journals = payload.get("journals", [])
        if isinstance(journals, list):
            entries.extend(journals)
    return entries


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


def build_letpub_if_index(journals: list[dict]) -> dict[str, dict]:
    by_name: dict[str, dict] = {}
    by_issn: dict[str, dict] = {}
    for item in journals:
        if not isinstance(item, dict):
            continue
        impact_factor_raw = normalize_if_value_allow_zero(item.get("impact_factor"))
        if impact_factor_raw is None:
            continue
        impact_factor = impact_factor_raw if impact_factor_raw > 0 else None
        if_status = IF_STATUS_AVAILABLE if impact_factor_raw > 0 else IF_STATUS_NOT_AVAILABLE_YET
        if_year = normalize_if_year(item.get("impact_factor_year"))
        if if_year is None:
            if_year = normalize_if_year(item.get("if_year"))
        source = str(item.get("source", "letpub")).strip() or "letpub"
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
                by_name[key] = {
                    "impact_factor": impact_factor,
                    "impact_factor_year": if_year,
                    "if_status": if_status,
                    "source": source,
                }
        issn_key = normalize_issn(str(item.get("issn", "")).strip())
        if issn_key:
            current_issn = by_issn.get(issn_key)
            current_if = normalize_if_value_allow_zero(current_issn.get("impact_factor")) if current_issn else None
            if current_if is None:
                current_if = -1
            if impact_factor_raw > current_if:
                by_issn[issn_key] = {
                    "impact_factor": impact_factor,
                    "impact_factor_year": if_year,
                    "if_status": if_status,
                    "source": source,
                }
    return {"by_name": by_name, "by_issn": by_issn}


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
        try:
            if qtype == "issn":
                html = fetch_letpub_html(searchissn=qvalue, timeout=timeout)
            else:
                html = fetch_letpub_html(searchname=qvalue, timeout=timeout)
            rows = parse_letpub_rows(html)
        except Exception:
            rows = []
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
        "impact_factor_year": None,
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
        "source": "letpub_unresolved_crawler",
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
    unresolved_journals = unresolved.get("journals", {})
    if not isinstance(unresolved_journals, dict):
        unresolved_journals = {}
    for key in resolved_keys:
        unresolved_journals.pop(key, None)
    for key, meta in unresolved_observed.items():
        existing = unresolved_journals.get(key, {})
        if not isinstance(existing, dict):
            existing = {}
        seen_count_prev = int(existing.get("seen_count", 0) or 0)
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
            "last_seen": capture_date,
            "seen_count": seen_count_prev + int(meta.get("hit_count", 1) or 1),
            "last_file": last_file,
            "manual_full_name": manual_full_name,
            "notes": notes,
        }
    unresolved["journals"] = {
        k: unresolved_journals[k] for k in sorted(unresolved_journals.keys(), key=lambda s: s.lower())
    }
    unresolved["updated_at"] = now_iso_utc()


def infer_capture_date(path: Path) -> str:
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-", path.name)
    if m:
        return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")


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
    unresolved_key_index = {
        str(k).strip().lower(): str(k).strip()
        for k in unresolved_journals.keys()
        if isinstance(k, str) and str(k).strip()
    }
    unresolved_observed: dict[str, dict[str, object]] = {}
    resolved_keys: set[str] = set()
    supplement_changed = 0
    applied_count = 0
    capture_date = infer_capture_date(path)

    by_name = letpub_index["by_name"]
    by_issn = letpub_index["by_issn"]

    def resolve_key(journal_name: str) -> str:
        existing = unresolved_key_index.get(journal_name.strip().lower())
        if existing:
            return existing
        unresolved_key_index[journal_name.strip().lower()] = journal_name.strip()
        return journal_name.strip()

    for article in articles:
        if not isinstance(article, dict):
            continue
        journal_name = str(article.get("journal", "")).strip()
        if not journal_name:
            continue
        key = resolve_key(journal_name)
        article_issn = normalize_issn(str(article.get("journal_issn", "")).strip())
        unresolved_entry = unresolved_journals.get(key, {})
        manual_full_name = ""
        if isinstance(unresolved_entry, dict):
            manual_full_name = str(unresolved_entry.get("manual_full_name", "")).strip()
        match = None
        if article_issn:
            match = by_issn.get(article_issn)
        if not match and manual_full_name:
            match = by_name.get(normalize_journal_key(manual_full_name))
        if not match:
            match = by_name.get(normalize_journal_key(journal_name))

        if not match and crawl_online:
            row, trace = lookup_letpub_for_journal(
                journal_name=journal_name,
                journal_issn=article_issn,
                manual_full_name=manual_full_name,
                cache=query_cache,
                timeout=timeout,
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
                if upsert_supplement_entry(reference_payload, new_entry):
                    supplement_changed += 1
                letpub_index = build_letpub_if_index(
                    base_entries
                    + payload_journal_entries(supplement_payload)
                    + reference_payload.get("journals", [])
                )
                by_name = letpub_index["by_name"]
                by_issn = letpub_index["by_issn"]
                if article_issn:
                    match = by_issn.get(article_issn)
                if not match and manual_full_name:
                    match = by_name.get(normalize_journal_key(manual_full_name))
                if not match:
                    match = by_name.get(normalize_journal_key(journal_name))

        if match:
            applied_count += 1
            if match.get("if_status") != IF_STATUS_NOT_FOUND:
                resolved_keys.add(key)
            else:
                unresolved_observed[key] = {
                    "journal_issn": format_issn(article_issn),
                    "hit_count": 1,
                    "manual_full_name": manual_full_name,
                }
        else:
            unresolved_observed[key] = {
                "journal_issn": format_issn(article_issn),
                "hit_count": 1,
                "manual_full_name": manual_full_name,
            }

    update_unresolved_registry(
        unresolved=unresolved,
        unresolved_observed=unresolved_observed,
        resolved_keys=resolved_keys,
        capture_date=capture_date,
        last_file=path.name,
    )
    return (applied_count, supplement_changed)


def collect_default_files(data_dir: Path, unresolved: dict) -> list[Path]:
    journals = unresolved.get("journals", {})
    if not isinstance(journals, dict):
        return []
    files = []
    for entry in journals.values():
        if not isinstance(entry, dict):
            continue
        last_file = str(entry.get("last_file", "")).strip()
        if not last_file:
            continue
        if not last_file.lower().endswith(".json"):
            continue
        p = data_dir / last_file
        if p.exists():
            files.append(p)
    dedup = sorted({str(p): p for p in files}.values(), key=lambda p: p.name)
    return dedup


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

        if local_match:
            row = {
                "issn": format_issn(journal_issn),
                "journal_name": manual_full_name or journal_name,
                "journal_name_short": journal_name,
                "impact_factor": local_match.get("impact_factor"),
                "source": local_match.get("source", "letpub_local_index"),
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
            if upsert_supplement_entry(supplement_payload, new_entry):
                updated += 1
            if upsert_supplement_entry(reference_payload, new_entry):
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
                try:
                    _, row, trace = future.result()
                except Exception as exc:
                    row = None
                    trace = f"error:{exc}"

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
                    if upsert_supplement_entry(reference_payload, new_entry):
                        updated += 1
                    unresolved_journals.pop(journal_name, None)
                    print(f"[PROGRESS] {done}/{total} found: {journal_name}", flush=True)
                    continue

                key = journal_name
                existing = unresolved_journals.get(key, {})
                if not isinstance(existing, dict):
                    existing = {}
                unresolved_journals[key] = {
                    "journal_name": key,
                    "journal_issn": format_issn(journal_issn),
                    "first_seen": str(existing.get("first_seen", today)),
                    "last_seen": today,
                    "seen_count": int(existing.get("seen_count", 0) or 0) + 1,
                    "last_file": str(existing.get("last_file", "")),
                    "manual_full_name": manual_full_name,
                    "notes": str(
                        existing.get(
                            "notes",
                            f"手动输入期刊（reference={sanitize_reference(reference)}）未在 LetPub 命中",
                        )
                    ),
                }
                unresolved_added += 1
                print(f"[PROGRESS] {done}/{total} not_found: {journal_name}", flush=True)
    elif online_specs:
        for spec in online_specs:
            journal_name = spec["journal_name"]
            manual_full_name = spec["manual_full_name"]
            journal_issn = spec["journal_issn"]
            key = journal_name
            existing = unresolved_journals.get(key, {})
            if not isinstance(existing, dict):
                existing = {}
            unresolved_journals[key] = {
                "journal_name": key,
                "journal_issn": format_issn(journal_issn),
                "first_seen": str(existing.get("first_seen", today)),
                "last_seen": today,
                "seen_count": int(existing.get("seen_count", 0) or 0) + 1,
                "last_file": str(existing.get("last_file", "")),
                "manual_full_name": manual_full_name,
                "notes": str(
                    existing.get(
                        "notes",
                        f"手动输入期刊（reference={sanitize_reference(reference)}）未在 LetPub 命中",
                    )
                ),
            }
            unresolved_added += 1

    unresolved["journals"] = {
        k: unresolved_journals[k] for k in sorted(unresolved_journals.keys(), key=lambda s: s.lower())
    }
    unresolved["updated_at"] = now_iso_utc()
    elapsed = time.time() - start_ts
    print(f"[INFO] manual lookup elapsed={elapsed:.1f}s", flush=True)
    return (found, updated, unresolved_added)


def run(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    data_dir = (project_dir / "data").resolve()
    unresolved_path = data_dir / "if_unresolved_journals.json"
    letpub_dir = data_dir / "letpub"
    reference_dir = letpub_dir / LETPUB_REFERENCE_DIRNAME
    base_letpub_path = letpub_dir / "letpub_life_med_unique.json"
    raw_letpub_path = letpub_dir / "letpub_life_med_raw.json"
    legacy_supplement_path = letpub_dir / "letpub_manual_overrides.json"
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
    supplement_payload = load_raw_letpub_payload(raw_letpub_path)
    legacy_supplement_payload = load_supplement_payload(legacy_supplement_path)
    legacy_migrated = 0
    for legacy_entry in payload_journal_entries(legacy_supplement_payload):
        if not isinstance(legacy_entry, dict):
            continue
        if upsert_supplement_entry(supplement_payload, legacy_entry):
            legacy_migrated += 1
    if legacy_migrated:
        print(
            f"[INFO] migrated legacy overrides into letpub_life_med_raw.json: count={legacy_migrated}",
            flush=True,
        )
    reference_payload = load_reference_payload(reference_path, reference)
    base_entries = load_letpub_journal_list(base_letpub_path)
    all_reference_entries = load_all_reference_entries(reference_dir)

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
            base_entries
            + payload_journal_entries(supplement_payload)
            + all_reference_entries
            + reference_payload.get("journals", [])
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
            base_entries
            + payload_journal_entries(supplement_payload)
            + all_reference_entries
            + reference_payload.get("journals", [])
        )
        applied, changed = process_data_file(
            path=file_path,
            base_entries=base_entries,
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

    supplement_payload["updated_at"] = now_iso_utc()
    raw_entries = payload_journal_entries(supplement_payload)
    if isinstance(raw_entries, list):
        supplement_payload["raw_total"] = len(raw_entries)
    ref_journals = reference_payload.get("journals", [])
    if isinstance(ref_journals, list):
        ref_journals.sort(key=lambda x: normalize_journal_key(str((x or {}).get("journal_name", ""))))
    reference_payload["updated_at"] = now_iso_utc()
    letpub_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)
    raw_letpub_path.write_text(json.dumps(supplement_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reference_path.write_text(json.dumps(reference_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    unresolved_path.write_text(json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if legacy_supplement_path.exists():
        legacy_supplement_path.unlink()
        print(f"[INFO] removed legacy file: {legacy_supplement_path}")

    unresolved_count = len((unresolved.get("journals") or {}))
    supplement_count = len(payload_journal_entries(supplement_payload))
    reference_count = len((reference_payload.get("journals") or []))
    print(
        f"[DONE] reference={reference}, unresolved={unresolved_count}, "
        f"letpub_raw={supplement_count}, letpub_reference={reference_count}, "
        f"total_applied={total_applied}, total_letpub_updates={total_supplement}, "
        f"manual_found={manual_found}, manual_unresolved_added={manual_unresolved}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync impact factors from LetPub folder + unresolved crawl")
    parser.add_argument(
        "files",
        nargs="*",
        help="Target data JSON files. If omitted, uses last_file entries from if_unresolved_journals.json.",
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
