# Search Query Templates

针对工具应用、开源项目、硬核论文和技术圈讨论的搜索查询模板。

## 日期格式

动态插入当前日期：
- **今天**: `[current_date]` (e.g., 2026-02-18)
- **昨天**: `[current_date - 1 day]` (e.g., 2026-02-17)
- **本周**: `[current_date - 7 days]`
- **本月**: `[current_date - 30 days]`

---

## 一、🔥 工具与开源项目（最高优先级）

### GitHub 新项目搜索

```
"open source AI" OR "new AI tool" OR "just released" GitHub after:[yesterday]
```

```
site:github.com "ai" OR "llm" OR "machine learning" stars after:[yesterday]
```

```
GitHub "new release" AI model OR framework after:[yesterday]
```

### Hugging Face Spaces 搜索（WebSearch 补充）

```
site:huggingface.co/spaces "new" OR "trending" AI after:[yesterday]
```

```
"huggingface spaces" new demo OR tool OR app after:[yesterday]
```

### AI 框架与 API 更新

```
"AI framework" OR "LLM framework" release OR update after:[yesterday]
```

```
"open source LLM" OR "AI API" release OR launch after:[yesterday]
```

```
"PyTorch" OR "JAX" OR "transformers" new release after:[week_ago]
```

### 新模型发布（工具视角）

```
"model release" OR "new model" open source LLM after:[yesterday]
```

```
"fine-tuning" OR "LoRA" OR "GGUF" new model release after:[yesterday]
```

---

## 二、🔬 硬核科研与论文

### Hugging Face Papers 搜索（WebSearch 补充）

```
site:huggingface.co/papers trending after:[yesterday]
```

```
"huggingface papers" trending OR popular after:[yesterday]
```

### arXiv 最新论文

```
arXiv "cs.AI" OR "cs.LG" OR "cs.CL" paper after:[yesterday]
```

```
arXiv "cs.CV" OR "cs.RO" machine learning after:[yesterday]
```

```
arXiv preprint "large language model" OR "transformer" after:[yesterday]
```

### 技术突破搜索

```
"AI breakthrough" OR "machine learning breakthrough" research after:[yesterday]
```

```
"SOTA" OR "state-of-the-art" AI paper benchmark after:[yesterday]
```

```
"NeurIPS 2025" OR "ICML 2025" OR "ICLR 2025" paper
```

### 有代码实现的论文

```
"paper with code" OR "code available" AI research after:[yesterday]
```

```
arXiv "implementation" OR "code released" AI model after:[yesterday]
```

---

## 三、🗣️ Twitter/X 技术圈讨论

### 技术博主新项目发布

```
site:twitter.com OR site:x.com "just released" OR "new project" AI after:[yesterday]
```

```
"twitter" OR "x.com" developer "open source" AI project after:[yesterday]
```

### 工具/模型实测讨论

```
site:twitter.com OR site:x.com AI tool "tested" OR "tried" OR "benchmark" after:[yesterday]
```

```
"twitter" "AI" "demo" OR "playground" new after:[yesterday]
```

### 技术争论与热点

```
site:twitter.com OR site:x.com AI researcher "vs" OR "compared" OR "better than" after:[yesterday]
```

```
"twitter" OR "x.com" "AI" "hot take" OR "unpopular opinion" OR "thread" after:[yesterday]
```

### 论文讨论

```
site:twitter.com OR site:x.com arXiv paper "interesting" OR "breakthrough" after:[yesterday]
```

```
"twitter" "paper" "hugging face" OR "arxiv" AI researcher reaction after:[yesterday]
```

---

## 四、通用 AI 新闻补充

### 快速通用搜索

```
"AI news today" OR "artificial intelligence announcement" after:[yesterday]
```

```
"latest AI developments" OR "AI advancement" after:[yesterday]
```

### 主要模型更新

```
"OpenAI announcement" OR "GPT update" OR "ChatGPT news" after:[yesterday]
```

```
"Google AI announcement" OR "Gemini update" after:[yesterday]
```

```
"Anthropic news" OR "Claude update" after:[yesterday]
```

```
"Meta AI" OR "LLaMA update" after:[yesterday]
```

---

## 五、已移除的查询类别（不再使用）

以下类别已从日常搜索中移除：

- ~~AI 融资/投资查询~~ (e.g., "AI startup funding")
- ~~AI 并购查询~~ (e.g., "AI acquisition")
- ~~AI 政策/法规查询~~ (e.g., "AI regulation", "AI policy")
- ~~AI 伦理讨论查询~~ (e.g., "AI ethics", "AI safety debate")
- ~~市场分析查询~~ (e.g., "AI market trends", "AI industry analysis")

---

## 推荐查询组合

### 标准日报（5条查询）

```
Query 1 [工具]: "open source AI" OR "new AI tool" OR "just released" GitHub after:[yesterday]
Query 2 [HF论文]: site:huggingface.co/papers trending OR "huggingface papers" popular after:[yesterday]
Query 3 [arXiv]: arXiv "cs.AI" OR "cs.LG" OR "cs.CL" paper after:[yesterday]
Query 4 [Twitter工具]: site:twitter.com OR site:x.com "just released" OR "new project" AI after:[yesterday]
Query 5 [Twitter讨论]: site:twitter.com OR site:x.com AI tool "tested" OR "tried" after:[yesterday]
```

### 聚焦工具（3条查询）

```
Query 1: "open source AI" OR "AI tool release" OR "new LLM" GitHub after:[yesterday]
Query 2: site:huggingface.co/spaces "new" OR "trending" AI after:[yesterday]
Query 3: site:twitter.com OR site:x.com "just released" "open source" AI after:[yesterday]
```

### 聚焦论文（3条查询）

```
Query 1: site:huggingface.co/papers trending after:[yesterday]
Query 2: arXiv "cs.AI" OR "cs.LG" paper after:[yesterday]
Query 3: "paper with code" OR "code released" AI research after:[yesterday]
```

### 聚焦技术圈讨论（3条查询）

```
Query 1: site:twitter.com OR site:x.com AI researcher "new project" OR "just shipped" after:[yesterday]
Query 2: site:twitter.com OR site:x.com AI "tested" OR "benchmark" after:[yesterday]
Query 3: site:twitter.com OR site:x.com arXiv paper "interesting" after:[yesterday]
```

---

## 搜索优化技巧

### 1. 日期过滤
始终使用日期过滤确保内容新鲜：
- 日报: `after:[yesterday]`
- 周报: `after:[week_ago]`

### 2. 排除噪音
过滤无关内容：
```
"AI news" NOT "funding" NOT "acquisition" NOT "regulation" NOT "policy"
```

### 3. 优先一手内容
- `site:github.com` → 直接仓库
- `site:huggingface.co` → 直接模型/Space
- `site:arxiv.org` → 直接论文
- `site:twitter.com` → 直接讨论

### 4. 不要重复的词
- ❌ `"AI" AND "artificial intelligence"` (冗余)
- ✅ `"AI" OR "machine learning" OR "deep learning"` (互补)
