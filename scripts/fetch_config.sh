#!/bin/bash
# 抓取配置：模型与提示词模板统一维护

# 可用示例：opencode/kimi-k2.5-free, opencode/glm-5-free,  minimax-m2.5-free, big pickle
MODEL_ID="opencode/minimax-m2.5-free"

# 抓取完成后自动提交并推送 data/ 到 GitHub（1=开启，0=关闭）
AUTO_GIT_SYNC="1"

AI_PROMPT_TEMPLATE='请使用 daily-ai-news 技能，检索今日（__TODAY__）AI 资讯。
检索式中包含今天日期，例如："AI news __TODAY__"。

只做这几件事：
1. 必须用 Write 工具把结果写入 "__DATA_FILE__"（不要只在对话输出）。
2. 若文件已存在，先 Read，再合并并按 title 去重。
3. 每条 AI 文章必须包含：title、summary、url、category、subcategory、published_date、date。
4. category 固定为 "AI"；published_date 为 YYYY-MM-DD 格式真实发布日期。
5. subcategory 根据来源填写，取值范围：GitHub Trending / HN Show HN / HuggingFace Spaces / Product Hunt / Major Release / Twitter/X / Reddit / AI for Science。
6. 顶层结构固定：{"date":"__TODAY__","articles":[...]}。
'

ACADEMIC_PROMPT_TEMPLATE='你的任务是检索 __DOMAIN_LABEL__ 领域的学术论文（今天：__TODAY__）。

必须先读取领域配置文件，严格按照文件中规定的检索方法、查询词、API 和过滤规则执行：
__DOMAIN_CONFIG_PATH__

配置文件中的每条检索步骤都必须执行，不得跳过或替换为其他方法。
**禁止调用任何 skill（pubmed-search、arxiv-search 等），必须直接用 Bash/curl 按配置文件中的 API 步骤执行。**

完成检索后，用 Write 工具将结果写入 "__DATA_FILE__"：
- 顶层结构：{"date":"__TODAY__","articles":[...]}
- 每条文章：title、summary、url、category、source、journal、published_date、date
- category 固定为 "__CATEGORY__"；published_date 为 YYYY-MM-DD 格式；journal 为期刊名称（没有则空字符串）
- 若文件已存在，先 Read 后合并去重再写入
- 若当天无文章，写入 {"date":"__TODAY__","articles":[]}

不写文件 = 任务失败。
'

TEST_PROMPT_TEMPLATE='Create a JSON file at "__DATA_FILE__" with one dummy AI article about "DeepMind Testing". Use the Write tool immediately.'
