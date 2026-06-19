import sys
import os
import pandas as pd

# ensure project root in path
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from streamlit_echarts import st_echarts

from src.config import DEEPSEEK_API_KEY, DB_PATH
from src.database import init_db, get_session, DimUser, DimProduct, FactOrder, FactAfterSales
from src.mock_data import seed_all
from src.chromadb_setup import init_chroma_schema
from src.graph.edges import build_workflow
from src.graph.state import AgentState

st.set_page_config(
    page_title="电商私域智能 BI",
    page_icon="📊",
    layout="wide",
)

# ── Initialize ──────────────────────────────────────────────
if "initialized" not in st.session_state:
    init_db()
    seed_all()
    init_chroma_schema()
    st.session_state.initialized = True

if "workflow" not in st.session_state:
    st.session_state.workflow = build_workflow()

if "history" not in st.session_state:
    st.session_state.history = []


# ── Helpers ──────────────────────────────────────────────────
def get_db_stats():
    session = get_session()
    try:
        return {
            "users": session.query(DimUser).count(),
            "products": session.query(DimProduct).count(),
            "orders": session.query(FactOrder).count(),
            "after_sales": session.query(FactAfterSales).count(),
        }
    finally:
        session.close()


def run_query(user_query: str):
    initial_state: AgentState = {
        "messages": [],
        "user_query": user_query,
        "intent": "",
        "retrieved_schema": "",
        "sql_query": "",
        "sql_result": None,
        "sql_columns": None,
        "error_msg": "",
        "retry_count": 0,
        "chart_config": None,
    }
    result = st.session_state.workflow.invoke(initial_state)
    return result


# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 电商私域智能 BI")

    api_key_ok = bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "sk-your-key-here")
    if not api_key_ok:
        st.error("请先在 `.env` 文件中配置 `DEEPSEEK_API_KEY`")

    st.divider()

    st.subheader("💬 试试这些问题")
    examples = [
        "上个月因为物流破损导致退款金额最高的 Top 3 供应商，用柱状图",
        "统计不同用户等级带来的总订单金额占比，画饼图",
        "查询销量前五的商品品类，以及它们对应的平均单件利润，用折线图",
    ]
    for i, ex in enumerate(examples):
        if st.button(f"场景{i+1}: {ex[:40]}...", key=f"ex_{i}", use_container_width=True):
            st.session_state.pending_query = ex

    st.divider()

    st.subheader("📈 数据库概况")
    try:
        stats = get_db_stats()
        st.metric("用户数", stats["users"])
        st.metric("商品数", stats["products"])
        st.metric("订单数", stats["orders"])
        st.metric("售后记录", stats["after_sales"])
    except Exception:
        st.caption("数据库未就绪")

    st.divider()
    if st.button("🔄 重新生成 Mock 数据", use_container_width=True):
        # re-seed
        import sqlalchemy
        from src.database import Base, engine
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        seed_all()
        init_chroma_schema()
        st.session_state.history = []
        st.rerun()


# ── Main Area ────────────────────────────────────────────────
st.title("📊 电商私域智能 BI 与可视化分析 Agent")

# input
col_input, col_btn = st.columns([5, 1])
with col_input:
    user_input = st.chat_input("输入你的分析需求，例如：上个月退款最多的品类是什么？")
with col_btn:
    run_btn = st.button("🚀 分析", use_container_width=True, disabled=not api_key_ok)

# handle pending query from sidebar examples
pending = st.session_state.pop("pending_query", None)
if pending:
    user_input = pending

if user_input is None:
    user_input = ""

# trigger
if user_input.strip() and api_key_ok:
    with st.spinner("🤖 Agent 正在思考..."):
        result = run_query(user_input.strip())
    st.session_state.history.append(result)

# ── Display Results ──────────────────────────────────────────
if st.session_state.history:
    latest = st.session_state.history[-1]

    intent = latest.get("intent", "")
    if intent == "chat":
        msgs = latest.get("messages", [])
        if msgs:
            st.chat_message("assistant").write(msgs[-1].content)
        else:
            st.chat_message("assistant").write("你好！我可以帮你查询和分析电商数据。")

    else:
        # SQL block
        sql = latest.get("sql_query", "")
        if sql:
            with st.expander("📝 生成的 SQL", expanded=True):
                st.code(sql, language="sql")

        # Errors
        error = latest.get("error_msg", "")
        if error and not latest.get("sql_result"):
            retries = latest.get("retry_count", 0)
            st.error(f"SQL 执行失败（已重试 {retries} 次）：\n{error}")
            if retries >= 3:
                st.warning("已达最大重试次数，请尝试换一种方式描述问题。")

        # Results table
        result_data = latest.get("sql_result")
        if result_data:
            df = pd.DataFrame(result_data)
            st.subheader("📋 查询结果")
            st.dataframe(df, use_container_width=True)

            # Chart
            chart_config = latest.get("chart_config")
            if chart_config:
                st.subheader("📈 可视化图表")
                try:
                    st_echarts(options=chart_config, height="400px")
                except Exception as e:
                    st.warning(f"图表渲染失败：{e}")
                    st.json(chart_config)
            else:
                st.info("未能生成图表配置，请查看数据表格。")

        # Empty result
        if result_data is not None and len(result_data) == 0 and not error:
            st.info("查询结果为空，请尝试调整问题描述。")

# history
if len(st.session_state.history) > 1:
    st.divider()
    st.subheader("📜 历史查询")
    for i, entry in enumerate(reversed(st.session_state.history[:-1])):
        q = entry.get("user_query", "")
        with st.expander(f"Q: {q[:60]}..." if len(q) > 60 else f"Q: {q}"):
            sql = entry.get("sql_query", "")
            if sql:
                st.code(sql, language="sql")
            result_data = entry.get("sql_result")
            if result_data:
                st.dataframe(pd.DataFrame(result_data), use_container_width=True)
            chart_config = entry.get("chart_config")
            if chart_config:
                try:
                    st_echarts(options=chart_config, height="300px")
                except Exception:
                    pass
