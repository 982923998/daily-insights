# Unresolved Manual Cleanup

Use after `data/if_unresolved_journals.json` is generated and before IF crawling.

## Rule

- AI must manually review unresolved entries and remove obvious non-journal sources.
- Do not rely on script rules/regex to auto-filter these entries.

## Remove Examples

- `arXiv`
- `arXiv preprint`
- Conference names
- Proceedings / Workshop / Symposium titles
- Paper-collection or event-only sources that are not journals

## Keep Examples

- Real journals with unclear abbreviation
- Journals missing ISSN
- Journals needing `manual_full_name`补充

## Minimal Workflow

1. Open `data/if_unresolved_journals.json`.
2. Delete obvious non-journal entries manually.
3. Save file and continue IF crawling for remaining journals only.
