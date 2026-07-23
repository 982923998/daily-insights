---
id: tms
label: TMS
category: TMS
color: "#8b5cf6"
icon: zap
skill: academic-search
platforms: pubmed
order: 3
---

## PubMed 检索（Entrez E-utilities）

使用 `reldate=3&datetype=crdt` 获取最近 3 天入库的经颅磁刺激研究。

### 检索词

```text
("Transcranial Magnetic Stimulation"[Mesh] OR "transcranial magnetic stimulation"[Title/Abstract] OR "repetitive transcranial magnetic stimulation"[Title/Abstract] OR rTMS[Title/Abstract] OR "theta burst stimulation"[Title/Abstract] OR iTBS[Title/Abstract] OR cTBS[Title/Abstract])
```

严格执行 `esearch → esummary → efetch(xml)`：

1. `esearch` 使用上述检索词、`reldate=3`、`datetype=crdt`、`retmax=100`、`retmode=json`。
2. `esummary` 提取 PMID、标题、期刊和发表日期。
3. `efetch(xml)` 提取摘要；缺少摘要时写入 `No abstract available in source.`。
4. 只保留 `published_date` 为今天、昨天或前天的记录。
5. 按 PubMed URL 去重。

每条记录的 `category` 固定为 `TMS`，`source` 固定为 `pubmed`。
