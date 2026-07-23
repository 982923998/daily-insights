# Daily Insights 全项目优化设计

日期：2026-07-23

## 目标

将 Daily Insights 收敛为一条可验证、可重复运行的本地 Brain MRI 每日流水线：抓取 PubMed 文献，补全期刊 IF，删除已知 `IF < 6` 的文章，完成疾病分流和 digest，并由前端直接展示每日数据文件中的 IF。

本设计采用以下已声明规则：

- 数值 IF `< 6` 的文章删除，`IF == 6` 保留。
- IF 未知、未匹配或期刊尚无 IF 的文章暂时保留，但必须有明确状态，不能伪装成通过门槛。
- 历史数据不在日常优化中直接批量删除；先提供 dry-run 报告，后续经用户确认再迁移。
- 保留工作区内现有未提交改动，不重构无关功能。

## 当前问题

1. `sync_impact_factors.py` 只统计匹配数量和更新注册表，没有把 IF 写回文章 JSON。
2. 每日任务对六个分流文件分别同步 IF，结尾又执行一次全局同步，造成重复查询和非幂等计数。
3. 上游未保留 PubMed ISSN，后续只能依赖期刊简称匹配。
4. digest 在可靠的 IF 门禁之前生成，无法保证推荐中不存在低 IF 文章。
5. 前端每次下载约 2.4 MB LetPub 数据并在浏览器临时匹配，与 README 的文章自包含契约冲突。
6. 本地 HTTP 服务存在目录穿越风险并监听全部网卡。
7. 日期、IF 状态、过滤结果和 shell 编排缺少自动化测试。

## 总体架构

### 每日数据流

正式顺序固定为：

1. 在唯一批次临时目录中抓取 Brain MRI，工作主文件先包含本次抓取的全部文章。
2. 校验原始文章 schema、日期、URL 与唯一性。
3. 对工作主文件执行一次 IF enrichment。
4. 删除所有已知且有限数值 `IF < 6` 的文章；保留 `IF >= 6` 和未知 IF。
5. 再次校验 IF 合同与过滤门禁。
6. 将过滤后的工作主文件分流到 Autism、Depression、ADHD、Alzheimer's、Parkinson's；最终 `brainmri` 文件只保存未命中任何疾病的文章，多疾病文章复制到每个命中的疾病文件。
7. 校验六个输出文件。
8. 分别为六个过滤后输出文件生成各自的 digest；每个 digest 只能引用同文件的最终 articles。
9. 最终校验全部产物后，将六个文件作为一个批次发布，随后才允许可选 Git 同步。digest 沿用现有结构，嵌入各文章文件的顶层 `digest` 字段，因此正式产物仍是六个文件。

IF enrichment、过滤或最终校验失败时，任务必须失败，不得继续生成 digest 或推送数据。抓取、enrichment、过滤、分流和 digest 都在批次临时目录内完成；六个正式文件只在整批验证通过后依次使用 `os.replace` 发布，普通异常时从备份回滚。该机制不声称跨六文件具备文件系统事务性：若进程在发布过程中被强制终止，顶层 `batch_id` 可识别混合批次，`/api/dates` 和前端不得展示六文件 `batch_id` 不一致的日期；下一次运行重新发布完整批次。

### 文章 IF 合同

每篇有期刊的文章必须包含以下机器可读字段：

```json
{
  "journal": "Journal name",
  "journal_issn": "1234-5678",
  "impact_factor": 8.2,
  "impact_factor_year": null,
  "impact_factor_status": "available",
  "impact_factor_source": "letpub",
  "impact_factor_match_method": "issn",
  "impact_factor_matched_journal": "Canonical journal name"
}
```

状态固定为：

- `available`：存在有限正数 IF。
- `not_available_yet`：已匹配期刊，但数据源没有正数 IF；`impact_factor` 为 `null`。
- `unresolved`：未匹配或查询失败；`impact_factor` 为 `null`，并记录 `impact_factor_unresolved_reason`。

中文仅用于前端展示，不写入机器状态字段。IF 年份无法从现有 LetPub 数据确认时保持 `null`，不得猜测。

### 匹配规则

匹配顺序为：

1. exact normalized ISSN；
2. exact normalized canonical/full journal name；
3. exact normalized abbreviation。

不再使用“取最大 IF”解决冲突。来源优先级固定为：

1. `letpub_manual_overrides.json` 中经人工或显式在线任务确认的记录；
2. `letpub_life_med_raw.json` 中 `source=letpub_unresolved_crawler` 的 legacy supplement；
3. `letpub_life_med_unique.json` 的基础目录；
4. `letpub_life_med_raw.json` 的普通历史原始记录。

`references/*.json` 只用于审计，不参与事实索引。同一身份、同一来源优先级存在多条记录时，只有明确的较新 `impact_factor_year` 可以覆盖旧记录；年份相同或缺失但 IF 数值冲突时，文章进入 `unresolved`，原因为 `conflict`。

PubMed 抓取提示词必须要求保留 `journal_issn`。ISSN 缺失时允许名称匹配，但必须记录匹配方法。

### IF 数据文件职责

- `letpub_life_med_unique.json`：只读基础目录。
- `letpub_life_med_raw.json`：兼容读取的历史原始数据，不再作为在线补抓写入目标。
- `letpub_manual_overrides.json`：在线补抓和人工确认的权威补充表。
- `references/<reference>.json`：任务审计记录，不作为“取最大值”的事实数据库。
- `if_unresolved_journals.json`：未解析期刊注册表，按稳定期刊身份维护 `files` 列表；重复处理同一文件不得增加观察次数。

现有 raw/reference 数据只做兼容读取。首次迁移必须生成冲突与重复报告，不静默删除原数据。

## 组件设计

### IF enrichment

保留 `scripts/sync_impact_factors.py` 作为单一入口，但把核心行为拆成可测试纯函数：构建索引、解析文章 IF、更新 unresolved、原子写回。

脚本接受一个或多个明确的数据文件。日常流水线只传当天主文件并只调用一次。无参数的 unresolved 补抓继续作为人工命令使用，不再由每日任务自动执行第二遍。

日常 enrichment 默认只使用本地 IF 数据；在线 unresolved 补抓由显式 `fetch.sh if` 工作流完成，以避免自动任务与技能要求的人工清理步骤冲突。普通本地未匹配记为 `no_match` 并保留文章；LetPub 索引无法加载、JSON 解析失败、索引结构非法等系统性错误必须让整个批次失败，不能降级为 `unresolved`。显式在线任务中的网络或 HTML 解析错误记录为 `lookup_error`，不得伪装成真实未命中。

### IF 过滤

新增一个小型纯过滤组件，输入文章列表和阈值 `6.0`，输出保留文章及统计：

- `available && impact_factor < 6`：删除；
- `available && impact_factor >= 6`：保留；
- `not_available_yet` 或 `unresolved`：保留并计入 unresolved 统计；
- 非法状态/数值组合：报错，不按未知项放行。

正式数据以整批临时目录发布，日志输出 removed/kept/unresolved 数量。重复运行结果必须相同。

### 数据校验

`validate_data.py` 增加阶段化校验：

- raw：现有 schema、日期、URL、唯一性；
- enriched：检查 IF 字段与状态组合；
- final：除 enriched 合同外，不允许残留 `available && IF < 6`。

文件名日期、顶层日期和每篇文章日期必须一致。Brain MRI 与疾病文件的 category 必须符合领域。

### 疾病分流与 digest

疾病匹配只使用 `title` 和 `summary`，避免期刊名触发假阳性。多疾病文章仍复制到每个命中疾病文件；未命中疾病的文章保留在 Brain MRI。

六个文件分别生成嵌入式顶层 `digest`。每个 digest 只接收对应文件最终过滤后的文章；`digest.stats.total == len(articles)`，推荐 URL 必须是最终 articles URL 的子集，不能引用已过滤或其他领域的文章。

### 前端

删除浏览器侧 LetPub 全库加载和索引。卡片与 digest 推荐直接读取文章的 `impact_factor*` 字段，并将机器状态映射为中文。

前端不重复执行业务过滤。历史收藏若缺 IF 字段，显示为未知，不静默删除。

### 本地服务器与运行脚本

- 静态路径解析必须限制在 `WEB_DIR` 或 `DATA_DIR` 内，拒绝 `..`、编码穿越和符号链接越界。
- 默认只监听 `127.0.0.1`。
- 抓取 mode 使用明确白名单，请求体设置上限。
- 若保留抓取/SSE API，限制本地 Origin，并清理完成任务的内存状态。
- 安装脚本采用健康检查，不以端口占用等同于服务正常。
- launchd 使用安装时解析到的 Codex 绝对路径。

## 历史数据迁移

历史迁移分两步：

1. dry-run：只扫描文件名严格匹配 `YYYY-MM-DD-(brainmri|autism|depression|adhd|ad|pd).json` 的文章文件，报告可匹配、低于 6、未知、冲突及预计删除数量，不改文件；同时报告“按文件出现次数”和“按 URL 去重后的唯一文章数”，避免疾病复制导致误读。
2. apply：只有用户确认报告后才执行原子批量回填与过滤。

当前 unresolved 的 `seen_count` 已受重复运行污染，迁移时从实际文件重新计算，不沿用为权威频数。

## 测试策略

所有行为修改采用 TDD：先写失败测试并确认失败原因，再写最小实现。

必须覆盖：

- ISSN、全名、简称匹配以及冲突处理；
- 来源优先级以及同优先级、无可比较年份时的冲突降级；
- 抓取输出契约与离线流水线 fixture 必须证明 `journal_issn` 从上游进入文章并贯穿 enrichment、过滤和分流；
- IF 字段真实写回和写后读回；
- `5.999` 删除、`6.0` 保留、未知保留；
- 非法 IF 合同失败；
- 重复运行幂等；
- IF/filter 失败阻断 digest 与 Git；
- 系统性 IF 索引/解析故障必须阻断批次，单篇 `no_match` 则保留为 `unresolved`；
- 日期一致性和疾病分流输入边界；
- digest total 与最终 articles 数量相等，推荐 URL 是最终文章 URL 的子集；
- 前端不再请求 `/data/letpub/*`；
- HTTP 路径穿越被拒绝且仅 loopback 监听；
- 发布前失败保持旧批次不变；发布中断造成的 `batch_id` 不一致不会被 API/前端展示；
- 历史迁移 dry-run 不修改任何文件。

## 分阶段实施

### 阶段 1：数据正确性

修复 IF 写回、保留 ISSN、增加 IF 过滤、单次 enrichment、阶段化校验与核心测试。

### 阶段 2：消费与安全

前端改读文章 IF，移除 LetPub 大文件加载；修复路径穿越、监听地址和 API 白名单。

### 阶段 3：流水线与运行可靠性

收紧日期/分流/digest 契约，统一安装与 launchd 行为，增加离线 shell 集成测试。

### 阶段 4：迁移与文档

提供历史 dry-run 报告工具，更新 README、项目 skill 和测试命令。历史 apply 等待用户对报告的单独确认。

## 非目标

- 本轮不自动删除历史数据。
- 不更换 LetPub 数据源，也不虚构 JCR 年份。
- 不重新设计页面视觉样式。
- 不加入数据库、框架或云部署系统。
