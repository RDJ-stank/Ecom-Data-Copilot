# 📊 电商私域智能 BI 与可视化分析 Agent

基于 LangGraph 构建的 Text2SQL 智能体工作流，将电商运营的自然语言诉求转化为 SQL，安全执行并渲染为可视化图表。

## 核心能力

- **自然语言问数**：用大白话提问，Agent 自动生成 SQL 并查询
- **Schema RAG**：ChromaDB 向量检索表结构，精准匹配 4 张核心数据表
- **安全沙箱**：白名单放行 SELECT，拦截 DROP/DELETE/INSERT/UPDATE/TRUNCATE
- **自动纠错**：SQL 报错后自动回传模型修正，最多重试 3 次
- **图表可视化**：查询结果一键渲染为柱状图、饼图、折线图

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Streamlit + streamlit-echarts |
| 工作流 | LangGraph + LangChain |
| 大模型 | DeepSeek-Coder（兼容 OpenAI SDK） |
| 向量库 | ChromaDB（Table Schema RAG） |
| 数据库 | SQLite + SQLAlchemy ORM |
| SQL 安全 | sqlparse AST 解析 + 白名单策略 |

## 工作流架构

```
用户提问 → Router（意图识别）
           ├── 闲聊 → 直接回复
           └── 数据查询 → Schema RAG → Text2SQL → Execute SQL（安全校验）
                                    ↑                    │
                                    └── 报错重试 ←───────┤（≤3次）
                                                         ↓ 成功
                                                    Generate Chart → 渲染图表
```

## 分析场景示例

| 场景 | 问题 | 图表类型 |
|------|------|----------|
| 售后管控 | 上个月"物流破损"退款金额 Top 3 供应商 | 柱状图 |
| 用户价值 | 各用户等级总订单金额占比 | 饼图 |
| 商品利润 | 销量前五品类 + 平均单件利润 | 折线图/柱状图 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 DeepSeek API Key
# 编辑 .env 文件，填入你的 Key：
#   DEEPSEEK_API_KEY=sk-你的key

# 3. 启动
streamlit run app.py
```

浏览器打开 `http://localhost:8501`，首次启动会自动生成 Mock 数据（200 用户、60 商品、3000 订单、400 售后记录）并初始化 ChromaDB 索引。

## 项目结构

```
├── app.py                  # Streamlit 入口
├── src/
│   ├── database.py         # 4 张核心表的 ORM 定义
│   ├── mock_data.py        # Mock 数据生成器
│   ├── chromadb_setup.py   # Schema 向量索引 & 检索
│   ├── llm.py              # DeepSeek LLM 工厂
│   ├── prompts.py          # Router / Text2SQL / Chart Prompt 模板
│   └── graph/
│       ├── state.py        # AgentState 状态定义
│       ├── router.py       # 意图识别节点
│       ├── schema_rag.py   # Schema 召回节点
│       ├── text2sql.py     # SQL 生成节点（含重试纠错）
│       ├── execute_sql.py  # 安全校验 + 执行节点
│       ├── generate_chart.py # 图表配置生成节点
│       └── edges.py        # 条件边 + 工作流组装
├── data/                   # SQLite db + ChromaDB 索引（自动生成）
└── .env                    # API Key 配置
```
