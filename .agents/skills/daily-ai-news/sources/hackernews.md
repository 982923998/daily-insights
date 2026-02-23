# Hacker News — Show HN

**优先级**: 高（每次必抓）
**分类归属**: 🔥 热门工具与开源项目
**subcategory**: `HN Show HN`

---

## 抓取方式

### 直接抓取（优先）

- **URL**: https://news.ycombinator.com/show
- **方法**: `mcp__web_reader__webReader`
- **取**: 前 5 个 AI/ML 相关条目

### WebSearch 补充

```
site:news.ycombinator.com "Show HN" AI OR LLM after:[昨天日期]
site:news.ycombinator.com "Show HN" "open source" machine learning after:[昨天日期]
site:news.ycombinator.com "Show HN" research OR science OR lab AI after:[昨天日期]
```

---

## 筛选条件

- 优先: 有 GitHub 链接 或 可用 Demo
- 优先: 点赞数高（社区认可度指标）
- 跳过: 纯文章/讨论，无实际项目

## 失败处理

HN 无法访问 → 仅使用上方 WebSearch 补充查询
