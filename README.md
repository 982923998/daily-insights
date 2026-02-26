# 每日资讯 · Daily Insights

每日自动抓取 AI 资讯与孤独症（ASD）前沿研究，通过本地 Web 界面浏览、搜索与收藏。

![界面预览](https://img.shields.io/badge/stack-Python%20%7C%20React%20%7C%20Tailwind-blue)

---

## 功能

- **AI 资讯**：聚合当日 AI 领域新闻
- **Autism 研究**：从 PubMed / arXiv 抓取近3天内发布的 ASD 相关论文
- **收藏夹**：书签收藏感兴趣的文章，持久化存储在浏览器 localStorage
- **日期切换**：查看历史任意日期的资讯
- **实时日志**：抓取过程日志通过 SSE 实时推送到界面
- **Run Digest 推荐面板**：支持 `Jump to card` 快速跳转
- **期刊/IF 可视化**：推荐项中以两枚高亮标签展示“期刊名”和“IF”
- **IF 未命中追踪**：自动维护 `data/if_unresolved_journals.json` 便于人工补录

---

## 项目结构

```text
每日资讯/
├── web/
│   └── index.html          # 前端（React + Tailwind，单文件）
├── scripts/
│   ├── server.py           # 本地 HTTP 服务器（兼 API）
│   ├── fetch.sh            # 抓取任务入口
│   ├── fetch_config.sh     # 模型 ID 与 Prompt 模板配置
│   ├── enrich_journal.py   # 补全期刊名 + 同步影响因子注册表
│   └── generate_digest.py  # 生成摘要与推荐
├── data/                   # 抓取结果 JSON，按日期命名
│   ├── YYYY-MM-DD-ai.json
│   ├── YYYY-MM-DD-autism.json
│   └── journal_impact_factors.json  # 手工维护期刊 IF
└── .agents/
    └── skills/
        ├── pubmed-search/  # PubMed 语义搜索（Valyu API）
        ├── arxiv-search/   # arXiv 搜索
        └── daily-ai-news/  # AI 资讯聚合
```

---

## 依赖

- Python 3.8+
- Node.js 18+（pubmed-search 脚本使用内置 fetch）
- [opencode](https://opencode.ai) CLI
- [Valyu API Key](https://platform.valyu.ai)（PubMed 语义搜索，$10 免费额度）

---

## 快速开始

### 1. 启动本地服务器

```bash
python3 scripts/server.py
```

浏览器访问 <http://localhost:8080>

### 2. 配置模型

编辑 `scripts/fetch_config.sh`，修改 `MODEL_ID`：

```bash
MODEL_ID="opencode/kimi-k2.5-free"   # 或其他 opencode 支持的模型
```

如需抓取后自动推送到 GitHub，可在同文件设置：

```bash
AUTO_GIT_SYNC="1"   # 1=开启自动 git commit/push，0=关闭
```

### 3. 抓取资讯

在网页界面点击 `Fetch AI News` / `Fetch Autism News`，或直接命令行运行：

```bash
./scripts/fetch.sh ai       # 抓取 AI 资讯
./scripts/fetch.sh autism   # 抓取 Autism 研究
./scripts/fetch.sh all      # 两者都抓取
```

### 4. 手工维护影响因子

学术抓取后，系统会自动把新期刊写入 `data/journal_impact_factors.json`。  
你只需要手工填写对应条目的 `impact_factor` 与 `if_year`，前端会自动显示。

若你更新了注册表并希望历史数据立即刷新 IF，可执行：

```bash
for f in data/2026-*.json; do
  python3 scripts/enrich_journal.py "$f"
done
```

当期刊暂时无法匹配 IF 时，会写入 `data/if_unresolved_journals.json`。  
后续可手工补全 `journal_impact_factors.json` 后重跑 `enrich_journal.py` 自动消解。

---

## 数据格式

每个 JSON 文件结构如下：

```json
{
  "date": "2026-02-18",
  "articles": [
    {
      "title": "文章标题",
      "summary": "摘要",
      "url": "https://example.com",
      "category": "AI",
      "source": "来源",
      "journal": "期刊名（学术文献）",
      "impact_factor": 12.3,
      "impact_factor_year": 2024,
      "impact_factor_status": "已收录影响因子 | 尚无影响因子 | 未查到影响因子",
      "published_date": "2026-02-18",
      "date": "2026-02-18"
    }
  ]
}
```

---

## License

MIT
