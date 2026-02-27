#!/bin/bash
# 抓取配置：模型与提示词模板统一维护

# 可用示例：gpt-5.3-codex、gpt-5-codex、gpt-5
MODEL_ID="${MODEL_ID:-gpt-5.3-codex}"

# 可选：指定 Codex provider（默认留空，使用你本机 codex 的默认 provider）
CODEX_PROVIDER="${CODEX_PROVIDER:-}"

# 抓取完成后自动提交并推送 data/ 到 GitHub（1=开启，0=关闭）
AUTO_GIT_SYNC="${AUTO_GIT_SYNC:-1}"

# 单次 codex 抓取超时（秒）。默认 600（10 分钟），设为 0 表示不限制。
CODEX_TIMEOUT_SECONDS="${CODEX_TIMEOUT_SECONDS:-600}"

AI_PROMPT_TEMPLATE='你必须严格执行 daily-ai-news 技能工作流，路径如下：
- 技能文件：__AI_SKILL_PATH__
- 来源目录：__AI_SOURCES_DIR__
- 输出规范：__AI_OUTPUT_SPEC_PATH__

强制步骤（不得跳过）：
1. 先读取 __AI_SKILL_PATH__，按其中 Phase 0/1/2/3 顺序执行。
2. 至少读取并遵循这些来源规则文件：github.md、hackernews.md、reddit.md、major-releases.md、output.md。
3. 按技能中的日期确认、过滤与去重规则处理候选内容。
4. 抓取范围为最近 3 天（含 __TODAY__）。

执行限制（必须遵守）：
1. 禁止开启子任务/子代理，不要做额外规划，直接执行抓取。
2. 禁止扫描仓库、禁止读取历史 data 文件；除技能文件与来源文件外，不读其他本地文件。
3. 最多执行 8 次外部请求（Web Search + WebFetch + curl 总和）。
4. 优先使用结构化来源：OpenAI RSS、Google AI RSS、HN Algolia API、Reddit JSON、Anthropic News。
5. 搜索结束后必须立即写文件并结束，不要无限重试、不要停在提问阶段。
6. 必须在单次运行超时前写出结果文件。
7. 若结果不足，允许输出较少条目；若完全无结果，写空数组。

输出要求（必须遵守）：
1. 必须直接写入 "__DATA_FILE__"（UTF-8 JSON，不要只在对话输出）。
2. 若文件已存在，先读取后合并并按 title 去重；若不存在则直接新建。
3. 每条 AI 文章必须包含：title、summary、url、category、subcategory、published_date、date；summary 不得为空。
4. category 固定为 "AI"；published_date 为 YYYY-MM-DD 格式真实发布日期（最近 3 天内）。
5. subcategory 取值范围：GitHub Trending / HN Show HN / HuggingFace Spaces / Product Hunt / Major Release / Twitter/X / Reddit / AI for Science。
6. 顶层结构固定：{"date":"__TODAY__","articles":[...]}。
'

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

TEST_PROMPT_TEMPLATE='Create a JSON file at "__DATA_FILE__" and exit immediately.
Required exact structure:
{
  "date":"__TODAY__",
  "articles":[
    {
      "title":"DeepMind Testing",
      "summary":"Dummy entry for pipeline validation.",
      "url":"https://example.com/deepmind-testing",
      "category":"AI",
      "subcategory":"Major Release",
      "published_date":"__TODAY__",
      "date":"__TODAY__"
    }
  ]
}
Do not include extra fields. Write valid UTF-8 JSON only.'
