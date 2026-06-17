# Cursor Automations 挖词自动化流程

> 仓库：`ai-keyword-research`
> 目标：每天自动执行60分钟挖词流程，早上起来直接看结果

---

## 目录

- [整体架构](#整体架构)
- [文件结构](#文件结构)
- [模型选择建议](#模型选择建议)
- [Agent 1：每日扫新词](#agent-1每日扫新词)
- [Agent 2：趋势打标 + 竞争初筛](#agent-2趋势打标--竞争初筛)
- [Agent 3：找抱怨](#agent-3找抱怨)
- [Agent 4：最终打分 + 入池](#agent-4最终打分--入池)
- [配置步骤](#配置步骤)

---

## 整体架构

```
07:00 → Agent 1：扫新词（HF / Product Hunt / arXiv）
07:30 → Agent 2：趋势打标 + 竞争初判
08:00 → Agent 3：找抱怨，聚合痛点
09:00 → Agent 4：6维打分 → ≥24分进验证池 → 写入仓库文件
```

---

## 文件结构

```
/keywords/
  ├── raw/
  │   ├── 2026-06-14.json
  │   ├── 2026-06-15.json
  │   └── 2026-06-16.json        # Agent 1 输出：每日新词原始数据
  ├── scored/
  │   ├── 2026-06-14.json
  │   └── ...                    # Agent 2 输出：趋势 + 竞争标签
  ├── pain/
  │   ├── 2026-06-14.json
  │   └── ...                    # Agent 3 输出：抱怨 + 痛点
  └── validated/
      ├── 2026-06-14.json
      └── ...                    # Agent 4 输出：验证池（总分 ≥ 24）
```

> 每天生成新文件，历史数据全部保留，方便跨周期对比分析。

---

## 模型选择建议

| Agent | 推荐模型 | 原因 |
|-------|---------|------|
| Agent 1 扫新词 | claude-sonnet | 效果好，联网抓取 |
| Agent 2 趋势+竞争 | claude-sonnet | 需要联网搜索 |
| Agent 3 找抱怨 | claude-sonnet | 长文本理解更强 |
| Agent 4 打分生成 | claude-sonnet | 需要推理能力 |

---

## Agent 1：每日扫新词

**Trigger**：每天定时 07:00 GMT+8

**Tools**：Memories + Tavily MCP

**Agent Instructions：**

```
你是一个 AI 工具词汇侦察员。每天执行以下任务：

1. 获取今天的日期，格式为 YYYY-MM-DD

2. 用 Tavily 搜索以下来源的今日最新内容：
   - Hugging Face Daily Papers: huggingface.co/papers
   - Product Hunt Today: producthunt.com
   - arXiv cs.AI/cs.LG 最新论文标题列表

3. 从内容中提取：
   - 新出现的 AI 模型名（如 Qwen3、Gemma3）
   - 新工具/产品名
   - 高频出现的技术词汇
   - 用户痛点相关词（含 "too expensive" "hard to" "wish" "finally" 等）

4. 去重，与昨日列表对比，只保留新增词汇

5. 将结果写入仓库 /keywords/raw/{今日日期}.json，例如 /keywords/raw/2026-06-17.json：
{
  "date": "2026-06-17",
  "new_terms": ["词1", "词2"],
  "source_breakdown": {"huggingface": [], "producthunt": [], "arxiv": []},
  "pain_signals": ["抱怨句子1", "抱怨句子2"]
}

6. 直接 commit 并 push 到 main 分支，不要开 PR

每次搜索之间间隔5秒，避免触发速率限制。
```

---

## Agent 2：趋势打标 + 竞争初筛

**Trigger**：每天定时 07:30 GMT+8

**Tools**：Memories + Tavily MCP

**Agent Instructions：**

```
读取仓库 /keywords/raw/{今日日期}.json 中今天的 new_terms 列表。

对每个词执行：

1. 【趋势判断】
   用 Tavily 搜索该词近30天热度变化，判断：
   - 📈 上升中
   - 📊 平稳
   - 📉 下降
   主要搜索国家是哪里（US/CN/IN 等）

2. 【竞争初判】
   用 Tavily 搜索该词，观察前10名结果：
   - 是否有专门工具站（非博客/论坛）
   - 页面质量：标题是否精准匹配、内容深度如何
   - 是否存在明显弱页（论坛帖、低质博客占据前排）
   判断竞争等级：低 / 中 / 高

3. 将结果写入仓库 /keywords/scored/{今日日期}.json：
{
  "date": "2026-06-17",
  "entries": [
    {
      "term": "xxx",
      "trend": "📈上升",
      "main_geo": "US",
      "competition": "低",
      "top10_quality": "弱，论坛为主"
    }
  ]
}

4. 直接 commit 并 push 到 main 分支，不要开 PR

每次搜索之间间隔5秒，避免触发速率限制。
```

---

## Agent 3：找抱怨

**Trigger**：每天定时 08:00 GMT+8

**Tools**：Memories + Tavily MCP

**Agent Instructions：**

```
读取仓库 /keywords/scored/{今日日期}.json，针对趋势为"上升"的词执行：

1. 用 Tavily 搜索以下组合：
   - "[词] site:reddit.com"
   - "[词] complaints OR frustrating OR broken"
   - "[词] alternative"
   - "[词] review site:producthunt.com"

2. 从结果中提取：
   - 用户反复提到的痛点（归纳为一句话）
   - 现有工具的缺陷描述
   - 用户正在用的"绕路方案"（workaround）
   - 用户希望存在的功能（"I wish", "why can't"）

3. 将结果写入仓库 /keywords/pain/{今日日期}.json：
{
  "date": "2026-06-17",
  "entries": [
    {
      "term": "xxx",
      "top_complaints": ["太贵", "不支持中文", "导出格式少"],
      "workarounds": ["用户用Excel手动处理"],
      "desired_features": ["批量处理", "API接入"]
    }
  ]
}

4. 直接 commit 并 push 到 main 分支，不要开 PR

每次搜索之间间隔5秒，避免触发速率限制。
```

---

## Agent 4：最终打分 + 入池

**Trigger**：每天定时 09:00 GMT+8

**Tools**：Memories

**Agent Instructions：**

```
读取仓库今日三个数据文件：
- /keywords/raw/{今日日期}.json
- /keywords/scored/{今日日期}.json
- /keywords/pain/{今日日期}.json

对每个词按以下6个维度各打 0-5 分：

维度定义：
- D1 趋势热度：📈上升=5，📊平稳=3，📉下降=1
- D2 竞争空间：低=5，中=3，高=1
- D3 痛点明确度：有3条以上具体抱怨=5，1-2条=3，无=0
- D4 工具可行性：纯信息类难做=1，可做小工具=3，标准SaaS形态=5
- D5 变现潜力：有明确付费场景=5，模糊=3，纯免费=1
- D6 差异化空间：现有方案明显有缺口=5，有改进空间=3，市场饱和=1

规则：
- 总分 ≥ 24：写入 /keywords/validated/{今日日期}.json，标记为"进入验证池"
- 总分 18-23：写入 /keywords/validated/{今日日期}.json，标记为"继续观察"
- 总分 < 18：丢弃

对"进入验证池"的词，额外生成：
- 一句话产品方向描述
- 建议的落地页标题（英文）
- 3个目标用户画像

输出示例：
{
  "date": "2026-06-17",
  "entries": [
    {
      "term": "AI meeting notes",
      "total_score": 26,
      "scores": {"D1": 5, "D2": 3, "D3": 5, "D4": 5, "D5": 5, "D6": 3},
      "status": "进入验证池",
      "product_direction": "面向独立开发者的轻量会议转录+行动项提取工具",
      "suggested_headline": "Turn Any Meeting Into Action Items in 30 Seconds",
      "target_users": ["远程团队PM", "独立顾问", "销售跟进场景"]
    }
  ]
}

直接 commit 并 push 到 main 分支，不要开 PR
```

---

## 配置步骤

1. **仓库准备**：在 `ai-keyword-research` 仓库根目录创建以下空文件夹（各放一个 `.gitkeep`）：
   - `/keywords/raw/`
   - `/keywords/scored/`
   - `/keywords/pain/`
   - `/keywords/validated/`

2. **依次配置4个 Automation**：
   - Repository 都选 `ai-keyword-research`，分支选 `main`
   - 粘贴对应的 Agent Instructions
   - 设置对应的定时 Trigger（07:00 / 07:30 / 08:00 / 09:00 GMT+8）

3. **Tools 配置**：
   - Agent 1/2/3：Tavily MCP + Memories
   - Agent 4：只保留 Memories

4. **验证**：手动触发一次 Agent 1，确认 `/keywords/raw/今日日期.json` 写入成功，再依次测试后续 Agent

---

## 历史数据价值

积累一个月后可以做的事：

| 分析 | 方法 |
|------|------|
| 哪些词持续上升 | 对比多天 validated/ 文件 |
| 哪些词从观察池升级 | 追踪"继续观察"词的评分变化 |
| 跨周期趋势 | 让 Agent 5 每周汇总一次 |

---

## 存储估算

每天约 26KB，一年约 9.5MB，GitHub 免费仓库（1GB上限）可用 **100年以上**，无需担心空间问题。
