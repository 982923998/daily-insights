# HuggingFace Trending Spaces

**优先级**: 辅助
**分类归属**: 🔥 热门工具与开源项目
**subcategory**: `HuggingFace Spaces`
**注意**: 仅抓 Spaces，不抓 Papers（论文已从内容范围中排除）

---

## 抓取方式

### WebSearch（优先，有日期过滤）

```
site:huggingface.co/spaces new OR trending AI after:[昨天日期]
"huggingface spaces" new demo OR tool OR app after:[昨天日期]
```

### 直接抓取（备用）

- **URL**: https://huggingface.co/spaces
- **方法**: `mcp__web_reader__webReader`
- ⚠️ **时效警告**: 页面显示的是全局热门，**不等于今日新增**。使用此方法时必须手动核查每个 Space 的创建/更新日期，排除超过 3 天的内容

---

## 筛选条件

- 有实际可用功能（工具类 Space，非纯展示）
- likes 数量高（社区认可度）
- 优先新发布的 Space
