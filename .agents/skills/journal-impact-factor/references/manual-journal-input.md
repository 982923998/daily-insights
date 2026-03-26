# Manual Journal Input Flow

Use when:
- User provides journal names directly.
- Need IF crawling without running paper/news fetch.

## Single/Multiple journals

```bash
python3 scripts/sync_impact_factors.py \
  --reference user-manual-20260228 \
  --journal "Psychiatry Clin Neurosci|1323-1316|Psychiatry and Clinical Neurosciences" \
  --journal "Interdiscip Sci|1867-1462|Interdisciplinary Sciences: Computational Life Sciences"
```

`--journal` format:
- `name`
- `name|issn`
- `name|issn|manual_full_name`

## Batch file

```bash
python3 scripts/sync_impact_factors.py \
  --reference user-batch-20260228 \
  --journals-file data/manual_journals.txt \
  --workers 8
```

`txt` format (one line each):

```text
Clin Neuroradiol|1869-1439|Clinical Neuroradiology
Interdiscip Sci|1867-1462|Interdisciplinary Sciences: Computational Life Sciences
```

注意：
- `--journals-file` 只能传文件，不能传目录（例如 `data/`）。
- 大批量任务建议设置 `--workers 8`（或按网络情况调小到 4）。
- 运行后先人工检查 `data/if_unresolved_journals.json`，删除明显非期刊条目（如 arXiv / 会议）。

Result files:
- `data/letpub/letpub_manual_overrides.json`
- `data/letpub/references/<reference>.json`
