# Unresolved Auto Flow

Use when:
- Daily academic fetch has finished.
- Need to resolve IF for unresolved journals automatically.

Pre-step:
- AI manually checks `data/if_unresolved_journals.json` and removes obvious non-journal entries (e.g. arXiv / conference / proceedings) before running.

Command:

```bash
python3 scripts/sync_impact_factors.py --reference auto-unresolved
```

Behavior:
- Reads `data/if_unresolved_journals.json`
- Uses each entry `last_file` as target backfill file
- Queries LetPub if local letpub cache has no match
- Updates:
  - `data/letpub/letpub_manual_overrides.json`
  - `data/letpub/references/auto-unresolved.json`
  - `data/if_unresolved_journals.json`
  - target data files (`impact_factor` fields)
