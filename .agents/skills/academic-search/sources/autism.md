---
id: autism
label: Autism Research
category: Autism
color: "#14b8a6"
icon: activity
skill: academic-search
platforms: pubmed
order: 2
---

## PubMed 检索（Entrez E-utilities）

使用 `reldate=3&datetype=crdt` 动态获取最近 3 天入库的文献，无需硬编码日期。

### 检索词

```
("Autism Spectrum Disorder"[Mesh] OR "ASD"[Title/Abstract] OR "autism"[Title/Abstract] OR "autistic"[Title/Abstract]) AND ("MRI"[Title/Abstract] OR "magnetic resonance imaging"[Title/Abstract] OR "brain MRI"[Title/Abstract] OR "structural MRI"[Title/Abstract] OR "fMRI"[Title/Abstract] OR "functional MRI"[Title/Abstract] OR "resting-state"[Title/Abstract] OR "resting state fMRI"[Title/Abstract] OR "functional connectivity"[Title/Abstract] OR "BOLD"[Title/Abstract] OR "DTI"[Title/Abstract] OR "diffusion tensor imaging"[Title/Abstract] OR "diffusion MRI"[Title/Abstract] OR "tractography"[Title/Abstract] OR "VBM"[Title/Abstract] OR "voxel-based morphometry"[Title/Abstract] OR "cortical thickness"[Title/Abstract] OR "brain volume"[Title/Abstract] OR "gray matter"[Title/Abstract] OR "white matter"[Title/Abstract] OR "neuroimaging"[Title/Abstract] OR "brain imaging"[Title/Abstract] OR "brain mapping"[Title/Abstract] OR "connectome"[Title/Abstract] OR "MRS"[Title/Abstract] OR "magnetic resonance spectroscopy"[Title/Abstract] OR "arterial spin labeling"[Title/Abstract] OR "ASL"[Title/Abstract] OR "perfusion MRI"[Title/Abstract])
```

如需扩展或修改，直接编辑以上检索式，URL 编码后替换 `term=` 后的内容。

### Step 1：检索 PMIDs

将上方检索词 URL 编码后拼入请求：

```
term = (%22Autism+Spectrum+Disorder%22%5BMesh%5D+OR+%22ASD%22%5BTitle%2FAbstract%5D+OR+%22autism%22%5BTitle%2FAbstract%5D+OR+%22autistic%22%5BTitle%2FAbstract%5D)+AND+(%22MRI%22%5BTitle%2FAbstract%5D+OR+%22magnetic+resonance+imaging%22%5BTitle%2FAbstract%5D+OR+%22brain+MRI%22%5BTitle%2FAbstract%5D+OR+%22structural+MRI%22%5BTitle%2FAbstract%5D+OR+%22fMRI%22%5BTitle%2FAbstract%5D+OR+%22functional+MRI%22%5BTitle%2FAbstract%5D+OR+%22resting-state%22%5BTitle%2FAbstract%5D+OR+%22resting+state+fMRI%22%5BTitle%2FAbstract%5D+OR+%22functional+connectivity%22%5BTitle%2FAbstract%5D+OR+%22BOLD%22%5BTitle%2FAbstract%5D+OR+%22DTI%22%5BTitle%2FAbstract%5D+OR+%22diffusion+tensor+imaging%22%5BTitle%2FAbstract%5D+OR+%22diffusion+MRI%22%5BTitle%2FAbstract%5D+OR+%22tractography%22%5BTitle%2FAbstract%5D+OR+%22VBM%22%5BTitle%2FAbstract%5D+OR+%22voxel-based+morphometry%22%5BTitle%2FAbstract%5D+OR+%22cortical+thickness%22%5BTitle%2FAbstract%5D+OR+%22brain+volume%22%5BTitle%2FAbstract%5D+OR+%22gray+matter%22%5BTitle%2FAbstract%5D+OR+%22white+matter%22%5BTitle%2FAbstract%5D+OR+%22neuroimaging%22%5BTitle%2FAbstract%5D+OR+%22brain+imaging%22%5BTitle%2FAbstract%5D+OR+%22brain+mapping%22%5BTitle%2FAbstract%5D+OR+%22connectome%22%5BTitle%2FAbstract%5D+OR+%22MRS%22%5BTitle%2FAbstract%5D+OR+%22magnetic+resonance+spectroscopy%22%5BTitle%2FAbstract%5D+OR+%22arterial+spin+labeling%22%5BTitle%2FAbstract%5D+OR+%22ASL%22%5BTitle%2FAbstract%5D+OR+%22perfusion+MRI%22%5BTitle%2FAbstract%5D)
```

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=(%22Autism+Spectrum+Disorder%22%5BMesh%5D+OR+%22ASD%22%5BTitle%2FAbstract%5D+OR+%22autism%22%5BTitle%2FAbstract%5D+OR+%22autistic%22%5BTitle%2FAbstract%5D)+AND+(%22MRI%22%5BTitle%2FAbstract%5D+OR+%22magnetic+resonance+imaging%22%5BTitle%2FAbstract%5D+OR+%22brain+MRI%22%5BTitle%2FAbstract%5D+OR+%22structural+MRI%22%5BTitle%2FAbstract%5D+OR+%22fMRI%22%5BTitle%2FAbstract%5D+OR+%22functional+MRI%22%5BTitle%2FAbstract%5D+OR+%22resting-state%22%5BTitle%2FAbstract%5D+OR+%22resting+state+fMRI%22%5BTitle%2FAbstract%5D+OR+%22functional+connectivity%22%5BTitle%2FAbstract%5D+OR+%22BOLD%22%5BTitle%2FAbstract%5D+OR+%22DTI%22%5BTitle%2FAbstract%5D+OR+%22diffusion+tensor+imaging%22%5BTitle%2FAbstract%5D+OR+%22diffusion+MRI%22%5BTitle%2FAbstract%5D+OR+%22tractography%22%5BTitle%2FAbstract%5D+OR+%22VBM%22%5BTitle%2FAbstract%5D+OR+%22voxel-based+morphometry%22%5BTitle%2FAbstract%5D+OR+%22cortical+thickness%22%5BTitle%2FAbstract%5D+OR+%22brain+volume%22%5BTitle%2FAbstract%5D+OR+%22gray+matter%22%5BTitle%2FAbstract%5D+OR+%22white+matter%22%5BTitle%2FAbstract%5D+OR+%22neuroimaging%22%5BTitle%2FAbstract%5D+OR+%22brain+imaging%22%5BTitle%2FAbstract%5D+OR+%22brain+mapping%22%5BTitle%2FAbstract%5D+OR+%22connectome%22%5BTitle%2FAbstract%5D+OR+%22MRS%22%5BTitle%2FAbstract%5D+OR+%22magnetic+resonance+spectroscopy%22%5BTitle%2FAbstract%5D+OR+%22arterial+spin+labeling%22%5BTitle%2FAbstract%5D+OR+%22ASL%22%5BTitle%2FAbstract%5D+OR+%22perfusion+MRI%22%5BTitle%2FAbstract%5D)&reldate=3&datetype=crdt&retmax=100&retmode=json"
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

- `reldate=3&datetype=crdt` 是初筛（按入库日期取最近 3 天）
- **二次过滤（必须执行）**：只保留 `published_date` 在最近 3 天内的文章，丢弃更早日期的
- 按 `url` 去重

---

## 输出字段

| 字段 | 说明 |
|------|------|
| `title` | 论文标题（英文原文） |
| `summary` | 摘要（100-200 字） |
| `url` | PubMed 链接 |
| `category` | 固定为 `"Autism"` |
| `source` | `"pubmed"` |
| `published_date` | `YYYY-MM-DD` 格式 |
| `date` | 抓取日期（今天） |
