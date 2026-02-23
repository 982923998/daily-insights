# Reddit

**优先级**: 高（每次必抓）
**分类归属**: 🗣️ 技术圈舆论
**subcategory**: `Reddit`

---

## 抓取方式

Reddit 页面无法直接抓取，全部使用 WebSearch：

```
site:reddit.com/r/LocalLLaMA after:[昨天日期]
site:reddit.com/r/MachineLearning "new tool" OR "just released" OR "open source" after:[昨天日期]
site:reddit.com/r/LocalLLaMA "quantization" OR "fine-tuning" OR "inference" after:[昨天日期]
```

---

## 关注重点

- 本地部署、推理优化、量化方案
- 新模型权重发布
- 高票工程实践帖（社区热度指标）

## 失败处理

结果为空 → 扩大关键词，去掉 `after:` 限制，手动筛选日期
