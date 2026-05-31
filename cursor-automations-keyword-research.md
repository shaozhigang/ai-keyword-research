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
- [Slack 通知配置](#slack-通知配置)
- [配置步骤](#配置步骤)

---

## 整体架构

```
07:00 → Agent 1：扫新词（HF / Product Hunt / arXiv）
07:30 → Agent 2：趋势打标 + 竞争初判
08:00 → Agent 3：找抱怨，聚合痛点
09:00 → Agent 4：6维打分 → ≥24分进验证池 → 推送 Slack
```

---

## 文件结构

```
/keywords/
  ├── daily_raw.json          # Agent 1 输出：今日新词原始数据
  ├── daily_scored.json       # Agent 2 输出：趋势 + 竞争标签
  ├── daily_pain.json         # Agent 3 输出：抱怨 + 痛点
  ├── pool_validated.json     # 验证池（总分 ≥ 24）
  └── pool_watch.json         # 观察池（总分 18-23）
```

---

## 模型选择建议

| Agent | 推荐模型 | 原因 |
|-------|---------|------|
| Agent 1 扫新词 | GPT-5.5 Mini 或 claude-sonnet | 任务简单，省钱 |
| Agent 2 趋势+竞争 | GPT-5.5 Medium（默认） | 需要联网搜索 |
| Agent 3 找抱怨 | claude-sonnet | 长文本理解更强 |
| Agent 4 打分生成 | GPT-5.5 或 claude-sonnet | 需要推理能力 |

> 建议先全部用 GPT-5.5 Medium 跑通流程，稳定后 Agent 1/2 换成 Mini 节省用量。

---

## Agent 1：每日扫新词

**Trigger**：每天定时 07:00

**Agent Instructions：**

```
你是一个 AI 工具词汇侦察员。每天执行以下任务：

1. 抓取以下来源的最新内容（今天的）：
   - Hugging Face Daily Papers: huggingface.co/papers
   - Product Hunt Today: producthunt.com
   - arXiv cs.AI/cs.LG 最新论文标题列表

2. 从内容中提取：
   - 新出现的 AI 模型名（如 Qwen3、Gemma3）
   - 新工具/产品名
   - 高频出现的技术词汇
   - 用户痛点相关词（含 "too expensive" "hard to" "wish" "finally" 等）

3. 去重，与昨日列表对比，只保留新增词汇

4. 输出格式为 JSON：
{
  "date": "2026-05-31",
  "new_terms": ["词1", "词2"],
  "source_breakdown": {"huggingface": [], "producthunt": [], "arxiv": []},
  "pain_signals": ["抱怨句子1", "抱怨句子2"]
}

5. 将结果追加写入 /keywords/daily_raw.json
```

---

## Agent 2：趋势打标 + 竞争初筛

**Trigger**：每天定时 07:30（或 Agent 1 完成后 Webhook 触发）

**Agent Instructions：**

```
读取 /keywords/daily_raw.json 中今天的 new_terms 列表。

对每个词执行：

1. 【趋势判断】
   用 web search 查询该词近30天搜索量变化，判断：
   - 📈 上升中
   - 📊 平稳
   - 📉 下降
   主要搜索国家是哪里（US/CN/IN 等）

2. 【竞争初判】
   Google 搜索该词，观察前10名结果：
   - 是否有专门工具站（非博客/论坛）
   - 页面质量：标题是否精准匹配、内容深度如何
   - 是否存在明显弱页（论坛帖、低质博客占据前排）
   用 allintitle: 搜索，记录精确匹配页面数量
   判断竞争等级：低 / 中 / 高

3. 输出追加到 /keywords/daily_scored.json：
{
  "term": "xxx",
  "trend": "📈上升",
  "main_geo": "US",
  "competition": "低",
  "allintitle_count": 120,
  "top10_quality": "弱，论坛为主"
}
```

---

## Agent 3：找抱怨

**Trigger**：每天定时 08:00（或与 Agent 2 串联）

**Agent Instructions：**

```
读取 /keywords/daily_scored.json，针对趋势为"上升"的词执行：

1. 用 web search 搜索以下组合：
   - "[词] site:reddit.com"
   - "[词] complaints OR frustrating OR broken"
   - "[词] alternative"
   - "[词] review site:producthunt.com"

2. 从结果中提取：
   - 用户反复提到的痛点（归纳为一句话）
   - 现有工具的缺陷描述
   - 用户正在用的"绕路方案"（workaround）
   - 用户希望存在的功能（"I wish", "why can't"）

3. 每个词输出：
{
  "term": "xxx",
  "top_complaints": ["太贵", "不支持中文", "导出格式少"],
  "workarounds": ["用户用Excel手动处理"],
  "desired_features": ["批量处理", "API接入"]
}

追加写入 /keywords/daily_pain.json
```

---

## Agent 4：最终打分 + 入池

**Trigger**：每天定时 09:00（前三个 Agent 都完成后）

**Agent Instructions：**

```
读取今日三个数据文件，对每个词按以下6个维度各打 0-5 分：

维度定义：
- D1 趋势热度：📈上升=5，📊平稳=3，📉下降=1
- D2 竞争空间：低=5，中=3，高=1
- D3 痛点明确度：有3条以上具体抱怨=5，1-2条=3，无=0
- D4 工具可行性：纯信息类难做=1，可做小工具=3，标准SaaS形态=5
- D5 变现潜力：有明确付费场景=5，模糊=3，纯免费=1
- D6 差异化空间：现有方案明显有缺口=5，有改进空间=3，市场饱和=1

规则：
- 总分 ≥ 24：写入 /keywords/pool_validated.json，标记为"进入验证池"
- 总分 18-23：写入 /keywords/pool_watch.json，标记为"继续观察"
- 总分 < 18：丢弃

对"进入验证池"的词，额外生成：
- 一句话产品方向描述
- 建议的落地页标题（英文）
- 3个目标用户画像

输出示例：
{
  "term": "AI meeting notes",
  "total_score": 26,
  "status": "进入验证池",
  "product_direction": "面向独立开发者的轻量会议转录+行动项提取工具",
  "suggested_headline": "Turn Any Meeting Into Action Items in 30 Seconds",
  "target_users": ["远程团队PM", "独立顾问", "销售跟进场景"]
}
```

---

## Slack 通知配置

在 Agent 4 的 Instructions 末尾追加以下内容，并在 Tools 中添加 Slack MCP：

```
完成后，发送 Slack 消息到 #keyword-pool 频道：

"📊 今日词汇分析完成
✅ 进入验证池：X个词
👀 继续观察：X个词
🔥 今日最高分：[词名] (XX分)
查看详情：/keywords/pool_validated.json"
```

---

## 配置步骤

1. **GitHub 新建仓库** `ai-keyword-research`，初始化 `/keywords/` 目录（放一个空的 `.gitkeep`）

2. **在 Cursor Automations 页面** 依次新建4个 Automation：
   - 每个都选择 Repository → `ai-keyword-research`
   - 粘贴对应的 Agent Instructions
   - 设置对应的定时 Trigger

3. **模型**：先全部用默认 GPT-5.5 Medium，跑稳后优化

4. **Slack 通知**：Agent 4 的 Tools 里 `+ Add Tool or MCP` → 添加 Slack MCP，填入 Webhook URL

5. **验证**：手动触发一次 Agent 1，确认 `/keywords/daily_raw.json` 写入成功后，再依次测试后续 Agent

---

## 预期效果

| 指标 | 手动 | 自动化后 |
|------|------|---------|
| 每日耗时 | 60分钟 | 5分钟（只看结果） |
| 覆盖来源 | 取决于精力 | 固定4个来源每天全跑 |
| 打分一致性 | 主观波动 | 规则固定，可对比历史 |
| 验证池积累 | 零散记录 | 自动归档，可追溯 |
