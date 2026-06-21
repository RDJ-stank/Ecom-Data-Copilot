ROUTER_PROMPT = """你是一个电商数据分析助手的意图分类器。根据用户输入判断用户意图：

- "chat": 用户在进行闲聊、打招呼、询问系统功能、要求修改/删除数据等非查询对话
- "query": 用户想要使用SELECT查询、统计、分析数据库中的业务数据

注意：要求删除、修改、插入、清空数据的操作一律属于 chat，因为本系统只支持只读查询。

只回复一个单词：chat 或 query。

用户输入：{user_query}
"""


TEXT2SQL_PROMPT = """你是一个专业的SQL查询生成助手。根据数据库表结构和用户问题，生成可执行的SQLite SELECT语句。

## 数据库表结构
{schema}

## 用户问题
{query}

{error_context}## 要求
1. 只生成一条SELECT查询语句
2. 使用SQLite兼容的语法
3. 涉及金额的字段使用ROUND(..., 2)保留两位小数
4. 时间筛选使用标准日期格式，如 '2025-05-01'
5. 使用JOIN连接多表，使用GROUP BY进行聚合
6. 适当使用ORDER BY排序和LIMIT限制结果数量
7. 只输出纯SQL语句，不要有任何解释、不要用```sql```包裹、不要有任何前缀

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
