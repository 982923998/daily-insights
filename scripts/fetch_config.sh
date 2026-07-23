#!/bin/bash
# 抓取配置：模型与提示词模板统一维护

# 可用示例：gpt-5.4、gpt-5.3-codex、gpt-5.2-codex、gpt-5
MODEL_ID="${MODEL_ID:-gpt-5.4}"

# 当天抓取失败时的降级模型（空则不降级）
FALLBACK_MODEL_ID="${FALLBACK_MODEL_ID:-gpt-5.2-codex}"

# 指定 Codex provider。服务器全局配置可能指向过期中转，项目默认走 OpenAI。
CODEX_PROVIDER="${CODEX_PROVIDER:-openai}"

# 抓取完成后自动提交并推送 data/ 到 GitHub（1=开启，0=关闭）
AUTO_GIT_SYNC="${AUTO_GIT_SYNC:-1}"

# 单次 codex 抓取超时（秒）。默认 600（10 分钟），设为 0 表示不限制。
CODEX_TIMEOUT_SECONDS="${CODEX_TIMEOUT_SECONDS:-600}"

# codex 失败重试次数与重试间隔（秒）。
CODEX_RETRY_ATTEMPTS="${CODEX_RETRY_ATTEMPTS:-3}"
CODEX_RETRY_DELAY_SECONDS="${CODEX_RETRY_DELAY_SECONDS:-20}"

ACADEMIC_PROMPT_TEMPLATE='你的任务是检索 __DOMAIN_LABEL__ 领域的学术论文（今天：__TODAY__）。

你必须严格执行 academic-search 技能工作流，路径如下：
- 技能文件：__ACADEMIC_SKILL_PATH__
- 领域配置：__DOMAIN_CONFIG_PATH__

强制步骤（不得跳过）：
1. 先读取 __ACADEMIC_SKILL_PATH__，遵循技能中的通用流程和输出要求。
2. 再读取 __DOMAIN_CONFIG_PATH__，严格按其中检索方法、查询词、API 和过滤规则执行。
3. 配置文件中的每条检索步骤都必须执行，不得跳过或替换为其他方法。
4. 禁止开启子任务/子代理；必须直接用 Bash/curl 按配置步骤执行。

领域配置文件：
__DOMAIN_CONFIG_PATH__

完成检索后，直接写入 "__DATA_FILE__"：
- 顶层结构：{"date":"__TODAY__","articles":[...]}
- 每条文章：title、summary、url、category、source、journal、published_date、date（summary 不得为空）
- category 固定为 "__CATEGORY__"；published_date 为 YYYY-MM-DD 格式；journal 为期刊名称（没有则空字符串）
- 若某条记录没有 abstract，summary 必须填入可读回退文本：`No abstract available in source.`
- 若文件已存在，先读取后合并去重再写入
- 若当天无文章，写入 {"date":"__TODAY__","articles":[]}

不写文件 = 任务失败。
'
