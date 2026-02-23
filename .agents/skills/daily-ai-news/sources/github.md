# GitHub Trending

**优先级**: 最高（每次必抓）
**分类归属**: 🔥 热门工具与开源项目
**subcategory**: `GitHub Trending`

---

## 抓取方式

### 日榜（必须）

- **URL**: https://github.com/trending?since=daily
- **方法**: `mcp__web_reader__webReader`
- **取**: 日增 star 最快的前 5 个 AI/ML 仓库（非 AI 项目顺延跳过）
- **记录**: 仓库名、star 总数、今日新增 star、一句话描述、链接

### 周榜（补充）

- **URL**: https://github.com/trending?since=weekly
- **方法**: `mcp__web_reader__webReader`
- **取**: 1-2 个日榜未覆盖的 AI/ML 亮点
- ⚠️ **时效**: 周榜覆盖**过去 7 天**，输出时必须标注 `本周热门`，不得标注为今日

### 专项补充（WebSearch）

```
site:github.com "AI agent" OR "LLM agent" stars released after:[昨天日期]
site:github.com "inference" OR "quantization" OR "fine-tuning" LLM after:[昨天日期]
site:github.com "AI tool" OR "CLI" OR "plugin" LLM after:[昨天日期]
```

---

## 筛选条件

- 与 LLM、AI、ML、Agent、深度学习相关
- 非 AI 项目跳过，顺延取下一个
- 日榜已有的仓库，周榜不重复收录

## 失败处理

GitHub Trending 无法访问 → WebSearch: `github trending AI today`
