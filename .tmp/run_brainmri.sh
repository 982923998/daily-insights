#!/usr/bin/env bash
set -euo pipefail
TODAY="2026-03-05"
YESTERDAY="2026-03-04"
TARGET="data/2026-03-05-brainmri.json"
mkdir -p data .tmp

jq -r '.result.uids[] as $id | [
  $id,
  (.result[$id].title // ""),
  (.result[$id].source // ""),
  (.result[$id].pubdate // "")
] | @tsv' .tmp/brainmri-esummary.json > .tmp/brainmri-meta.tsv

month_to_num() {
  local mon="${1:-}"
  local mon_lc
  mon_lc="$(printf '%s' "$mon" | tr '[:upper:]' '[:lower:]')"
  case "$mon_lc" in
    jan|january) echo 1 ;;
    feb|february) echo 2 ;;
    mar|march) echo 3 ;;
    apr|april) echo 4 ;;
    may) echo 5 ;;
    jun|june) echo 6 ;;
    jul|july) echo 7 ;;
    aug|august) echo 8 ;;
    sep|sept|september) echo 9 ;;
    oct|october) echo 10 ;;
    nov|november) echo 11 ;;
    dec|december) echo 12 ;;
    [0-9]|[0-9][0-9]) echo "$((10#${mon}))" ;;
    *) echo "" ;;
  esac
}

parse_pubdate() {
  local raw="$1"
  raw="$(echo "$raw" | tr -s " " | sed "s/^ *//;s/ *$//")"
  local year mon day month_num

  if [[ "$raw" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})$ ]]; then
    echo "${BASH_REMATCH[1]}-${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
    return
  elif [[ "$raw" =~ ^([0-9]{4})[[:space:]]+([A-Za-z]{3,9})[[:space:]]+([0-9]{1,2})$ ]]; then
    year="${BASH_REMATCH[1]}"; mon="${BASH_REMATCH[2]}"; day="${BASH_REMATCH[3]}"
  elif [[ "$raw" =~ ^([0-9]{4})[[:space:]]+([A-Za-z]{3,9})$ ]]; then
    year="${BASH_REMATCH[1]}"; mon="${BASH_REMATCH[2]}"; day="1"
  elif [[ "$raw" =~ ^([0-9]{4})[[:space:]]+([0-9]{1,2})[[:space:]]+([0-9]{1,2})$ ]]; then
    year="${BASH_REMATCH[1]}"; mon="${BASH_REMATCH[2]}"; day="${BASH_REMATCH[3]}"
  elif [[ "$raw" =~ ^([0-9]{4})[[:space:]]+([0-9]{1,2})$ ]]; then
    year="${BASH_REMATCH[1]}"; mon="${BASH_REMATCH[2]}"; day="1"
  elif [[ "$raw" =~ ^([0-9]{4})$ ]]; then
    year="${BASH_REMATCH[1]}"; mon="1"; day="1"
  else
    echo ""
    return
  fi

  month_num="$(month_to_num "$mon")"
  if [[ -z "$month_num" ]]; then
    echo ""
    return
  fi

  printf "%04d-%02d-%02d\n" "$year" "$month_num" "$day"
}

: > .tmp/brainmri-new.ndjson

while IFS=$'\t' read -r uid title journal pubdate; do
  iso_date="$(parse_pubdate "$pubdate")"
  if [[ "$iso_date" != "$TODAY" && "$iso_date" != "$YESTERDAY" ]]; then
    continue
  fi

  abstract="$(xmllint --xpath "normalize-space(string(//PubmedArticle[MedlineCitation/PMID='${uid}']/MedlineCitation/Article/Abstract))" .tmp/brainmri-efetch.xml 2>/dev/null || true)"
  if [[ -z "${abstract// /}" ]]; then
    abstract="No abstract available in source."
  fi

  jq -cn \
    --arg title "$title" \
    --arg summary "$abstract" \
    --arg url "https://pubmed.ncbi.nlm.nih.gov/${uid}/" \
    --arg category "Brain MRI" \
    --arg source "pubmed" \
    --arg journal "$journal" \
    --arg published_date "$iso_date" \
    --arg date "$TODAY" \
    '{title:$title,summary:$summary,url:$url,category:$category,source:$source,journal:$journal,published_date:$published_date,date:$date}' \
    >> .tmp/brainmri-new.ndjson

done < .tmp/brainmri-meta.tsv

if [[ -s .tmp/brainmri-new.ndjson ]]; then
  jq -s 'unique_by(.url)' .tmp/brainmri-new.ndjson > .tmp/brainmri-new.json
else
  echo '[]' > .tmp/brainmri-new.json
fi

if [[ -f "$TARGET" ]]; then
  jq -s --arg date "$TODAY" '{date:$date, articles: (((.[1] // []) + (.[0].articles // [])) | unique_by(.url))}' "$TARGET" .tmp/brainmri-new.json > "${TARGET}.tmp"
else
  jq -n --arg date "$TODAY" --slurpfile arr .tmp/brainmri-new.json '{date:$date, articles: ($arr[0] // [])}' > "${TARGET}.tmp"
fi

mv "${TARGET}.tmp" "$TARGET"

echo "Wrote: $TARGET"
echo -n "New filtered articles: "
jq 'length' .tmp/brainmri-new.json
