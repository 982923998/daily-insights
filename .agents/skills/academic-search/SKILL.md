---
name: academic-search
description: Search academic papers on PubMed using domain-specific configurations. Each research domain is defined in sources/{id}.md with search queries and filtering rules.
keywords:
  - academic
  - research
  - pubmed
  - papers
  - literature
license: MIT
---

# Academic Search

Searches PubMed for papers in configured research domains.
Domain configurations live in `sources/{id}.md` — each file defines what to search and filter rules.

## Requirements

1. Bash + curl (uses PubMed E-utilities directly, no external API key needed)

## Workflow

1. Read domain config from `sources/{domain_id}.md` to get queries and filter rules
2. Execute PubMed E-utilities searches (esearch → esummary → efetch)
3. Apply date filtering per domain rules
4. Output in standard JSON format

## Domain Configuration (sources/{id}.md)

Each domain file has:

- **Frontmatter** (YAML between `---`): UI metadata + search settings
  - `id`: unique identifier, used for data filename `{date}-{id}.json`
  - `label`: display name in the UI
  - `category`: value written to each article's `category` field
  - `color`: hex color for UI rendering
  - `icon`: Lucide icon name
  - `skill`: which skill handles fetching (`daily-ai-news` or `academic-search`)
  - `platforms`: `pubmed` (only PubMed is supported)
  - `date_filter_days`: how many days back to keep (default: 3)
  - `order`: display order in the UI tab bar

- **Body**: search queries and domain-specific filtering rules (in natural language)

## Output Format per Article

```json
{
  "title": "Paper Title",
  "summary": "Abstract or summary (100-200 words)",
  "url": "https://pubmed.ncbi.nlm.nih.gov/...",
  "category": "Autism",
  "source": "pubmed",
  "published_date": "2026-02-23",
  "date": "2026-02-23"
}
```

## Top-Level File Structure

```json
{
  "date": "2026-02-23",
  "articles": [ ... ]
}
```
