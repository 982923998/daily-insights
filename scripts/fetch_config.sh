#!/bin/bash
# 抓取配置：模型与提示词模板统一维护

# 可用示例：opencode/kimi-k2.5-free, opencode/glm-5-free, google/gemini-2.0-flash
MODEL_ID="opencode/kimi-k2.5-free"

AI_PROMPT_TEMPLATE='请使用 daily-ai-news 技能，检索今日（__TODAY__）AI 资讯。
检索式中包含今天日期，例如："AI news __TODAY__"。

只做这几件事：
1. 必须用 Write 工具把结果写入 "__DATA_FILE__"（不要只在对话输出）。
2. 若文件已存在，先 Read，再合并并按 title 去重。
3. 每条 AI 文章必须包含：title、summary、url、category、published_date、date。
4. category 固定为 "AI"；published_date 为 YYYY-MM-DD 格式真实发布日期。
5. 顶层结构固定：{"date":"__TODAY__","articles":[...]}。
'

AUTISM_PROMPT_TEMPLATE='你的任务分两步，缺一不可：

第一步：用 pubmed-search 和 arxiv-search 技能检索当天 Autism/ASD 资讯。

【重要】pubmed-search 必须通过 filter-by-date 过滤，只保留今天（__TODAY__）发布的文章。
操作步骤如下：

1. 定位脚本路径（用 Bash 执行）：
   PUBMED_SCRIPT=$(find ~/.claude/plugins/cache -name "search" -path "*/pubmed-search/*/scripts/*" -type f 2>/dev/null | head -1)
   FILTER_SCRIPT=$(find ~/.claude/plugins/cache -name "filter-by-date" -path "*/pubmed-search/*/scripts/*" -type f 2>/dev/null | head -1)

2. 执行搜索并过滤（只保留最近3天发布的文章，days=3）：
   $PUBMED_SCRIPT "autism ASD" 20 | $FILTER_SCRIPT 3

3. 使用 arxiv-search 技能搜索（不过滤，由你根据 published_date 字段判断是否为今日）：
   arxiv-search: "autism spectrum disorder __TODAY__"

pubmed filter-by-date 返回的 JSON 中，kept 文章在 results 字段，filtered_out 字段为被过滤掉的旧文章，忽略 filtered_out。

第二步（必须完成）：用 Write 工具把结果写入文件 "__DATA_FILE__"。
- 只写入 published_date 在最近3天内的文章
- 顶层结构：{"date":"__TODAY__","articles":[...]}
- 每条文章字段：title、summary、url、category、source、published_date、date
- category 固定为 "Autism"；published_date 为 YYYY-MM-DD 格式真实发布日期
- 若文件已存在，先 Read 后合并去重再写入
- 若当天无文章，写入 {"date":"__TODAY__","articles":[]}

不写文件=任务失败。
'

TEST_PROMPT_TEMPLATE='Create a JSON file at "__DATA_FILE__" with one dummy AI article about "DeepMind Testing". Use the Write tool immediately.'
