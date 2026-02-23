---
id: mefmri
label: Multi-Echo fMRI
category: Multi-Echo fMRI
color: "#8b5cf6"
icon: brain
skill: academic-search
platforms: pubmed
order: 7
---

## PubMed 检索（Entrez E-utilities）

使用 `reldate=7&datetype=crdt` 动态获取最近 7 天入库的文献，无需硬编码日期。

### 检索词

```
("multi-echo"[Title/Abstract] OR "multiecho"[Title/Abstract] OR "multi echo"[Title/Abstract] OR "ME-EPI"[Title/Abstract]) AND ("fMRI"[Title/Abstract] OR "functional magnetic resonance imaging"[Title/Abstract] OR "functional MRI"[Title/Abstract] OR "BOLD"[Title/Abstract])
```

如需扩展或修改，直接编辑以上检索式，URL 编码后替换 `term=` 后的内容。

### Step 1：检索 PMIDs

将上方检索词 URL 编码后拼入请求：

```
term = (%22multi-echo%22%5BTitle%2FAbstract%5D+OR+%22multiecho%22%5BTitle%2FAbstract%5D+OR+%22multi+echo%22%5BTitle%2FAbstract%5D+OR+%22ME-EPI%22%5BTitle%2FAbstract%5D)+AND+(%22fMRI%22%5BTitle%2FAbstract%5D+OR+%22functional+magnetic+resonance+imaging%22%5BTitle%2FAbstract%5D+OR+%22functional+MRI%22%5BTitle%2FAbstract%5D+OR+%22BOLD%22%5BTitle%2FAbstract%5D)
```

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=(%22multi-echo%22%5BTitle%2FAbstract%5D+OR+%22multiecho%22%5BTitle%2FAbstract%5D+OR+%22multi+echo%22%5BTitle%2FAbstract%5D+OR+%22ME-EPI%22%5BTitle%2FAbstract%5D)+AND+(%22fMRI%22%5BTitle%2FAbstract%5D+OR+%22functional+magnetic+resonance+imaging%22%5BTitle%2FAbstract%5D+OR+%22functional+MRI%22%5BTitle%2FAbstract%5D+OR+%22BOLD%22%5BTitle%2FAbstract%5D)&reldate=7&datetype=crdt&retmax=100&retmode=json"
```

从返回 JSON 的 `esearchresult.idlist` 取出 PMID 列表。

### Step 2：获取元数据（esummary）

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=PMID1,PMID2,...&retmode=json"
```

提取字段：
- `title` → title
- `source` → source（期刊名）
- `edat`（Entrez 入库日期，格式 "YYYY/MM/DD HH:MM"）→ published_date（转为 YYYY-MM-DD）；若 `edat` 缺失则退用 `pubdate`
- `uid` → url：`https://pubmed.ncbi.nlm.nih.gov/{uid}/`

### Step 3：获取摘要文本（efetch）

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=PMID1,PMID2,...&retmode=xml&rettype=abstract"
```

从 XML 的 `<AbstractText>` 标签提取摘要作为 summary 字段。

---

## 过滤策略

- `reldate=7&datetype=crdt` 已按 Entrez 入库日期过滤，只返回最近 7 天入库的文献
- **不再对 `published_date` 做二次日期过滤**：PubMed 的 `edat` 是入库日期（近 7 天），已由 API 保证
- 按 `url` 去重

---

## 输出字段

| 字段 | 说明 |
|------|------|
| `title` | 论文标题（英文原文） |
| `summary` | 摘要（100-200 字） |
| `url` | PubMed 链接 |
| `category` | 固定为 `"Multi-Echo fMRI"` |
| `source` | `"pubmed"` |
| `published_date` | `YYYY-MM-DD` 格式 |
| `date` | 抓取日期（今天） |
