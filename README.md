# 每日资讯 · Daily Insights

每日自动抓取 Brain MRI 相关学术内容，生成可浏览的本地仪表盘（含疾病分流、推荐摘要、期刊与影响因子信息）。

## 主要功能

- 单次 MRI 检索：每天只执行 `brainmri` PubMed 检索
- 疾病分流：按关键词复制到 Autism / Depression / ADHD / Alzheimer's / Parkinson's；未命中疾病的保留在 Brain MRI
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
│   ├── fetch.sh                      # 抓取入口（brainmri/all/指定领域）
│   ├── fetch_config.sh               # 模型与 prompt、自动 git 同步开关
│   ├── sync_impact_factors.py        # LetPub IF 同步（含 unresolved 在线补抓）
│   ├── generate_digest.py            # 生成 digest 推荐
│   └── schedule.sh                   # launchd 定时任务安装与管理
├── data/
│   ├── YYYY-MM-DD-<domain>.json      # 每日抓取结果
│   ├── if_unresolved_journals.json   # 仍未匹配 IF 的期刊清单
│   └── letpub/                        # LetPub 主库 + 手工补抓补充库
├── logs/                             # 定时任务日志
├── .agents/skills/
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
./scripts/fetch.sh brainmri           # Brain MRI + 疾病分流
./scripts/fetch.sh autism depression  # 等价于 brainmri：不会分别检索疾病
./scripts/fetch.sh all                # 等价于 brainmri
./scripts/fetch.sh if                 # 仅同步期刊 IF（不抓论文/新闻）
./scripts/fetch.sh if --reference user-manual-20260228 --journal "J Alzheimers Dis"
```

## 可抓取领域（当前）

- `brainmri`（Brain MRI；未命中疾病的 MRI 文献）
- `autism`
- `depression`
- `adhd`
- `ad`（Alzheimer's）
- `pd`（Parkinson's）

领域配置位于：`.agents/skills/academic-search/sources/*.md`

## 抓取链路

`fetch.sh brainmri` → `split_brainmri_by_disease.py`（疾病分流）→ `sync_impact_factors.py`（LetPub IF 同步 + unresolved 维护）→ `generate_digest.py`（推荐摘要）

IF 同步逻辑要点：

- IF 读取仅来自 `data/letpub/*`
- 优先按 ISSN/期刊名匹配 LetPub 本地库
- 若本地未命中，按 `if_unresolved_journals.json` 的 `manual_full_name` / ISSN 在线补抓并写入 `data/letpub/letpub_life_med_raw.json`
- IF 状态区分为：
  - `已收录影响因子`
  - `尚无影响因子`
  - `未查到影响因子`
- 未匹配到 IF 的期刊会进入 `data/if_unresolved_journals.json`

## 手工维护 IF（推荐流程）

1. 在 `data/if_unresolved_journals.json` 补充 `manual_full_name`
2. 运行 IF 同步：

```bash
python3 scripts/sync_impact_factors.py --reference auto-unresolved
```

3. 如需仅本地匹配（不访问 LetPub 在线）：

```bash
python3 scripts/sync_impact_factors.py --no-crawl
```

4. 用户手工输入期刊名触发抓取：

```bash
python3 scripts/sync_impact_factors.py \
  --reference user-manual-20260228 \
  --journal "Clin Neuroradiol|1869-1439|Clinical Neuroradiology" \
  --journal "Interdiscip Sci|1867-1462|Interdisciplinary Sciences: Computational Life Sciences" \
  --workers 8
```

完成后，前端会自动显示更新后的 IF（来自每日 data 文件里的 `impact_factor` 字段）。

另外会按 reference 分任务写入：
- 全局：`data/letpub/letpub_life_med_raw.json`
- 分任务：`data/letpub/references/<reference>.json`

注意：`--journals-file` 必须传具体文件，不能传目录（例如 `data/`）。

## 配置说明

编辑 `scripts/fetch_config.sh`：

- `MODEL_ID`：抓取使用的模型（默认 `gpt-5.4`）
- `CODEX_PROVIDER`：指定 Codex provider（默认 `openai`，避免服务器全局配置走过期中转）
- `AUTO_GIT_SYNC`：是否抓取后自动同步 GitHub（默认 `1`）
- `CODEX_TIMEOUT_SECONDS`：单次抓取超时秒数（默认 `600`，即 10 分钟；`0` 为不限制）

```bash
MODEL_ID="gpt-5.4"
CODEX_PROVIDER="openai"
AUTO_GIT_SYNC="1"
CODEX_TIMEOUT_SECONDS="600"
```

注意：自动同步仅提交 `data/` 目录。

## 定时任务（launchd）

使用：

```bash
./scripts/schedule.sh install
./scripts/schedule.sh status
./scripts/schedule.sh run-now brainmri
./scripts/schedule.sh uninstall
```

当前计划：

- Brain MRI：每天 `08:30`，抓取后自动分流到疾病标签

日志目录：`logs/`

## 华为云部署

当前项目已部署到华为云。服务器位置、无删除同步流程、备份、验收与回滚说明见：

- [docs/huawei-cloud-deployment.md](docs/huawei-cloud-deployment.md)

## API（由 `server.py` 提供）

- `GET /api/dates`：可用日期
- `GET /api/domains`：领域元数据
- `GET /api/status`：抓取任务状态
- `POST /api/fetch`：触发抓取（body: `{"mode":"brainmri"}` 等）
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
- 人工补 `manual_full_name` 后重跑 `python3 scripts/sync_impact_factors.py`

4. 抓取长时间无响应
- 默认单次抓取 10 分钟超时（`CODEX_TIMEOUT_SECONDS="600"`）
- 可临时调小超时快速失败排查，例如：`CODEX_TIMEOUT_SECONDS=120 ./scripts/fetch.sh brainmri`
- 设为 `0` 可关闭超时限制（不推荐）

## License

MIT
