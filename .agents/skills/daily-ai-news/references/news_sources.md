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

### 3. GitHub Trending (AI/ML)
- **URL**: https://github.com/trending?since=daily
- **抓取方式**: `mcp__web_reader__webReader`
- **重点内容**: 日榜 star 增长最快的仓库
- **筛选条件**: LLM、AI、ML、深度学习相关项目
- **类别归属**: 🔥 热门工具与开源项目

### 4. Twitter/X 技术博主讨论
- **抓取方式**: `WebSearch`（无法直接抓取 X 页面）
- **搜索策略**: 搜索技术博主的原创内容，而非媒体转述
- **重点关注**:
  - 研究员/开发者发布新开源项目
  - 从业者分享技术实测结果
  - 社区讨论新论文实现细节
  - 第一手的工具/模型体验反馈
- **类别归属**: 🗣️ 技术圈舆论

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

## Tier 3: 公司博客（重大发布时检查）

仅在有重大工具/模型发布时检查，日常可跳过。

### 1. OpenAI Blog
- **URL**: https://openai.com/blog
- **Best For**: GPT/ChatGPT 官方发布、API 更新

### 2. Google AI Blog
- **URL**: https://blog.google/technology/ai/
- **Best For**: Gemini 更新、Google AI 工具发布

### 3. DeepMind Blog
- **URL**: https://deepmind.google/discover/blog/
- **Best For**: 重大研究突破（AlphaFold 级别）

### 4. Anthropic News
- **URL**: https://www.anthropic.com/news
- **Best For**: Claude 功能更新

### 5. Meta AI Blog
- **URL**: https://ai.meta.com/blog/
- **Best For**: LLaMA 系列更新、开源发布

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
3. GitHub Trending → 🔥 开源项目
4. WebSearch: Twitter/X 技术讨论 → 🗣️ 舆论

辅助（选2个）:
5. Papers with Code → 🔬 论文补充
6. The Verge AI 或 MIT Tech Review → 工具/分析补充
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
