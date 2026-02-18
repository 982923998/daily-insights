#!/usr/bin/env node

/**
 * PubMed Date Filter
 * Reads search results from stdin and filters by publication date.
 *
 * Usage:
 *   scripts/search "autism" 20 | scripts/filter-by-date
 *   scripts/search "autism" 20 | scripts/filter-by-date 7
 *
 * Arguments:
 *   [days]  Keep articles published within the last N days. Default: 3.
 *           Pass 0 to skip filtering.
 */

const PUBMED_ESUMMARY = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi';

function extractPMID(url) {
  const match = url?.match(/pubmed\.ncbi\.nlm\.nih\.gov\/(\d+)/);
  return match ? match[1] : null;
}

async function fetchPubDates(pmids) {
  if (!pmids.length) return new Map();

  const url = `${PUBMED_ESUMMARY}?db=pubmed&id=${pmids.join(',')}&retmode=json`;

  try {
    const response = await fetch(url);
    if (!response.ok) return new Map();

    const data = await response.json();
    const dateMap = new Map();

    for (const pmid of pmids) {
      const record = data.result?.[pmid];
      if (!record) continue;

      // epubdate = electronic publish date (earlier), fallback to pubdate
      const dateStr = record.epubdate || record.pubdate;
      if (!dateStr) continue;

      // PubMed date formats: "2026 Feb 15", "2026 Feb", "2026"
      const parsed = new Date(dateStr);
      if (!isNaN(parsed.getTime())) {
        dateMap.set(pmid, parsed);
      }
    }

    return dateMap;
  } catch (e) {
    return new Map();
  }
}

async function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', chunk => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

(async () => {
  const days = process.argv[2] !== undefined ? parseInt(process.argv[2], 10) : 3;

  // Read search results from stdin
  let input;
  try {
    const raw = await readStdin();
    input = JSON.parse(raw);
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: 'Invalid JSON from stdin' }));
    process.exit(1);
  }

  // Pass through errors or non-search results unchanged
  if (!input.success || !Array.isArray(input.results)) {
    console.log(JSON.stringify(input, null, 2));
    process.exit(input.success ? 0 : 1);
  }

  // Skip filtering when days = 0
  if (days === 0) {
    console.log(JSON.stringify({ ...input, filter_days: 0 }, null, 2));
    process.exit(0);
  }

  // Compute cutoff: start of day, N days ago
  const today = new Date();
  const cutoff = new Date(today.getFullYear(), today.getMonth(), today.getDate() - days);

  const pmids = input.results.map(r => extractPMID(r.url)).filter(Boolean);
  const dateMap = await fetchPubDates(pmids);

  const kept = [];
  const removed = [];

  for (const result of input.results) {
    const pmid = extractPMID(result.url);
    const pubDate = pmid ? dateMap.get(pmid) : null;

    if (!pubDate) {
      removed.push({ title: result.title, url: result.url, reason: 'date_unknown' });
      continue;
    }

    const dateStr = pubDate.toISOString().split('T')[0];
    if (pubDate >= cutoff) {
      kept.push({ ...result, pub_date: dateStr });
    } else {
      removed.push({ title: result.title, url: result.url, pub_date: dateStr, reason: 'too_old' });
    }
  }

  const cutoffStr = cutoff.toISOString().split('T')[0];
  const todayStr = today.toISOString().split('T')[0];

  console.log(JSON.stringify({
    ...input,
    filter_days: days,
    date_range: `${cutoffStr} ~ ${todayStr}`,
    total_fetched: input.results.length,
    result_count: kept.length,
    results: kept,
    filtered_out: removed
  }, null, 2));

  process.exit(0);
})();
