---
name: journal-impact-factor
description: Sync journal impact factors from LetPub for unresolved journals, update letpub supplement data, and backfill IF into daily data files.
keywords:
  - journal
  - impact factor
  - letpub
  - unresolved
  - if
  - reference
  - manual journal
license: MIT
---

# Journal Impact Factor Sync

Use this skill when the user asks things like:
- "抓取期刊影响因子"
- "补齐 unresolved 里的 IF"
- "根据 manual_full_name 去查 IF"
- "我给你几个期刊名字，去查 IF"
- "按某个任务 reference 单独抓一批期刊 IF"

## Goal

1. Read unresolved journals from `data/if_unresolved_journals.json`
2. AI manually reviews `data/if_unresolved_journals.json` and deletes obvious non-journal entries (e.g. `arXiv`, `arXiv preprint`, conferences, proceedings) before IF crawling.
3. Query LetPub once per journal（优先 ISSN，其次 manual full name，再次 journal abbreviation）
4. Write supplemental results into `data/letpub/letpub_manual_overrides.json`
5. Write task-scoped results into `data/letpub/references/<reference>.json`
6. Backfill IF into target `data/YYYY-MM-DD-*.json`
7. Keep unresolved list updated for journals still not found

## Reference Buckets

- Every run should use a `reference` so tasks are separated.
- Global supplement file:
  - `data/letpub/letpub_manual_overrides.json`
- Task-scoped file:
  - `data/letpub/references/<reference>.json`
- Suggested references:
  - `auto-unresolved`（每日抓取后的自动补抓）
  - `user-manual-YYYYMMDD`（用户手动输入期刊）
  - `backfill-<domain>`（某领域回填）

## Commands

Process specific data files:

```bash
python3 scripts/sync_impact_factors.py --reference backfill-brainmri data/2026-02-28-brainmri.json
```

Process unresolved `last_file` set automatically:

```bash
python3 scripts/sync_impact_factors.py --reference auto-unresolved
```

No online crawling (local letpub files only):

```bash
python3 scripts/sync_impact_factors.py --reference local-only --no-crawl
```

Manual journal names (single):

```bash
python3 scripts/sync_impact_factors.py \
  --reference user-manual-20260228 \
  --journal "Interdiscip Sci|1867-1462|Interdisciplinary Sciences: Computational Life Sciences" \
  --journal "Clin Neuroradiol|1869-1439|Clinical Neuroradiology"
```

Manual journal names (file):

```bash
python3 scripts/sync_impact_factors.py \
  --reference user-batch-20260228 \
  --journals-file data/manual_journals.txt \
  --workers 8
```

注意：
- `--journals-file` 必须是具体文件路径，不能传目录（例如不能传 `data/`）。
- 在线查询为“单次请求模式”：每个期刊只查一次，不做重试。
- 非期刊条目清理属于 AI 的手工步骤，不通过脚本规则自动剔除。

## Integration

- `./scripts/fetch.sh <academic-domain>` automatically triggers this after data validation.
- `./scripts/fetch.sh if` runs IF sync directly without paper/news fetching.
- `./scripts/fetch.sh if --reference user-manual-20260228 --journal "J Alzheimers Dis"` supports ad-hoc journal inputs.

## Reference Docs

- `references/unresolved-auto.md`
- `references/manual-journal-input.md`
- `references/reference-naming.md`
- `references/unresolved-manual-cleanup.md`
