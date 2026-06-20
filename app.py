import sys, os, json, io
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from streamlit_echarts import st_echarts

from src.config import DEEPSEEK_API_KEY
from src.database import init_db, get_session, DimUser, DimProduct, FactOrder, FactAfterSales
from src.mock_data import seed_all
from src.chromadb_setup import init_chroma_schema
from src.graph.edges import build_workflow
from src.graph.state import AgentState
from src.progress import set_callback
from src.llm import get_llm
from src.prompts import INSIGHT_PROMPT

st.set_page_config(page_title="电商私域智能 BI", page_icon="📊", layout="wide")

# ── CSS Injection ─────────────────────────────────────────────
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {display: none;}

    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 1rem;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    /* Accent overrides */
    :root {
        --primary-color: #6366f1;
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(99,102,241,0.05) 0%, rgba(99,102,241,0.02) 100%);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        border: 1px solid rgba(99,102,241,0.10);
    }
    div[data-testid="stMetric"] label {
        font-size: 0.8rem !important;
        color: #64748b !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #1e293b !important;
    }

    div[data-testid="stExpander"] {
        border-radius: 12px;
        border: 1px solid rgba(99,102,241,0.10);
        box-shadow: 0 1px 8px rgba(0,0,0,0.04);
        overflow: hidden;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(99,102,241,0.06);
    }

    section[data-testid="stSidebar"] button[kind="secondary"] {
        border-radius: 10px;
        font-size: 0.9rem;
        padding: 0.5rem 0.75rem;
        transition: all 0.2s;
    }
    section[data-testid="stSidebar"] button[kind="secondary"]:hover {
        border-color: #6366f1;
        color: #6366f1;
    }

    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
    .stButton > button:focus, .stButton > button:active {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 2px rgba(99,102,241,0.25) !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(99,102,241,0.02) 0%, rgba(99,102,241,0.00) 100%);
    }

    .stDownloadButton > button {
        border-radius: 8px;
        font-size: 0.85rem;
    }

    .stChatInput textarea {
        border-radius: 12px !important;
        border: 1px solid rgba(99,102,241,0.2) !important;
    }
    .stChatInput textarea:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
    }

    .stAlert {
        border-radius: 12px;
    }

    div[data-testid="stStatus"] {
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ── Init ───────────────────────────────────────────────────────
force_reset = st.session_state.pop("force_reset", False)
if "initialized" not in st.session_state or force_reset:
    if force_reset:
        from src.database import Base, engine
        engine.dispose()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        import shutil
        from src.config import CHROMA_PATH
        if os.path.exists(CHROMA_PATH):
            shutil.rmtree(CHROMA_PATH, ignore_errors=True)

    init_db()
    seed_all()
    init_chroma_schema()
    st.session_state.initialized = True

if "workflow" not in st.session_state:
    st.session_state.workflow = build_workflow()

if "history" not in st.session_state:
    st.session_state.history = []

if "progress_log" not in st.session_state:
    st.session_state.progress_log = []

api_key_ok = bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "sk-your-key-here")

# ── Helpers ────────────────────────────────────────────────────
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


def _on_progress(msg: str):
    st.session_state.progress_log.append(msg)


def run_query(user_query: str):
    st.session_state.progress_log = []
    set_callback(_on_progress)

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


def _is_amount_col(name: str) -> bool:
    kw = ["amount", "金额", "price", "价格", "cost", "成本", "profit", "利润",
          "sum", "total", "总计", "合计", "收入", "支出", "退款", "actual", "订单金额"]
    return any(k in name.lower() for k in kw)


def _is_pct_col(name: str) -> bool:
    kw = ["percentage", "占比", "ratio", "rate", "pct", "比例", "百分比"]
    return any(k in name.lower() for k in kw)


def build_column_config(df: pd.DataFrame) -> dict:
    cfg = {}
    for col in df.columns:
        if _is_pct_col(col):
            cfg[col] = st.column_config.NumberColumn(col, format="%.1f%%")
        elif _is_amount_col(col):
            cfg[col] = st.column_config.NumberColumn(col, format="¥%.2f")
    return cfg


def extract_metrics(df: pd.DataFrame):
    """从结果中挑1-3个关键数字用作指标卡"""
    metrics = []
    # find first amount column for total
    amount_col = None
    for col in df.columns:
        if _is_amount_col(col) and df[col].dtype in ("float64", "int64", "float32", "int32"):
            amount_col = col
            break
    # row count
    if len(df) > 1 and amount_col:
        total = df[amount_col].sum()
        if total > 0:
            metrics.append(("📊 汇总金额", f"¥{total:,.2f}"))
    if len(df) > 0:
        metrics.append(("📋 结果行数", f"{len(df)} 条"))
    # if single row, show key values
    if len(df) == 1 and amount_col:
        val = df[amount_col].iloc[0]
        metrics.append(("💎 核心数值", f"¥{val:,.2f}"))
    return metrics[:3]


def fetch_insight(user_query: str, data: list) -> str:
    try:
        data_json = json.dumps(data[:10], ensure_ascii=False, default=str)
        prompt = INSIGHT_PROMPT.format(query=user_query, data_json=data_json)
        llm = get_llm(temperature=0.3)
        resp = llm.invoke(prompt)
        return resp.content.strip()
    except Exception:
        return ""


# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Ecom BI")
    st.caption("电商私域智能分析平台")

    if not api_key_ok:
        st.error("请在 `.env` 中配置 `DEEPSEEK_API_KEY`")

    st.divider()

    st.markdown("### 💬 快捷分析场景")
    examples = [
        ("📦", "售后物流破损分析", "上个月因为物流破损导致退款金额最高的 Top 3 供应商，用柱状图"),
        ("👥", "用户等级价值分析", "统计不同用户等级带来的总订单金额占比，画饼图"),
        ("📈", "商品品类利润洞察", "查询销量前五的商品品类，以及它们对应的平均单件利润，用柱状图"),
    ]
    for emoji, title, query in examples:
        with st.container():
            c1, c2 = st.columns([0.15, 0.85])
            with c1:
                st.markdown(f"<div style='font-size:1.6rem;text-align:center;padding-top:0.3rem;'>{emoji}</div>", unsafe_allow_html=True)
            with c2:
                btn_label = title
                if st.button(btn_label, key=f"ex_{title}", use_container_width=True):
                    st.session_state.pending_query = query

    st.divider()

    st.markdown("### 📈 数据库概况")
    try:
        stats = get_db_stats()
        cols = st.columns(2)
        cols[0].metric("用户数", stats["users"])
        cols[1].metric("商品数", stats["products"])
        cols[0].metric("订单数", stats["orders"])
        cols[1].metric("售后记录", stats["after_sales"])
    except Exception:
        st.caption("数据库未就绪")

    st.divider()
    if st.button("🔄 重新生成 Mock 数据", use_container_width=True):
        st.session_state.force_reset = True
        st.session_state.history = []
        st.rerun()

    st.markdown("<div style='text-align:center;padding-top:1rem;opacity:0.4;font-size:0.78rem;'>Powered by LangGraph + DeepSeek</div>", unsafe_allow_html=True)

# ── Main Area ──────────────────────────────────────────────────
# Welcome hero when cold start
if not st.session_state.history:
    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1.5rem 0;">
        <h1 style="font-size:2.2rem;font-weight:700;color:#1e293b;margin-bottom:0.5rem;">📊 电商私域智能 BI</h1>
        <p style="font-size:1.05rem;color:#64748b;max-width:600px;margin:0 auto 1.5rem auto;">
            用自然语言提问，AI 自动生成 SQL 并可视化为图表。<br>支持售后分析、用户价值、商品利润等多维度洞察。
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Quick start cards
    qc1, qc2, qc3 = st.columns(3)
    cards = [
        ("📦", "售后物流分析", "找出物流破损退款最高的供应商，定位售后风险源头"),
        ("👥", "用户价值分层", "按用户等级统计订单金额占比，识别高价值客群"),
        ("📈", "商品利润洞察", "品类销量排名与单件利润对比，优化选品策略"),
    ]
    for idx, (col, (emoji, title, desc)) in enumerate(zip([qc1, qc2, qc3], cards)):
        with col:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(99,102,241,0.04) 0%,rgba(99,102,241,0.01) 100%);
                        border-radius:14px;padding:1.5rem 1.2rem;border:1px solid rgba(99,102,241,0.08);
                        height:100%;cursor:default;">
                <div style="font-size:2rem;margin-bottom:0.5rem;">{emoji}</div>
                <div style="font-weight:600;font-size:1rem;color:#1e293b;margin-bottom:0.35rem;">{title}</div>
                <div style="font-size:0.82rem;color:#94a3b8;line-height:1.5;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

# Chat-style input
st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
col_input, col_btn = st.columns([6, 1])
with col_input:
    user_input = st.chat_input("输入你的分析需求，例如：上个月哪个品类退款率最高？")
with col_btn:
    run_btn = st.button("🚀 分析", use_container_width=True, disabled=not api_key_ok)

pending = st.session_state.pop("pending_query", None)
if pending:
    user_input = pending

if user_input is None:
    user_input = ""

# ── Execute ────────────────────────────────────────────────────
if user_input.strip() and api_key_ok:
    with st.spinner("🤖 AI Agent 正在分析..."):
        result = run_query(user_input.strip())
    st.session_state.history.append(result)

# ── Display Latest Result ──────────────────────────────────────
if st.session_state.history:
    latest = st.session_state.history[-1]
    user_q = latest.get("user_query", "")

    # Show progress timeline
    progress_log = st.session_state.get("progress_log", [])
    if progress_log and latest.get("intent") == "query":
        with st.expander("🔍 查看执行过程", expanded=False):
            for step in progress_log:
                st.write(step)

    intent = latest.get("intent", "")
    if intent == "chat":
        msgs = latest.get("messages", [])
        if msgs:
            st.chat_message("assistant").write(msgs[-1].content)
        else:
            st.chat_message("assistant").write("你好！我可以帮你查询和分析电商数据。")
    else:
        error = latest.get("error_msg", "")
        result_data = latest.get("sql_result")

        # Error state
        if error and not result_data:
            retries = latest.get("retry_count", 0)
            st.error(f"SQL 执行失败（已重试 {retries} 次）\n\n{error}")
            if retries >= 3:
                st.warning("已达最大重试次数，请尝试换一种方式描述问题。")
        elif result_data is not None:
            df = pd.DataFrame(result_data)

            # ── 1. Key Metrics ──
            metrics = extract_metrics(df)
            if metrics:
                cols = st.columns(len(metrics))
                for col, (label, value) in zip(cols, metrics):
                    with col:
                        st.metric(label=label, value=value)

            # ── 2. Chart (top priority) ──
            chart_config = latest.get("chart_config")
            if chart_config:
                st.markdown("### 📈 可视化图表")
                # card wrapper effect
                with st.container():
                    try:
                        st_echarts(options=chart_config, height="420px")
                    except Exception as e:
                        st.warning(f"图表渲染失败：{e}")

            # ── 3. Insight Conclusion ──
            if result_data and len(result_data) > 0:
                insight_key = f"insight_{hash(user_q)}"
                if insight_key not in st.session_state:
                    st.session_state[insight_key] = fetch_insight(user_q, result_data)
                insight = st.session_state.get(insight_key, "")
                if insight:
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,rgba(99,102,241,0.06) 0%,rgba(99,102,241,0.02) 100%);
                                border-radius:12px;padding:1rem 1.25rem;border-left:3px solid #6366f1;
                                margin:0.8rem 0 1rem 0;">
                        <span style="font-size:0.8rem;color:#6366f1;font-weight:600;">💡 AI 洞察</span><br>
                        <span style="color:#475569;font-size:0.95rem;">{insight}</span>
                    </div>
                    """, unsafe_allow_html=True)

            # ── 4. Data Table ──
            st.markdown("### 📋 数据明细")
            col_config = build_column_config(df)
            st.dataframe(
                df,
                column_config=col_config,
                use_container_width=True,
                hide_index=True,
                height=min(400, 35 * len(df) + 38),
            )

            # ── 5. CSV Download ──
            csv = df.to_csv(index=False).encode("utf-8-sig")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="📥 下载 CSV",
                data=csv,
                file_name=f"ecom_bi_{ts}.csv",
                mime="text/csv",
            )

            # ── 6. SQL (collapsed, last) ──
            sql = latest.get("sql_query", "")
            if sql:
                with st.expander("🛠️ 查看生成的 SQL 代码", expanded=False):
                    st.code(sql, language="sql")

            # Empty result
            if len(result_data) == 0 and not error:
                st.info("查询结果为空，请尝试调整问题描述。")

# ── History ────────────────────────────────────────────────────
if len(st.session_state.history) > 1:
    st.divider()
    st.markdown("### 📜 历史查询")
    for i, entry in enumerate(reversed(st.session_state.history[:-1])):
        q = entry.get("user_query", "")
        label = f"Q: {q[:70]}..." if len(q) > 70 else f"Q: {q}"
        with st.expander(label):
            result_data = entry.get("sql_result")
            if result_data:
                df = pd.DataFrame(result_data)
                col_config = build_column_config(df)
                st.dataframe(df, column_config=col_config, use_container_width=True, hide_index=True)
            chart_config = entry.get("chart_config")
            if chart_config:
                try:
                    st_echarts(options=chart_config, height="320px")
                except Exception:
                    pass
            sql = entry.get("sql_query", "")
            if sql:
                st.code(sql, language="sql")
