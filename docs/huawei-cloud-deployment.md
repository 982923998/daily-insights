# 华为云部署与同步

本文记录 `daily-insights` 的华为云运行位置，以及以后将本地新更改同步到服务器的标准流程。

> 安全说明：仓库不保存服务器密码、令牌或其他凭据。连接时使用 SSH 密钥（推荐）或交互式输入凭据。

## 当前部署信息

| 项目 | 当前值 |
| --- | --- |
| 服务器 | `root@139.9.67.96` |
| 系统 | Ubuntu 22.04 LTS |
| 项目目录 | `/projects/daily-insights` |
| 公网入口 | <http://139.9.67.96/daily-insights/> |
| Web 服务 | `daily-insights.service` |
| 每日任务定时器 | `daily-insights-fetch-all.timer`（已禁用） |
| IF 补查定时器 | `daily-insights-if-maintenance.timer`（已禁用） |
| 当前抓取位置 | 本机 launchd，每天 08:30（Asia/Shanghai） |
| 后端监听 | `127.0.0.1:8080`，由 Nginx 反向代理 |

公网只提供页面和只读数据接口。`POST /api/fetch` 在 Nginx 层返回 `403`。

自 2026-07-28 起，华为云不再执行自动抓取或 IF 补查，仅保留 Web 服务和历史数据。每日抓取由本机 `com.dailyinsights.fetch.all` LaunchAgent 执行，服务器数据按需手动同步。

## 同步原则

服务器上的 `data/` 包含运行期间产生的历史数据，不能把它当作可随时覆盖的纯代码副本。因此：

- 同步前先备份远端项目。
- `rsync` 不使用 `--delete`，避免删除服务器独有数据。
- 不在服务器执行 `git reset --hard`、`git clean` 或未经检查的 `git pull`。
- 同步时排除 `.git`、临时文件和 Python 缓存。
- 代码更新后先跑测试，再重启服务，最后检查公网接口和定时器。

## 标准同步流程

以下命令均从本地项目根目录执行。

### 1. 本地检查

```bash
git status --short
python3 -m unittest discover -s tests -q
python3 -m py_compile scripts/*.py tests/*.py
bash -n scripts/*.sh
```

确认测试通过，并检查待同步的改动确实属于本次更新。

### 2. 备份服务器

```bash
ssh root@139.9.67.96
backup_stamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p /projects/backups
tar \
  --exclude='daily-insights/.git' \
  --exclude='daily-insights/.tmp' \
  --exclude='daily-insights/.tmp_*' \
  -czf "/projects/backups/daily-insights-${backup_stamp}.tar.gz" \
  -C /projects daily-insights
sha256sum "/projects/backups/daily-insights-${backup_stamp}.tar.gz"
exit
```

保存命令输出中的备份路径和 SHA256。

### 3. 无删除同步

```bash
rsync -az --no-owner --no-group \
  --exclude='.git/' \
  --exclude='.DS_Store' \
  --exclude='.tmp/' \
  --exclude='.tmp_*' \
  --exclude='__pycache__/' \
  ./ root@139.9.67.96:/projects/daily-insights/
```

该命令会更新同名文件，但不会删除服务器独有文件。若本次明确不应覆盖某类服务器数据，应在同步前增加对应的 `--exclude`。

本次三领域迁移还需在完成备份后，定点删除服务器上的退役代码；不要删除任何 `data/*.json`：

```bash
rm -f \
  /projects/daily-insights/.agents/skills/academic-search/sources/{brainmri,adhd,ad,pd,mefmri}.md \
  /projects/daily-insights/scripts/split_brainmri_by_disease.py \
  /projects/daily-insights/tests/test_split_brainmri_by_disease.py
```

随后把服务器定时器从 `brainmri` 切换到 `all`：

```bash
cp /etc/systemd/system/daily-insights-fetch-brainmri.timer \
  /etc/systemd/system/daily-insights-fetch-all.timer
sed -i \
  -e 's/BrainMRI/Autism Depression TMS/' \
  -e 's/@brainmri/@all/' \
  /etc/systemd/system/daily-insights-fetch-all.timer
systemctl daemon-reload
systemctl disable --now daily-insights-fetch-brainmri.timer
systemctl enable --now daily-insights-fetch-all.timer
```

安装每日 unresolved IF 补查任务：

```bash
cp deploy/systemd/daily-insights-if-maintenance.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now daily-insights-if-maintenance.timer
```

该任务复用 `daily-insights-fetch@.service`，运行 `fetch.sh if`。它只处理
`autism/depression/tms` 中仍含 unresolved 期刊的文件，回填后重新执行 IF ≥ 8
过滤、摘要生成和最终校验。

### 4. 远端测试与重启

```bash
ssh root@139.9.67.96
cd /projects/daily-insights
python3 -m unittest discover -s tests -q
python3 -m py_compile scripts/*.py tests/*.py
bash -n scripts/*.sh
nginx -t
systemctl restart daily-insights.service
systemctl is-active daily-insights.service
systemctl is-enabled daily-insights.service
systemctl is-active daily-insights-fetch-all.timer
systemctl is-enabled daily-insights-fetch-all.timer
systemctl is-active daily-insights-if-maintenance.timer
systemctl is-enabled daily-insights-if-maintenance.timer
ss -ltnp | grep ':8080'
exit
```

预期 Web 服务和定时器均为 `active`、`enabled`，且 `8080` 只监听 `127.0.0.1`。

### 5. 公网验收

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' http://139.9.67.96/daily-insights/
curl -fsS -o /dev/null -w '%{http_code}\n' http://139.9.67.96/api/domains
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"mode":"all"}' \
  http://139.9.67.96/api/fetch
```

预期状态码依次为 `200`、`200`、`403`。同时确认公网无法直接访问 `139.9.67.96:8080`。

## 回滚

若部署后出现问题，先停止服务并把备份解压到新的检查目录，不要直接覆盖当前项目：

```bash
ssh root@139.9.67.96
systemctl stop daily-insights.service
restore_dir="/projects/restore-daily-insights-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$restore_dir"
tar -xzf /projects/backups/daily-insights-<时间戳>.tar.gz -C "$restore_dir"
```

检查恢复副本后，再决定是否切换目录；完成后运行远端测试并重新启动服务。

## 部署记录

### 2026-07-23

- 首次确认并完成华为云正式部署。
- 部署本地提交：`11ea5a2`、`60933da`。
- 部署前备份：`/projects/backups/daily-insights-20260723-200454.tar.gz`。
- 备份 SHA256：`b570307eef091114ef0f8058be52e22122e6c19062b160eceefed00687a10b11`。
- 验收结果：远端 49 项测试通过；Nginx 配置通过；页面、API 和六类最新数据均可访问；公网触发抓取被禁止；`8080` 未对公网开放。
- 部署三领域迁移提交 `99f8dea`：仅保留 Autism + MRI、Depression + MRI、TMS，统一执行 IF ≥ 8 过滤。
- 三领域迁移备份：`/projects/backups/daily-insights-20260723-214118.tar.gz`；SHA256：`f64bdb094622ecd6167dd9244c06503875ee154da868e5d8a01b2c5f7a6c262b`。
- 三领域迁移验收：远端 49 项测试通过；`/api/domains` 精确返回 `autism/depression/tms`；`daily-insights-fetch-all.timer` 已启用，旧 `brainmri` timer 已禁用；历史 Brain MRI JSON 保留。
- 增加 `daily-insights-if-maintenance.timer`：每天 11:00 复查三个活动领域的 unresolved IF，并在回填后重新执行 IF ≥ 8 过滤和最终校验。
- 2026-07-28：停用华为云 `daily-insights-fetch-all.timer` 和 `daily-insights-if-maintenance.timer`；后续仅在本机每天 08:30 抓取，华为云保留 Web 展示。
