import sys, os, json
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

    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 0.5rem;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    :root {
        --primary-color: #818cf8;
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(129,140,248,0.06) 0%, rgba(129,140,248,0.02) 100%);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        border: 1px solid rgba(129,140,248,0.12);
    }
    div[data-testid="stMetric"] label {
        font-size: 0.8rem !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }

    div[data-testid="stExpander"] {
        border-radius: 12px;
        border: 1px solid rgba(129,140,248,0.12);
        box-shadow: 0 1px 8px rgba(0,0,0,0.04);
        overflow: hidden;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(129,140,248,0.08);
    }

    section[data-testid="stSidebar"] button[kind="secondary"] {
        border-radius: 10px;
        font-size: 0.9rem;
        padding: 0.5rem 0.75rem;
        transition: all 0.2s;
    }
    section[data-testid="stSidebar"] button[kind="secondary"]:hover {
        border-color: #818cf8;
        color: #818cf8;
    }

    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
    .stButton > button:focus, .stButton > button:active {
        border-color: #818cf8 !important;
        box-shadow: 0 0 0 2px rgba(129,140,248,0.25) !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(129,140,248,0.03) 0%, rgba(129,140,248,0.00) 100%);
    }

    .stDownloadButton > button {
        border-radius: 8px;
        font-size: 0.85rem;
    }

    .stChatInput textarea {
        border-radius: 12px !important;
        border: 1px solid rgba(129,140,248,0.25) !important;
    }
    .stChatInput textarea:focus {
        border-color: #818cf8 !important;
        box-shadow: 0 0 0 3px rgba(129,140,248,0.15) !important;
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

if "messages" not in st.session_state:
    st.session_state.messages = []

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
    return st.session_state.workflow.invoke(initial_state)


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
    metrics = []
    amount_col = None
    for col in df.columns:
        if _is_amount_col(col) and df[col].dtype in ("float64", "int64", "float32", "int32"):
            amount_col = col
            break
    if amount_col and len(df) > 0:
        total = df[amount_col].sum()
        if total > 0:
            metrics.append(("📊 汇总金额", f"¥{total:,.2f}"))
    if len(df) > 0:
        metrics.append(("📋 结果行数", f"{len(df)} 条"))
    if amount_col and len(df) > 0:
        avg = df[amount_col].mean()
        if avg > 0 and len(df) > 1:
            metrics.append(("📈 平均值", f"¥{avg:,.2f}"))
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

    st.markdown("### 💬 快捷分析")
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
                if st.button(title, key=f"ex_{title}", use_container_width=True):
                    # add to messages just like a user typed it
                    st.session_state.messages.append({"role": "user", "content": query})
                    st.rerun()

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
        st.session_state.messages = []
        st.rerun()

    st.markdown("<div style='text-align:center;padding-top:1rem;opacity:0.4;font-size:0.78rem;'>Powered by LangGraph + DeepSeek</div>", unsafe_allow_html=True)

# ── Chat Interface ─────────────────────────────────────────────

# Render all messages
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg.get("content", "")
    with st.chat_message(role):
        if role == "user":
            st.write(content)
        else:
            # assistant message — render result blocks
            result = msg.get("result", {})
            intent = result.get("intent", "")
            progress_log = msg.get("progress_log", [])

            if progress_log:
                with st.expander("🔍 执行过程", expanded=False):
                    for step in progress_log:
                        st.write(step)

            if intent == "chat":
                msgs = result.get("messages", [])
                if msgs:
                    st.write(msgs[-1].content)
                else:
                    st.write(content)
                continue

            error = result.get("error_msg", "")
            result_data = result.get("sql_result")

            if error and not result_data:
                retries = result.get("retry_count", 0)
                st.error(f"SQL 执行失败（已重试 {retries} 次）\n\n{error}")
                if retries >= 3:
                    st.warning("已达最大重试次数，请尝试换一种方式描述问题。")
                continue

            if result_data is not None:
                df = pd.DataFrame(result_data)
                user_q = result.get("user_query", "")

                # Metrics
                metrics = extract_metrics(df)
                if metrics:
                    cols = st.columns(len(metrics))
                    for col, (label, value) in zip(cols, metrics):
                        with col:
                            st.metric(label=label, value=value)

                # Chart
                chart_config = result.get("chart_config")
                if chart_config:
                    st.markdown("#### 📈 可视化图表")
                    try:
                        st_echarts(options=chart_config, height="420px")
                    except Exception as e:
                        st.warning(f"图表渲染失败：{e}")

                # Insight
                if len(result_data) > 0:
                    insight_key = f"insight_{hash(user_q)}_{id(msg)}"
                    if insight_key not in st.session_state:
                        st.session_state[insight_key] = fetch_insight(user_q, result_data)
                    insight = st.session_state.get(insight_key, "")
                    if insight:
                        st.markdown(f"""
                        <div style="background:linear-gradient(135deg,rgba(129,140,248,0.08) 0%,rgba(129,140,248,0.02) 100%);
                                    border-radius:12px;padding:1rem 1.25rem;border-left:3px solid #818cf8;
                                    margin:0.5rem 0 0.5rem 0;">
                            <span style="font-size:0.8rem;color:#818cf8;font-weight:600;">💡 AI 洞察</span><br>
                            <span style="font-size:0.95rem;">{insight}</span>
                        </div>
                        """, unsafe_allow_html=True)

                # Data table
                st.markdown("#### 📋 数据明细")
                col_config = build_column_config(df)
                st.dataframe(
                    df,
                    column_config=col_config,
                    use_container_width=True,
                    hide_index=True,
                    height=min(400, 35 * len(df) + 38),
                )

                # CSV download
                csv = df.to_csv(index=False).encode("utf-8-sig")
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="📥 下载 CSV",
                    data=csv,
                    file_name=f"ecom_bi_{ts}.csv",
                    mime="text/csv",
                )

                # SQL
                sql = result.get("sql_query", "")
                if sql:
                    with st.expander("🛠️ 查看生成的 SQL", expanded=False):
                        st.code(sql, language="sql")

                if len(result_data) == 0 and not error:
                    st.info("查询结果为空，请尝试调整问题描述。")

# Input — placed at bottom
col1, col2 = st.columns([7, 1])
with col1:
    prompt = st.chat_input("输入你的分析需求，例如：上个月哪个品类退款率最高？")
with col2:
    if st.button("🧹 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

if prompt and api_key_ok:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Run query
    with st.spinner("🤖 AI Agent 正在分析..."):
        result = run_query(prompt.strip())

    user_q = result.get("user_query", prompt)
    intent = result.get("intent", "")

    content = ""
    if intent == "chat":
        msgs = result.get("messages", [])
        content = msgs[-1].content if msgs else ""
    elif result.get("error_msg") and not result.get("sql_result"):
        content = f"SQL 执行失败：{result['error_msg']}"
    elif result.get("sql_result"):
        row_count = len(result["sql_result"])
        content = f"查询完成，共返回 {row_count} 条数据。"

    # Add assistant message with full result attached
    st.session_state.messages.append({
        "role": "assistant",
        "content": content,
        "result": result,
        "progress_log": st.session_state.get("progress_log", []),
    })
    st.rerun()
