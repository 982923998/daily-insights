---
name: daily-ai-news
description: "Aggregates and summarizes the latest AI news from multiple sources including AI news websites, Hugging Face, Twitter/X tech community, and web search. Focuses on tools, open-source projects, research papers, and tech community discussions. Activates when user asks for 'today's AI news', 'AI updates', 'latest AI developments', or mentions wanting a 'daily AI briefing'."
---

# Daily AI News Briefing

> 聚焦工具应用、开源项目、硬核论文与技术圈讨论，拒绝商业融资与政策法规噪音

## When to Use This Skill

Activate this skill when the user:
- Asks for today's AI news or latest AI developments
- Requests a daily AI briefing or updates
- Mentions wanting to know what's happening in AI
- Asks for AI tools, research papers, or tech community discussions
- Wants a summary of recent AI announcements
- Says: "给我今天的AI资讯" (Give me today's AI news)
- Says: "AI有什么新动态" (What's new in AI)
- Says: "有什么新工具/新项目" (Any new tools/projects)

## Workflow Overview

```
Phase 1: Information Gathering
  ├─ Hugging Face: Trending Papers + Trending Spaces (MANDATORY)
  ├─ GitHub Trending (MANDATORY)
  ├─ Twitter/X: 大佬账号定向监控 + 技术圈讨论 (MANDATORY)
  │   ├─ 重点账号: @karpathy @ylecun @simonw @AnthropicAI @OpenAI 等
  │   └─ 泛搜: 工具实测、好玩分享、论文讨论
  ├─ 主要 AI 公司发布专项搜索 (MANDATORY，防漏 Claude/GPT/Gemini 发布)
  └─ Web search (AI news sites + arXiv)
      ↓
Phase 2: Content Filtering
  ├─ Keep: Tools, open-source, research papers, tech discussions
  └─ Remove: Funding, acquisitions, policy, regulations, duplicates
      ↓
Phase 3: Categorization
  └─ Organize into 3 core categories
      ↓
Phase 4: Output Formatting
  └─ Present with links and structure
```

## Phase 1: Information Gathering

### Step 1.1: 【必须】抓取 Hugging Face 热榜

使用 `mcp__web_reader__webReader` 强制抓取以下两个页面：

**Hugging Face Trending Papers**:
- URL: https://huggingface.co/papers
- 重点: 当日/本周 trending 论文标题、点赞数、摘要
- 关注: 有开源代码的论文优先

**Hugging Face Trending Spaces**:
- URL: https://huggingface.co/spaces
- 重点: 热门 Demo Spaces，特别是新发布的工具类 Space
- 关注: likes 数量、是否可直接使用

### Step 1.2: 【必须】抓取 GitHub Trending 日榜前3

使用 `mcp__web_reader__webReader` 抓取：

**GitHub Trending (AI相关)**:
- URL: https://github.com/trending?since=daily&spoken_language_code=
- **重点**: 只取日榜 star 增长最快的前3个 AI/ML 仓库，必须收录
- **筛选条件**: 与 LLM、AI、ML、深度学习相关；若前3中有非 AI 项目，顺延取下一个 AI 项目补足3条
- **必须记录**: 仓库名、star 数、今日新增 star 数、一句话描述

### Step 1.3: 【必须】监控 Twitter/X 大佬账号 + 技术讨论

使用 `WebSearch` 分两步执行，不可跳过：

**第一步：定向搜索重点账号**（每次必执行，防漏第一手发布）

研究者 / 科学家账号：
```
site:twitter.com/karpathy after:[yesterday]
site:twitter.com/ylecun after:[yesterday]
site:twitter.com/emollick AI after:[yesterday]
```

开发者 / 从业者账号：
```
site:twitter.com/simonw AI OR LLM after:[yesterday]
site:twitter.com/goodside after:[yesterday]
```

AI 公司官方账号（**最重要**，防止漏抓 Claude/GPT/Gemini 发布）：
```
site:twitter.com/AnthropicAI after:[yesterday]
site:twitter.com/OpenAI after:[yesterday]
site:twitter.com/huggingface after:[yesterday]
site:twitter.com/MistralAI after:[yesterday]
```

**第二步：泛搜技术圈讨论 + 好玩分享**

```
site:twitter.com OR site:x.com "just released" OR "new project" AI after:[yesterday]
```

```
site:twitter.com OR site:x.com AI "fun" OR "trick" OR "interesting" demo after:[yesterday]
```

```
"twitter" OR "x.com" AI tool "tested" OR "tried" OR "benchmark" after:[yesterday]
```

**重点关注内容**：
- 研究员/开发者发布新开源项目（第一手）
- 从业者分享技术实测结果和 benchmark
- 好玩的 LLM 实验、prompt 技巧、有趣的 demo
- 技术圈对新论文/工具的集体讨论
- 非官方媒体的第一手体验反馈

完整账号列表见 `references/news_sources.md` 中"Twitter/X 重点大佬账号"部分。

### Step 1.4: 抓取主要 AI 新闻站点

使用 `mcp__web_reader__webReader` 抓取 2-3 个新闻源（辅助，非主要）：

**推荐来源**（每次选2-3个）：
- The Verge AI: https://www.theverge.com/ai-artificial-intelligence
- MIT Technology Review AI: https://www.technologyreview.com/topic/artificial-intelligence/
- Papers with Code: https://paperswithcode.com/

### Step 1.5: 执行 Web 搜索补充

**【必须】主要 AI 公司发布专项搜索**（防漏 Claude/GPT/Gemini 等重大发布）：

```
"Anthropic" OR "Claude" release OR announcement after:[yesterday]
```

```
"OpenAI" OR "GPT" OR "ChatGPT" release OR update after:[yesterday]
```

```
"Google AI" OR "Gemini" OR "DeepMind" release after:[yesterday]
```

```
"Meta AI" OR "LLaMA" OR "Mistral" release after:[yesterday]
```

**工具与开源项目**：
```
"open source AI" OR "AI tool release" OR "new LLM" GitHub after:[yesterday]
```

**硬核论文**：
```
arXiv "cs.AI" OR "cs.LG" OR "cs.CL" paper after:[yesterday]
```

```
"Hugging Face" paper OR model release after:[yesterday]
```

**技术社区热点**：
```
AI developer community "new project" OR "just shipped" OR "released today" after:[yesterday]
```

## Phase 2: Content Filtering

### 保留标准（Keep）

**高优先级**：
- 🔥 新开源项目、GitHub 热门仓库（AI/ML 相关）
- 🔥 Hugging Face Trending Spaces 上的新工具 Demo
- 🔥 实用 AI 工具、框架、API 发布
- 🔬 Hugging Face Trending Papers（有代码实现优先）
- 🔬 arXiv 近期高关注度论文
- 🗣️ 技术博主在 Twitter/X 上的深度讨论、技术测评、项目发布

**中优先级**：
- 主要模型更新（GPT、Claude、Gemini 等能力变化）
- 技术社区的集体讨论热点

### 过滤标准（Remove，硬性排除）

- ❌ **融资/收购新闻**：任何融资轮次、并购、投资相关内容
- ❌ **合作/战略协议**：企业间合作声明、战略合作协议（如"X公司与Y公司达成合作"），除非含有实质性技术发布
- ❌ **政策/法规新闻**：AI 监管、政府政策、伦理讨论（宏观层面）
- ❌ **市场分析**：行业分析报告、市场规模预测
- ❌ **PR 通稿**：官方公关稿件（除非包含实质性技术内容）
- ❌ **重复内容**：同一新闻多个来源，只保留最完整的版本
- ❌ **3天以上的旧内容**（除非极度重要）

### 去重策略

相同故事出现在多个来源时：
- 优先保留有技术细节的版本
- 优先保留有 GitHub/demo 链接的版本
- 公司博客 > 新闻聚合器

## Phase 3: Categorization

将内容整理为以下**3个核心类别**（按优先级排列）：

### 🔥 热门工具与开源项目

**内容范围**：
- GitHub 新发布/趋势 AI 仓库
- Hugging Face Trending Spaces（新工具 Demo）
- 实用 AI 框架、API、插件更新
- 开发者社区热议的新项目

**评判标准**：可以立刻动手用的工具或项目

### 🔬 硬核科研与论文

**内容范围**：
- Hugging Face Trending Papers
- arXiv 近期高关注论文
- 有重大突破的研究成果（新架构、新方法、SOTA结果）
- 有配套代码/实现的论文优先

**评判标准**：技术上有实质性进展，而非综述或进展报告

### 🗣️ 技术圈舆论

**内容范围**：
- Twitter/X 上技术博主的深度讨论
- 开发者对新发布工具/模型的实测反馈
- 技术社区的集体观点与争论
- 值得关注的新项目作者第一手介绍

**评判标准**：来自真实从业者的第一手观点，而非媒体转述

## Phase 4: Output Formatting

使用以下模板保持输出一致性：

```markdown
# 🤖 AI 技术日报

**日期**: [当前日期，例如 2026年2月18日]
**信息来源**: HuggingFace · GitHub · Twitter/X · [X] 篇文章
**覆盖时段**: 最近 24 小时

---

## 🔥 热门工具与开源项目

### [项目/工具名称]

**一句话**: [最简洁的功能描述]

**核心亮点**:
- [技术特点 1]
- [技术特点 2]
- [可用性/部署信息]

**为什么值得关注**: [1 句话说明实用价值]

📅 **来源**: [来源名称] • [发布日期]
🔗 **链接**: [原始链接]
💻 **GitHub/Demo**: [仓库或 Demo 链接（如有）]

---

### [项目/工具名称 2]

[同上格式]

---

## 🔬 硬核科研与论文

### [论文标题]

**一句话**: [核心贡献的最简描述]

**关键发现**:
- [技术贡献 1]
- [技术贡献 2]
- [基准测试结果（如有）]

**技术价值**: [为什么这篇论文值得读 - 1 句话]

📅 **来源**: [HuggingFace Papers / arXiv] • [日期]
🔗 **论文链接**: [URL]
💻 **代码**: [GitHub 链接（如有）]

---

### [论文标题 2]

[同上格式]

---

## 🗣️ 技术圈舆论

### [话题/讨论标题]

**核心观点**: [1-2 句话概括讨论的核心]

**技术社区在说什么**:
- [博主/开发者观点 1]
- [博主/开发者观点 2]
- [与之前技术的对比或争议点]

**值得关注的原因**: [1 句话说明为何这个讨论有价值]

📅 **来源**: Twitter/X • [日期]
🔗 **链接**: [URL（如有）]

---

### [话题 2]

[同上格式]

---

## 🎯 今日重点

1. **最值得动手试的**: [1 句话，指向具体工具]
2. **最值得深读的论文**: [1 句话，指向具体论文]
3. **技术圈最热的讨论**: [1 句话，概括讨论热点]

---

**生成时间**: [时间戳]
```

## Customization Options

提供初始简报后，可按以下方向定制：

### 1. 深度调整
"需要多详细？"
- **速览**: 仅标题 + 一句话描述
- **标准**: 关键点 + 来源链接（默认）
- **深度**: 技术细节 + 社区反应分析

### 2. 时间范围
"看多久的内容？"
- 最近 24 小时（默认）
- 最近 3 天
- 最近一周

### 3. 类别聚焦
"只看某类？"
- 只看工具与开源项目
- 只看论文
- 只看技术社区讨论

## Follow-up Interactions

### User: "详细介绍一下 [项目X]"
**Action**: 使用 `mcp__web_reader__webReader` 抓取完整页面，提供详细介绍 + 技术分析

### User: "这篇论文讲的是什么？"
**Action**: 获取论文全文，提供中文详细摘要 + 关键贡献解析

### User: "Twitter 上怎么评价 [工具Y]？"
**Action**: 搜索相关讨论，汇总社区真实反馈

### User: "有没有类似的开源替代？"
**Action**: 搜索 GitHub 和 HuggingFace，对比相关项目

## Quality Standards

### Validation Checklist
- HuggingFace Trending Papers 和 Trending Spaces 已抓取
- GitHub Trending 已检索
- Twitter/X 技术博主讨论已搜索
- 所有链接有效可访问
- 无融资/收购/政策类内容（已过滤）
- 无重复故事
- 所有条目有时间戳（优先今日内容）
- 摘要准确（非臆造）
- 以 GitHub/Demo 链接为准，而非新闻聚合链接

### Error Handling
- `webReader` 失败 → 跳过该 URL，尝试下一个来源
- HuggingFace 无法访问 → 用 WebSearch 搜索 "huggingface trending papers today"
- GitHub Trending 无法访问 → 用 WebSearch 搜索 "github trending AI today"
- 搜索结果为空 → 扩大日期范围或换关键词
- 内容有付费墙 → 使用可用摘要并注明限制

## Examples

### Example 1: 标准请求

**User**: "给我今天的AI资讯"

**AI Response**:
[执行4阶段工作流，输出3个类别的 5-10 条内容，重点突出工具与开源项目]

---

### Example 2: 只看工具

**User**: "今天有什么新的AI工具？"

**AI Response**:
[聚焦 🔥 热门工具与开源项目 类别，从 GitHub Trending + HuggingFace Spaces 重点输出]

---

### Example 3: 只看论文

**User**: "HuggingFace 今天有什么热门论文？"

**AI Response**:
[聚焦 🔬 硬核科研与论文，重点抓取 HuggingFace Trending Papers]

---

### Example 4: 社区讨论

**User**: "技术圈最近在讨论什么？"

**AI Response**:
[聚焦 🗣️ 技术圈舆论，输出 Twitter/X 技术博主的热点讨论]

## Additional Resources

完整的数据源列表、搜索查询模板和输出格式模板，参见：
- `references/news_sources.md` - AI 数据源数据库（含 HuggingFace 和 Twitter/X）
- `references/search_queries.md` - 按类别的搜索查询模板
- `references/output_templates.md` - 可选输出格式模板
