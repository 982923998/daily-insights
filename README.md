# 每日资讯 · Daily Insights

每日自动抓取 AI 与脑影像相关学术内容，生成可浏览的本地仪表盘（含推荐摘要、期刊与影响因子信息）。

## 主要功能

- AI 资讯抓取：按当天日期抓取并去重
- 学术领域抓取：按领域配置文件执行 PubMed 检索
- 自动增强学术条目：补全期刊、ISSN、影响因子状态
- Digest 推荐：每个数据文件自动生成 `digest`（优先级与推荐项）
- 数据质量门禁：抓取后执行 schema/字段/去重校验（不通过即中止后续处理）
- 前端可视化：推荐项保留 `Jump to card`，并用高亮标签展示“期刊名 / IF”
- 本地服务：Web 页面 + API + SSE 实时日志
- 定时任务：`launchd` 自动定时抓取
- 可选自动同步：抓取后自动 `git add/commit/push` `data/`（同步失败不影响本地抓取成功）

## 项目结构

```text
Daily Insights/
├── web/
│   └── index.html                    # 前端（React + Tailwind 单文件）
├── scripts/
│   ├── server.py                     # 本地 HTTP 服务（页面 + API + SSE）
│   ├── fetch.sh                      # 抓取入口（ai/all/指定领域）
│   ├── fetch_config.sh               # 模型与 prompt、自动 git 同步开关
│   ├── enrich_journal.py             # 期刊/ISSN/IF 增强 + unresolved 维护
│   ├── generate_digest.py            # 生成 digest 推荐
│   └── schedule.sh                   # launchd 定时任务安装与管理
├── data/
│   ├── YYYY-MM-DD-<domain>.json      # 每日抓取结果
│   ├── journal_impact_factors.json   # IF 注册表（可人工维护）
│   ├── if_unresolved_journals.json   # 仍未匹配 IF 的期刊清单
│   └── letpub/                        # LetPub 期刊库缓存
├── logs/                             # 定时任务日志
├── .agents/skills/
│   ├── daily-ai-news/
│   └── academic-search/sources/*.md  # 学术领域配置
├── 启动.command                       # 双击启动本地服务并打开网页
└── install.sh                        # 安装向导（含桌面 app）
```

## 环境依赖

- macOS（定时任务与安装脚本按 macOS 编写）
- Python 3.8+
- Node.js 18+
- `codex` CLI
- 网络可访问 PubMed / LetPub / 新闻源

## 快速开始

1. 启动服务

```bash
python3 scripts/server.py
```

打开：<http://localhost:8080>

2. 或双击启动

- 双击项目根目录 `启动.command`

3. 抓取数据

```bash
./scripts/fetch.sh ai                 # 仅 AI
./scripts/fetch.sh brainmri           # 仅 Brain MRI
./scripts/fetch.sh autism depression  # 指定多个学术领域
./scripts/fetch.sh all                # AI + 全部学术领域
```

## 可抓取领域（当前）

- `ai`（AI News）
- `autism`
- `depression`
- `adhd`
- `ad`（Alzheimer's）
- `pd`（Parkinson's）
- `mefmri`（Multi-Echo fMRI）
- `brainmri`

领域配置位于：`.agents/skills/academic-search/sources/*.md`

## 抓取链路（学术）

`fetch.sh`（按领域触发）→ `enrich_journal.py`（期刊与 IF 增强）→ `generate_digest.py`（推荐摘要）

增强逻辑要点：

- 从 PubMed `esummary` 补 `journal` 与 `journal_issn`
- 优先按 ISSN/期刊名匹配 LetPub 数据
- IF 状态区分为：
  - `已收录影响因子`
  - `尚无影响因子`
  - `未查到影响因子`
- 未匹配到 IF 的期刊会进入 `data/if_unresolved_journals.json`

## 手工维护 IF（推荐流程）

1. 编辑 `data/journal_impact_factors.json` 对应期刊条目（`impact_factor` / `if_year` / `if_status`）
2. 回填历史文件：

```bash
for f in data/2026-*.json; do
  python3 scripts/enrich_journal.py "$f"
done
```

完成后，前端会自动显示更新后的 IF。

## 配置说明

编辑 `scripts/fetch_config.sh`：

- `MODEL_ID`：抓取使用的模型（默认 `gpt-5.3-codex`）
- `CODEX_PROVIDER`：可选，指定 Codex provider（默认留空，跟随本机 `codex` 默认配置）
- `AUTO_GIT_SYNC`：是否抓取后自动同步 GitHub（默认 `1`）
- `CODEX_TIMEOUT_SECONDS`：单次抓取超时秒数（默认 `600`，即 10 分钟；`0` 为不限制）

```bash
MODEL_ID="gpt-5.3-codex"
CODEX_PROVIDER=""
AUTO_GIT_SYNC="1"
CODEX_TIMEOUT_SECONDS="600"
```

注意：自动同步仅提交 `data/` 目录。

## 定时任务（launchd）

使用：

```bash
./scripts/schedule.sh install
./scripts/schedule.sh status
./scripts/schedule.sh run-now ai
./scripts/schedule.sh run-now brainmri
./scripts/schedule.sh run-now academic
./scripts/schedule.sh run-now mefmri
./scripts/schedule.sh uninstall
```

当前计划：

- AI：每天 `08:00`
- Brain MRI：每天 `08:30`
- 学术批量（autism/depression/adhd/ad/pd）：每 `3` 天
- ME-fMRI：每 `7` 天

日志目录：`logs/`

## API（由 `server.py` 提供）

- `GET /api/dates`：可用日期
- `GET /api/domains`：领域元数据
- `GET /api/status`：抓取任务状态
- `POST /api/fetch`：触发抓取（body: `{"mode":"ai"}` 等）
- `GET /api/events?mode=<id>`：SSE 日志流

## 数据格式

```json
{
  "date": "2026-02-26",
  "articles": [
    {
      "title": "...",
      "summary": "...",
      "url": "https://...",
      "category": "Brain MRI",
      "source": "pubmed",
      "journal": "J Neural Eng",
      "journal_issn": "1741-2552",
      "impact_factor": 3.8,
      "impact_factor_year": 2024,
      "impact_factor_status": "已收录影响因子",
      "published_date": "2026-02-26",
      "date": "2026-02-26"
    }
  ],
  "digest": {
    "summary": "...",
    "stats": { "total": 0, "high_priority": 0, "medium_priority": 0, "low_priority": 0 },
    "recommendations": []
  }
}
```

## 常见问题

1. 抓取后没有推送到 GitHub
- 确认 `AUTO_GIT_SYNC="1"`
- 确认当前目录是 Git 仓库，且远程与权限可用
- 查看 `logs/` 与 `scripts/fetch.sh` 输出中的 git 错误
- 注意：即使 git 同步失败，`data/` 本地文件仍会保留，抓取本身不算失败

2. 页面刷新看不到最新样式
- 使用强制刷新：`Cmd + Shift + R`

3. 某些期刊一直没有 IF
- 查看 `data/if_unresolved_journals.json`
- 人工补充后重跑 `enrich_journal.py`

4. 抓取长时间无响应
- 默认单次抓取 10 分钟超时（`CODEX_TIMEOUT_SECONDS="600"`）
- 可临时调小超时快速失败排查，例如：`CODEX_TIMEOUT_SECONDS=120 ./scripts/fetch.sh ai`
- 设为 `0` 可关闭超时限制（不推荐）

## License

MIT
