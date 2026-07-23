#!/usr/bin/env python3
"""Backfill missing daily Brain MRI files from PubMed for a date range."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path


SEARCH_TERM = (
    '("Brain"[Mesh] OR brain*[Title/Abstract] OR cerebr*[Title/Abstract] OR '
    'encephalon[Title/Abstract] OR intracranial[Title/Abstract]) AND '
    '("Magnetic Resonance Imaging"[Mesh] OR "MRI"[Title/Abstract] OR '
    '"magnetic resonance"[Title/Abstract] OR "fMRI"[Title/Abstract] OR '
    '"DTI"[Title/Abstract] OR "diffusion tensor"[Title/Abstract] OR '
    '"VBM"[Title/Abstract] OR "voxel-based morphometry"[Title/Abstract] OR '
    '"connectome"[Title/Abstract] OR "arterial spin labeling"[Title/Abstract] OR '
    '"magnetic resonance spectroscopy"[Title/Abstract])'
)

MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    )
    if name
}
MONTHS.update(
    {
        name.lower(): number
        for number, name in enumerate(
            (
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            )
        )
        if name
    }
)


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def _date_from_parts(year: str, month: str, day: str) -> date | None:
    try:
        month_number = int(month) if month.isdigit() else MONTHS[month.lower()]
        return date(int(year), month_number, int(day or "1"))
    except (KeyError, TypeError, ValueError):
        return None


def _date_from_node(node: ET.Element | None) -> date | None:
    if node is None:
        return None
    parsed = _date_from_parts(
        _text(node.find("Year")),
        _text(node.find("Month")),
        _text(node.find("Day")),
    )
    if parsed:
        return parsed
    medline_date = _text(node.find("MedlineDate"))
    match = re.search(r"(\d{4})(?:\s+([A-Za-z]+))?(?:\s+(\d{1,2}))?", medline_date)
    if not match:
        return None
    return _date_from_parts(match.group(1), match.group(2) or "1", match.group(3) or "1")


def _published_date(article: ET.Element) -> date | None:
    candidates = article.findall("./MedlineCitation/Article/ArticleDate")
    candidates += article.findall("./MedlineCitation/Article/Journal/JournalIssue/PubDate")
    for status in ("epublish", "ppublish", "pubmed"):
        candidates += article.findall(f"./PubmedData/History/PubMedPubDate[@PubStatus='{status}']")
    for node in candidates:
        parsed = _date_from_node(node)
        if parsed:
            return parsed
    return None


def parse_pubmed_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    records = []
    for article in root.findall("PubmedArticle"):
        pmid = _text(article.find("./MedlineCitation/PMID"))
        published = _published_date(article)
        created = _date_from_node(
            article.find("./PubmedData/History/PubMedPubDate[@PubStatus='entrez']")
        )
        if not pmid or not published or not created:
            continue

        abstract_parts = []
        for node in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
            value = _text(node)
            if not value:
                continue
            label = (node.get("Label") or "").strip()
            abstract_parts.append(f"{label}: {value}" if label else value)

        journal = _text(article.find("./MedlineCitation/Article/Journal/ISOAbbreviation"))
        if not journal:
            journal = _text(article.find("./MedlineCitation/Article/Journal/Title"))
        issn = _text(article.find("./MedlineCitation/Article/Journal/ISSN"))
        if not issn:
            issn = _text(article.find("./MedlineCitation/MedlineJournalInfo/ISSNLinking"))

        records.append(
            {
                "title": _text(article.find("./MedlineCitation/Article/ArticleTitle")),
                "summary": " ".join(abstract_parts) or "No abstract available in source.",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "category": "Brain MRI",
                "source": "pubmed",
                "journal": journal,
                "journal_issn": issn,
                "published_date": published.isoformat(),
                "_created_date": created.isoformat(),
            }
        )
    return records


def bucket_articles(records: list[dict], start: date, end: date) -> dict[str, list[dict]]:
    buckets = {}
    current = start
    while current <= end:
        items = []
        window_start = current - timedelta(days=2)
        for record in records:
            published = date.fromisoformat(record["published_date"])
            created = date.fromisoformat(record["_created_date"])
            if window_start <= published <= current and window_start <= created <= current:
                item = {key: value for key, value in record.items() if not key.startswith("_")}
                item["date"] = current.isoformat()
                items.append(item)
        buckets[current.isoformat()] = sorted(items, key=lambda item: item["url"])
        current += timedelta(days=1)
    return buckets


def _request_json(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "daily-insights/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _request_xml(url: str, params: dict) -> str:
    body = urllib.parse.urlencode(params).encode("ascii")
    request = urllib.request.Request(url, data=body, headers={"User-Agent": "daily-insights/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def fetch_records(start: date, end: date) -> list[dict]:
    search_start = start - timedelta(days=2)
    result = _request_json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {
            "db": "pubmed",
            "term": SEARCH_TERM,
            "mindate": search_start.strftime("%Y/%m/%d"),
            "maxdate": end.strftime("%Y/%m/%d"),
            "datetype": "crdt",
            "retmax": "10000",
            "retmode": "json",
            "tool": "daily_insights",
        },
    )["esearchresult"]
    ids = result.get("idlist", [])
    if int(result.get("count", 0)) > len(ids):
        raise RuntimeError("PubMed result exceeds retmax=10000; split the requested date range")

    records = []
    for offset in range(0, len(ids), 200):
        batch = ids[offset : offset + 200]
        xml_text = _request_xml(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "rettype": "abstract",
                "tool": "daily_insights",
            },
        )
        records.extend(parse_pubmed_xml(xml_text))
        print(f"Fetched PubMed records: {min(offset + len(batch), len(ids))}/{len(ids)}", flush=True)
        time.sleep(0.34)
    return records


def _write_json(path: Path, payload: dict) -> None:
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must not be after --end")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    missing_dates = []
    current = args.start
    while current <= args.end:
        path = args.output_dir / f"{current.isoformat()}-brainmri.json"
        if not path.exists():
            missing_dates.append(current.isoformat())
        current += timedelta(days=1)
    if not missing_dates:
        print("No missing Brain MRI dates in requested range.")
        return 0

    records = fetch_records(args.start, args.end)
    buckets = bucket_articles(records, args.start, args.end)
    for day in missing_dates:
        path = args.output_dir / f"{day}-brainmri.json"
        _write_json(path, {"date": day, "articles": buckets[day]})
        print(f"Wrote {path} ({len(buckets[day])} articles)")
    print(f"Backfilled {len(missing_dates)} missing dates from {len(records)} parsed PubMed records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
