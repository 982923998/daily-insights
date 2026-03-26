# Reference Naming

Reference separates different IF tasks into independent buckets.

## Rules

- Allowed chars: `a-z`, `0-9`, `_`, `-`
- Other chars are normalized to `-`
- Empty reference becomes `default`

## Suggested patterns

- `auto-unresolved`
- `user-manual-YYYYMMDD`
- `backfill-<domain>`
- `investigation-<topic>`

## Storage

- Global merged file:
  - `data/letpub/letpub_manual_overrides.json`
- Reference-specific file:
  - `data/letpub/references/<reference>.json`

Both are written in each run so:
- Global lookup remains fast
- Task history stays isolated by reference
