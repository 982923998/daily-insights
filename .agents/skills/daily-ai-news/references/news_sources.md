# AI News Sources Database

按优先级排列的 AI 信息来源，聚焦工具应用、开源项目、硬核论文与技术圈讨论。

---

## Tier 1: 核心数据源（每次必抓）

### 1. Hugging Face Trending Papers
- **URL**: https://huggingface.co/papers
- **抓取方式**: `mcp__web_reader__webReader`
- **重点内容**: 当日/本周 trending 论文、点赞数、摘要
- **优先条件**: 有配套代码实现的论文
- **类别归属**: 🔬 硬核科研与论文

### 2. Hugging Face Trending Spaces
- **URL**: https://huggingface.co/spaces
- **抓取方式**: `mcp__web_reader__webReader`
- **重点内容**: 热门 Demo Spaces，特别是新发布的工具类 Space
- **优先条件**: likes 数量高、可直接使用的工具
- **类别归属**: 🔥 热门工具与开源项目

### 3. GitHub Trending (AI/ML) — 日榜前3
- **URL**: https://github.com/trending?since=daily
- **抓取方式**: `mcp__web_reader__webReader`
- **重点内容**: 日榜 star 增长最快的前3个 AI/ML 仓库（必须收录）
- **筛选条件**: 与 LLM、AI、ML、深度学习相关；非 AI 项目顺延跳过
- **必须记录**: 仓库名、star 数、今日新增 star 数、一句话描述
- **类别归属**: 🔥 热门工具与开源项目

### 4. Twitter/X 重点大佬账号
- **抓取方式**: `WebSearch`（无法直接抓取 X 页面，通过 Google 搜索 `site:twitter.com/用户名` 或 `"@用户名"` 来定向获取）
- **搜索策略**: 优先搜索以下具体账号的近期内容，再做泛搜
- **类别归属**: 🗣️ 技术圈舆论

#### 核心研究者 / 科学家

| 账号 | 姓名 | 为何关注 |
|------|------|----------|
| @karpathy | Andrej Karpathy | ex-OpenAI/Tesla，AI 教育与前沿实践，帖子质量极高 |
| @ylecun | Yann LeCun | Meta AI 首席科学家，常有争议性观点 |
| @drjimfan | Jim Fan | NVIDIA Research，具身智能 + 多模态前沿 |
| @emollick | Ethan Mollick | Wharton 教授，AI 实际用法研究，案例丰富 |
| @jeremyphoward | Jeremy Howard | fast.ai 创始人，实践派深度学习 |

#### 开发者 / 从业者

| 账号 | 姓名 | 为何关注 |
|------|------|----------|
| @simonw | Simon Willison | 大量 AI 工具实测，SQLite/LLM 工具链专家 |
| @swyx | swyx | AI 工程社区核心，latent.space 播客 |
| @hwchase17 | Harrison Chase | LangChain 创始人，Agent 框架最新进展 |
| @omarsar0 | Elvis Saravia | NLP/LLM 资讯整理，DAIR.AI |
| @abacaj | Anton Bacaj | 高效 LLM 推理与量化实践 |

#### AI 公司官方账号（必须主动检查）

| 账号 | 公司 | 为何关注 |
|------|------|----------|
| @AnthropicAI | Anthropic | Claude 系列发布第一手信息 |
| @OpenAI | OpenAI | GPT/ChatGPT 官方发布 |
| @huggingface | Hugging Face | 模型/数据集/Spaces 热点 |
| @GoogleDeepMind | Google DeepMind | Gemini/Research 发布 |
| @MetaAI | Meta AI | LLaMA 系列开源发布 |
| @MistralAI | Mistral AI | 开源模型发布 |
| @xai | xAI | Grok 系列更新 |

#### 好玩 / 技术分享型账号

| 账号 | 为何关注 |
|------|----------|
| @goodside | Riley Goodside，提示工程技巧、有趣 LLM 实验 |
| @theshawwn | Shawn Presser，各种脑洞大开的 AI 实验 |
| @m__dehghani | Mostafa Dehghani，视觉 Transformer 研究 |
| @danielnouri | Daniel Nouri，实用深度学习技巧 |

---

## Tier 2: 技术新闻站点（辅助来源）

### 1. Papers with Code
- **URL**: https://paperswithcode.com/
- **Update Frequency**: Daily
- **Focus Areas**: 有代码实现的研究论文、Trending 论文
- **Best For**: 找到可复现的研究成果
- **类别归属**: 🔬 硬核科研与论文

### 2. The Verge AI
- **URL**: https://www.theverge.com/ai-artificial-intelligence
- **Update Frequency**: Daily
- **Focus Areas**: 消费级 AI 产品、工具评测
- **Best For**: 工具实际使用体验报道
- **类别归属**: 🔥 热门工具与开源项目

### 3. MIT Technology Review AI
- **URL**: https://www.technologyreview.com/topic/artificial-intelligence/
- **Update Frequency**: Daily
- **Focus Areas**: 深度技术分析、研究突破
- **Best For**: 有深度的技术解读
- **类别归属**: 🔬 硬核科研与论文

---

## Tier 3: 公司博客（每次必检查，防漏重要发布）

以下公司博客**每次运行必须通过 WebSearch 检查是否有当日发布**，不可跳过。历史上多次漏抓正是因为跳过了这一步。

### 1. Anthropic News
- **URL**: https://www.anthropic.com/news
- **搜索词**: `"Anthropic" OR "Claude" announcement after:[yesterday]`
- **Best For**: Claude 模型发布（如 Claude Sonnet、Haiku 等）、API 更新

### 2. OpenAI Blog
- **URL**: https://openai.com/blog
- **搜索词**: `"OpenAI" OR "ChatGPT" OR "GPT" release after:[yesterday]`
- **Best For**: GPT/o 系列发布、ChatGPT 功能更新

### 3. Google AI / DeepMind Blog
- **URL**: https://blog.google/technology/ai/ 和 https://deepmind.google/discover/blog/
- **搜索词**: `"Google AI" OR "Gemini" OR "DeepMind" release after:[yesterday]`
- **Best For**: Gemini 系列更新、重大研究突破

### 4. Meta AI Blog
- **URL**: https://ai.meta.com/blog/
- **搜索词**: `"Meta AI" OR "LLaMA" release after:[yesterday]`
- **Best For**: LLaMA 系列开源发布

### 5. Mistral AI Blog
- **URL**: https://mistral.ai/news/
- **搜索词**: `"Mistral AI" OR "Mistral" model release after:[yesterday]`
- **Best For**: 开源模型发布

---

## Tier 4: 技术学习资源（按需）

### 1. KDnuggets
- **URL**: https://www.kdnuggets.com/
- **Focus Areas**: 数据科学、机器学习教程
- **Best For**: 技术实操教程

### 2. Towards Data Science
- **URL**: https://towardsdatascience.com/
- **Focus Areas**: ML 技术教程、实战指南
- **Best For**: 社区贡献的技术内容

### 3. Synced Review
- **URL**: https://syncedreview.com/
- **Focus Areas**: 中国 AI 新闻、技术深度报道
- **Best For**: 中国 AI 生态覆盖

---

## Source Selection Strategy

### 标准日报（推荐组合）

```
必抓（每次）:
1. HuggingFace Trending Papers → 🔬 论文
2. HuggingFace Trending Spaces → 🔥 工具
3. GitHub Trending 日榜前3 AI项目 → 🔥 开源项目（必须收录）
4. Twitter/X 大佬账号定向监控 → 🗣️ 舆论
5. 主要 AI 公司发布专项搜索 → 🔥/🔬（防漏 Claude/GPT/Gemini 等）

过滤（硬性排除）:
❌ 融资/收购/合作协议新闻
❌ 政策法规
❌ 无实质技术内容的 PR 通稿

辅助（选2个）:
6. Papers with Code → 🔬 论文补充
7. The Verge AI 或 MIT Tech Review → 工具/分析补充
```

### 聚焦工具模式

```
1. HuggingFace Trending Spaces
2. GitHub Trending
3. WebSearch: "new AI tool" OR "open source AI" GitHub after:[yesterday]
4. Twitter/X: 工具发布讨论
```

### 聚焦论文模式

```
1. HuggingFace Trending Papers
2. Papers with Code
3. WebSearch: arXiv "cs.AI" OR "cs.LG" after:[yesterday]
```

### 聚焦技术圈讨论模式

```
1. WebSearch: Twitter/X 技术博主近期内容
2. HuggingFace Papers（社区点赞高的）
3. GitHub Trending（看 README 和 Star 趋势）
```

---

## 已移除的来源（不再使用）

以下来源因聚焦商业融资或政策法规，已从日常工作流中移除：

- ~~VentureBeat AI~~ (融资/商业导向)
- ~~TechCrunch AI~~ (融资/收购为主)
- ~~AI News~~ (综合聚合，信噪比低)
- ~~AI Ethics Newsletter~~ (政策伦理导向)
- ~~AI Hub Today~~ (聚合器，质量参差)
