# 三领域独立检索设计

## 目标

停止“广义 Brain MRI 检索后按疾病关键词分流”的流程。每日只维护三个独立栏目：

- `autism`：孤独症 + MRI
- `depression`：抑郁症 + MRI
- `tms`：所有经颅磁刺激研究，不要求 MRI 或特定疾病

历史 JSON 数据保留在 `data/`，但旧栏目不再出现在页面、API 和每日任务中。

## 活动配置

`.agents/skills/academic-search/sources/` 只保留 `autism.md`、`depression.md` 和新增的 `tms.md`，固定顺序为 `autism → depression → tms`。TMS 使用以下 PubMed 逻辑：

```text
"Transcranial Magnetic Stimulation"[Mesh]
OR "transcranial magnetic stimulation"[Title/Abstract]
OR "repetitive transcranial magnetic stimulation"[Title/Abstract]
OR rTMS[Title/Abstract]
OR "theta burst stimulation"[Title/Abstract]
OR iTBS[Title/Abstract]
OR cTBS[Title/Abstract]
```

TMS 与另外两个栏目一致，使用 `reldate=3&datetype=crdt`，随后只保留 `published_date` 为当天、前一天或前两天的记录，按 PubMed URL 去重，固定 `category="TMS"`。

## 每日数据流

`./scripts/fetch.sh all` 是默认入口，依次尝试三个独立检索。抓取失败只记入失败列表，不阻止后续栏目；成功文件子集进入同一个 IF 同步进程完成本地匹配和在线补查。IF 进程整体失败时，不对该子集执行过滤和 Digest，并最终非零退出。IF 成功后，每个文件分别执行以下步骤；单文件任一步失败只跳过该文件的后续步骤，其余文件继续：

1. 删除已知 `IF < 8` 的文章；
2. 删除 `not_available_yet`（明确尚无 IF）的文章；
3. 保留 `unresolved` / `lookup_error` 并登记补查；
4. 生成 Digest；
5. 执行最终校验。

只要抓取、共享 IF 或任一文件后处理失败，整个命令最终返回非零状态，并在日志中列出失败栏目/阶段。

## 命令与界面

活动抓取命令仅包括：

- 无参数或 `all`：运行三个栏目完整流程；
- `autism`、`depression`、`tms`：只运行指定栏目的完整流程；
- `if [参数]`：保持现有 IF 工具透传行为；无额外参数时处理 unresolved 登记的文件；
- `test`：为三个活动栏目生成合成数据并执行离线校验，不访问 PubMed/LetPub。

旧模式 `brainmri`、`mri`、`adhd`、`ad`、`pd`、`mefmri` 和 `ai` 必须给出 disabled 错误并非零退出。

`/api/domains` 保持 `{"domains":[...]}` envelope，精确返回三个包含 `id/label/category/color/icon/skill/order` 的对象，顺序为 `autism`、`depression`、`tms`。历史数据文件不得参与活动领域发现。页面沿用该 API，因此只显示三个栏目。

服务器和 macOS 定时任务均在每天 08:30 执行 `all`。launchd 使用 `com.dailyinsights.fetch.all` 和 `fetch-all*.log`；服务器使用 `daily-insights-fetch-all.timer` 激活 `daily-insights-fetch@all.service`。部署时禁用旧 `brainmri` 定时器，并同步更新部署文档。

## 清理边界

- 删除活动范围外的领域配置；历史数据不删除。
- 抓取流程不再调用 MRI 疾病分流脚本，并移除该孤立脚本及其测试。
- 不改动与三领域切换无关的 IF 数据库、历史结果或前端样式。
- `unresolved` / `lookup_error` 继续写入 `data/if_unresolved_journals.json`；同步工具的原子写入和退出语义保持不变。

## 验收

- `/api/domains` 按固定顺序精确返回 `autism`、`depression`、`tms`，即使 `data/` 仍有旧领域文件。
- `fetch.sh all` 精确枚举三个领域；旧模式不再映射到 Brain MRI。
- 中间一个抓取失败时，其余两个仍执行，最终非零退出并列出准确失败栏目。
- IF 过滤保留 `IF = 8`，删除 `IF < 8` 和 `not_available_yet`，保留真正未解析项。
- 自动化测试、Python 编译和 shell 语法检查通过。
- 华为云同步后，Web 服务和每日 `all` 定时任务处于 active/enabled 状态。
