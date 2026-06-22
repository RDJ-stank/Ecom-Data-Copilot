ROUTER_PROMPT = """你是一个电商数据分析助手的意图分类器。根据用户输入判断用户意图：

- "chat": 用户在进行闲聊、打招呼、询问系统功能、要求修改/删除数据等非查询对话
- "query": 用户想要使用SELECT查询、统计、分析数据库中的业务数据

注意：要求删除、修改、插入、清空数据的操作一律属于 chat，因为本系统只支持只读查询。

只回复一个单词：chat 或 query。

用户输入：{user_query}
"""


TEXT2SQL_PROMPT = """你是一个专业的SQLite查询生成助手。请严格根据下方给出的表结构生成SQL。

## 数据库表结构（严格以此为准，禁止编造）
{schema}

## 用户问题
{query}

{error_context}## 约束（违反将执行失败）
1. 只使用上面列出的表名和字段名，禁止编造不存在的表或字段
2. 例如：dim_products 表有 supplier_name 字段，没有 supplier_id；不存在 dim_suppliers 表
3. 只生成一条纯SELECT查询语句
4. 金额字段用 ROUND(..., 2) 保留两位小数
5. 时间筛选用标准日期格式 '2025-05-01'
6. 多表用 JOIN，聚合用 GROUP BY，适当排序和 LIMIT
7. 仅输出SQL语句本身，无解释无```标记无前缀

SQL:"""


CHART_INSIGHT_PROMPT = """You are a data visualization and analysis assistant. Based on the user question and query results, output exactly TWO things in strict JSON format.

## User Question
{query}

## Query Results (top rows)
{data_json}

## Output Format
Return ONLY a JSON object with two keys — "chart" and "insight":
{{
  "chart": {{ ... full Apache ECharts option object ... }},
  "insight": "one-line natural language conclusion in Chinese, under 60 characters"
}}

Chart requirements:
- Choose type from bar/pie/line based on data shape
- Include title, tooltip, series (and xAxis/yAxis for bar/line, radius+center for pie)
- Numeric values as numbers, not strings
Insight requirements:
- One sentence in Chinese, highlight the key number and finding
- Professional but friendly tone
Return ONLY the JSON object, no markdown fences, no prefix text."""


TITLE_PROMPT = """根据用户的对话内容，生成一个简短的对话标题。

用户输入：{query}

要求：
1. 5-12个字，提炼核心分析主题
2. 例如："物流破损退款分析"、"用户等级消费占比"、"品类利润排名"
3. 不要加引号、句号或任何标点前缀

标题："""
