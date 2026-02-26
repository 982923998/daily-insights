---
id: brainmri
label: Brain MRI
category: Brain MRI
color: "#0ea5e9"
icon: crosshair
skill: academic-search
platforms: pubmed
order: 8
---

## PubMed 检索（Entrez E-utilities）

使用 `reldate=2&datetype=crdt` 动态获取最近 2 天入库的文献（覆盖今天与前一天），无需硬编码日期。

### 检索词

```
("Brain"[Mesh] OR brain*[Title/Abstract] OR cerebr*[Title/Abstract] OR encephalon[Title/Abstract] OR intracranial[Title/Abstract]) AND ("Magnetic Resonance Imaging"[Mesh] OR "MRI"[Title/Abstract] OR "magnetic resonance"[Title/Abstract] OR "fMRI"[Title/Abstract] OR "DTI"[Title/Abstract] OR "diffusion tensor"[Title/Abstract] OR "VBM"[Title/Abstract] OR "voxel-based morphometry"[Title/Abstract] OR "connectome"[Title/Abstract] OR "arterial spin labeling"[Title/Abstract] OR "magnetic resonance spectroscopy"[Title/Abstract])
```

如需扩展或修改，直接编辑以上检索式，URL 编码后替换 `term=` 后的内容。

### Step 1：检索 PMIDs

将上方检索词 URL 编码后拼入请求：

```
term = (%22Brain%22%5BMesh%5D+OR+brain*%5BTitle%2FAbstract%5D+OR+cerebr*%5BTitle%2FAbstract%5D+OR+encephalon%5BTitle%2FAbstract%5D+OR+intracranial%5BTitle%2FAbstract%5D)+AND+(%22Magnetic+Resonance+Imaging%22%5BMesh%5D+OR+%22MRI%22%5BTitle%2FAbstract%5D+OR+%22magnetic+resonance%22%5BTitle%2FAbstract%5D+OR+%22fMRI%22%5BTitle%2FAbstract%5D+OR+%22DTI%22%5BTitle%2FAbstract%5D+OR+%22diffusion+tensor%22%5BTitle%2FAbstract%5D+OR+%22VBM%22%5BTitle%2FAbstract%5D+OR+%22voxel-based+morphometry%22%5BTitle%2FAbstract%5D+OR+%22connectome%22%5BTitle%2FAbstract%5D+OR+%22arterial+spin+labeling%22%5BTitle%2FAbstract%5D+OR+%22magnetic+resonance+spectroscopy%22%5BTitle%2FAbstract%5D)
```

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=(%22Brain%22%5BMesh%5D+OR+brain*%5BTitle%2FAbstract%5D+OR+cerebr*%5BTitle%2FAbstract%5D+OR+encephalon%5BTitle%2FAbstract%5D+OR+intracranial%5BTitle%2FAbstract%5D)+AND+(%22Magnetic+Resonance+Imaging%22%5BMesh%5D+OR+%22MRI%22%5BTitle%2FAbstract%5D+OR+%22magnetic+resonance%22%5BTitle%2FAbstract%5D+OR+%22fMRI%22%5BTitle%2FAbstract%5D+OR+%22DTI%22%5BTitle%2FAbstract%5D+OR+%22diffusion+tensor%22%5BTitle%2FAbstract%5D+OR+%22VBM%22%5BTitle%2FAbstract%5D+OR+%22voxel-based+morphometry%22%5BTitle%2FAbstract%5D+OR+%22connectome%22%5BTitle%2FAbstract%5D+OR+%22arterial+spin+labeling%22%5BTitle%2FAbstract%5D+OR+%22magnetic+resonance+spectroscopy%22%5BTitle%2FAbstract%5D)&reldate=2&datetype=crdt&retmax=100&retmode=json"
```

从返回 JSON 的 `esearchresult.idlist` 取出 PMID 列表。

### Step 2：获取元数据（esummary）

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=PMID1,PMID2,...&retmode=json"
```

提取字段：
- `title` → title
- `source` → source（期刊名）
- `pubdate`（实际发表日期）→ published_date（转为 YYYY-MM-DD）；若 `pubdate` 仅有年月则补 01 日
- `uid` → url：`https://pubmed.ncbi.nlm.nih.gov/{uid}/`

### Step 3：获取摘要文本（efetch）

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=PMID1,PMID2,...&retmode=xml&rettype=abstract"
```

从 XML 的 `<AbstractText>` 标签提取摘要作为 summary 字段。

---

## 过滤策略

- `reldate=2&datetype=crdt` 是初筛（按入库日期取最近 2 天）
- **二次过滤（必须执行）**：只保留 `published_date` 为今天或前一天（YYYY-MM-DD）的文章，丢弃更早日期的
- 按 `url` 去重

---

## 输出字段

| 字段 | 说明 |
|------|------|
| `title` | 论文标题（英文原文） |
| `summary` | 摘要（100-200 字） |
| `url` | PubMed 链接 |
| `category` | 固定为 `"Brain MRI"` |
| `source` | `"pubmed"` |
| `published_date` | `YYYY-MM-DD` 格式 |
| `date` | 抓取日期（今天） |
