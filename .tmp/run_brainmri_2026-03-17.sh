#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/chenmayao/Projects/daily-insights"
TMP="$ROOT/.tmp"
OUT="$ROOT/data/2026-03-17-brainmri.json"
ESUM="$TMP/brainmri_esummary_2026-03-17.json"
EFETCH="$TMP/brainmri_efetch_2026-03-17.xml"
PMIDS="$TMP/brainmri_pmids_2026-03-17.txt"
BASE="$TMP/brainmri_articles_base_2026-03-17.tsv"
FINAL_NEW="$TMP/brainmri_articles_new_2026-03-17.json"

: > "$BASE"
if [ -s "$PMIDS" ]; then
  tr ',' '\n' < "$PMIDS" | sed '/^$/d' | while IFS= read -r pmid; do
    meta=$(jq -r --arg id "$pmid" '.result[$id] | [(.title // ""), (.source // ""), (.pubdate // "")] | @tsv' "$ESUM")
    title=$(printf "%s" "$meta" | awk -F "\t" '{print $1}')
    journal=$(printf "%s" "$meta" | awk -F "\t" '{print $2}')
    pubdate=$(printf "%s" "$meta" | awk -F "\t" '{print $3}')
    abstract=$(xmllint --xpath "string(//PubmedArticle[MedlineCitation/PMID=\"$pmid\"]/MedlineCitation/Article/Abstract)" "$EFETCH" 2>/dev/null || true)
    title=$(printf "%s" "$title" | tr "\n" " " | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//')
    journal=$(printf "%s" "$journal" | tr "\n" " " | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//')
    pubdate=$(printf "%s" "$pubdate" | tr "\n" " " | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//')
    abstract=$(printf "%s" "$abstract" | tr "\n" " " | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//')
    printf "%s\t%s\t%s\t%s\t%s\n" "$pmid" "$title" "$journal" "$pubdate" "$abstract" >> "$BASE"
  done
fi

jq -Rn '
  def m2n: {Jan:"01",Feb:"02",Mar:"03",Apr:"04",May:"05",Jun:"06",Jul:"07",Aug:"08",Sep:"09",Oct:"10",Nov:"11",Dec:"12"};
  def norm_date($s):
    ($s|gsub(" +";" ")|gsub(",";"")|sub("^ ";"")|sub(" $";"")) as $d |
    if ($d|test("^[0-9]{4}$")) then "\($d)-01-01"
    elif ($d|test("^[0-9]{4} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$")) then
      ($d|capture("^(?<y>[0-9]{4}) (?<m>[A-Za-z]{3})$")) as $c | "\($c.y)-\(m2n[$c.m])-01"
    elif ($d|test("^[0-9]{4} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [0-9]{1,2}$")) then
      ($d|capture("^(?<y>[0-9]{4}) (?<m>[A-Za-z]{3}) (?<day>[0-9]{1,2})$")) as $c |
      "\($c.y)-\(m2n[$c.m])-\(($c.day|tonumber|tostring|if length==1 then "0"+ . else . end))"
    elif ($d|test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$")) then $d
    else null end;
  [inputs | select(length>0) | split("\t") | {
      title: (.[1] // ""),
      summary: (if ((.[4] // "")|length)>0 then .[4] else "No abstract available in source." end),
      url: "https://pubmed.ncbi.nlm.nih.gov/\(.[0])/",
      category: "Brain MRI",
      source: "pubmed",
      journal: (.[2] // ""),
      published_date: norm_date(.[3] // ""),
      date: "2026-03-17"
  }]
  | map(select(.published_date == "2026-03-17" or .published_date == "2026-03-16"))
  | unique_by(.url)
' < "$BASE" > "$FINAL_NEW"

if [ -f "$OUT" ]; then
  jq -s '
    {
      date: "2026-03-17",
      articles: ((.[0].articles // []) + (.[1] // [])
        | map(select(.url != null and .url != ""))
        | unique_by(.url))
    }
  ' "$OUT" "$FINAL_NEW" > "$TMP/brainmri_merged_2026-03-17.json"
else
  jq '{date:"2026-03-17",articles:.}' "$FINAL_NEW" > "$TMP/brainmri_merged_2026-03-17.json"
fi

mv "$TMP/brainmri_merged_2026-03-17.json" "$OUT"
jq '.date, (.articles|length)' "$OUT"
