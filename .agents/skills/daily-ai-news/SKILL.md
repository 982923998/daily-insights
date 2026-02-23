---
name: daily-ai-news
description: "Aggregates and summarizes the latest AI news from multiple sources including GitHub, Hacker News, Reddit, Twitter/X, Product Hunt, and web search. Focuses on tools, open-source projects, and tech community discussions. Activates when user asks for 'today's AI news', 'AI updates', 'latest AI developments', or mentions wanting a 'daily AI briefing'."
domain_id: ai
domain_label: AI News
domain_category: AI
domain_color: "#6366f1"
domain_icon: cpu
domain_order: 1
---

# Daily AI News Briefing

> 聚焦工具应用、开源项目与技术圈讨论，拒绝论文摘要、商业融资与政策法规噪音

## 工作流

```
Phase 0: 日期确认（必须最先执行）
    ↓
Phase 1: 信息抓取（按优先级）
    ↓
Phase 2: 过滤与去重
    ↓
Phase 3: 分类输出
```

---

## Phase 0: 日期确认（强制，不可跳过）

> ⚠️ 所有查询中的 `after:[昨天日期]` 是占位符。不替换 = 无日期过滤 = 返回任意时间的旧内容。

执行步骤：
1. 获取今天的实际日期（格式 `YYYY-MM-DD`）
2. 计算昨天日期（今天 -1 天）
3. 在开始抓取前，输出一行确认：`📅 今日: YYYY-MM-DD | 搜索过滤: after:YYYY-MM-DD`
4. 后续所有查询中，将 `after:[昨天日期]` 替换为 `after:YYYY-MM-DD`（昨天的真实日期）

示例（今天 2026-02-23）：
- 过滤参数: `after:2026-02-22`
- 查询: `site:reddit.com/r/LocalLLaMA after:2026-02-22`

---

## Phase 1: 信息抓取

**执行顺序很重要**：先用 webReader 抓确定性最高的页面，再用 WebSearch 补充其余来源。

### 第一批：直接抓取（webReader，结果最稳定）

| 顺序 | 来源 | 分类 | 详情 |
|------|------|------|------|
| 1 | GitHub Trending 日榜 | 🔥 工具/开源 | `sources/github.md` |
| 2 | Hacker News Show HN | 🔥 工具/开源 | `sources/hackernews.md` |

### 第二批：WebSearch 补充（按优先级）

| 优先级 | 来源 | 分类 | 详情 |
|--------|------|------|------|
| 🔴 必须 | Reddit r/LocalLLaMA | 🗣️ 技术舆论 | `sources/reddit.md` |
| 🔴 必须 | 主要公司发布监控 | 🔥 工具/开源 | `sources/major-releases.md` |
| 🟡 辅助 | 技术博主博客 / Substack | 🗣️ 技术舆论 | `sources/tech-blogs.md` |
| 🟡 辅助 | GitHub Trending 周榜 | 🔥 工具/开源 | `sources/github.md` |
| 🟡 辅助 | HuggingFace Spaces | 🔥 工具/开源 | `sources/huggingface.md` |
| 🟡 辅助 | Product Hunt AI | 🔥 工具/开源 | `sources/producthunt.md` |
| 🟡 辅助 | AI for Science 工具 | 🔥 工具/开源 | `sources/ai-for-science.md` |

---

## Phase 2: 过滤与去重

### 2.1 日期校验（第一步，优先于其他过滤）

对每条候选内容：
- 确认实际发布日期（文章时间戳、commit 时间、帖子时间）
- 超过 **3 天**的内容直接丢弃（GitHub 周榜例外，标注"本周热门"）
- 发布日期不明确的内容，不得标注为"今日"

### 2.2 保留

- 可以立刻动手用的工具、框架、开源项目
- 主要模型发布（GPT、Claude、Gemini 等能力变化）
- 来自真实从业者的第一手技术讨论与实测

### 2.3 排除（硬性）

- ❌ 论文 / 学术研究结果（arXiv、HuggingFace Papers 等）
- ❌ 融资 / 收购 / 战略合作声明
- ❌ 政策 / 法规 / 伦理讨论
- ❌ 市场分析 / PR 通稿
- ❌ 重复内容（同一故事只保留最完整版本，优先有 GitHub/Demo 链接的版本）

---

## Phase 3: 分类输出

将内容整理为两个类别，每条必须标注 subcategory（取值见 `sources/output.md`）：

**🔥 热门工具与开源项目** — 可以立刻动手用的工具或项目

**🗣️ 技术圈舆论** — 来自真实从业者的第一手观点（非媒体转述）

输出格式见 `sources/output.md`，默认使用标准格式。

---

## 错误处理

| 情况 | 处理方式 |
|------|----------|
| webReader 失败 | 跳过该 URL，用 WebSearch 替代 |
| GitHub Trending 无法访问 | WebSearch: `github trending AI today` |
| HN 无法访问 | 仅用 WebSearch 补充查询 |
| 搜索结果为空 | 去掉 `after:` 限制，手动筛选日期 |

---

## 定制选项

用户可在初始简报后请求：
- **速览 / 深度**: 调整详细程度（模板见 `sources/output.md`）
- **时间范围**: 默认 24 小时，可调整为 3 天 / 1 周
- **只看某类**: 仅工具与开源 / 仅 GitHub / 仅技术讨论
