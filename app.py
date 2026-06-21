import sys, os, uuid
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
from src.prompts import TITLE_PROMPT
from src.context_frame import build_frame, compare_frame, FRESH, CHANGE_CHART, CHANGE_FILTER, CHANGE_SUBJECT, CHANGE_NONE

st.set_page_config(page_title="电商私域智能 BI", page_icon="📊", layout="wide")

# ── CSS Injection ─────────────────────────────────────────────
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .main .block-container { padding-top: 1rem; padding-bottom: 0.5rem; }
    section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }

    :root { --primary-color: #818cf8; }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(129,140,248,0.06) 0%, rgba(129,140,248,0.02) 100%);
        border-radius: 14px; padding: 1rem 1.25rem;
        border: 1px solid rgba(129,140,248,0.12);
    }
    div[data-testid="stMetric"] label { font-size: 0.8rem !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important; font-weight: 700 !important;
    }

    div[data-testid="stExpander"], div[data-testid="stDataFrame"], .stAlert {
        border-radius: 12px; overflow: hidden;
    }
    div[data-testid="stExpander"] {
        border: 1px solid rgba(129,140,248,0.12);
        box-shadow: 0 1px 8px rgba(0,0,0,0.04);
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(129,140,248,0.08);
    }

    .stButton > button { border-radius: 8px; font-weight: 500; }
    .stButton > button:focus, .stButton > button:active {
        border-color: #818cf8 !important;
        box-shadow: 0 0 0 2px rgba(129,140,248,0.25) !important;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(129,140,248,0.03) 0%, rgba(129,140,248,0.00) 100%);
    }
    .stDownloadButton > button { border-radius: 8px; font-size: 0.85rem; }
    .stChatInput textarea {
        border-radius: 12px !important;
        border: 1px solid rgba(129,140,248,0.25) !important;
    }
    .stChatInput textarea:focus {
        border-color: #818cf8 !important;
        box-shadow: 0 0 0 3px rgba(129,140,248,0.15) !important;
    }
    /* session list buttons in sidebar — compact */
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] button {
        text-align: left; padding: 0.4rem 0.6rem; font-size: 0.85rem;
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

# session structure: {"sessions": {id: {title, messages, created}}, "active": id}
if "sessions" not in st.session_state:
    sid = str(uuid.uuid4())[:8]
    st.session_state.sessions = {}
    st.session_state.active_session = sid

if "editing_sid" not in st.session_state:
    st.session_state.editing_sid = None

# ensure there's always an active session
active = st.session_state.active_session
if active not in st.session_state.sessions:
    st.session_state.sessions[active] = {
        "title": "对话 1",
        "messages": [],
        "created": datetime.now().isoformat(),
        "last_frame": None,
        "cached_result": None,
    }

_api_key_ok = bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "sk-your-key-here")


# ── Helpers ────────────────────────────────────────────────────
def _current_session():
    return st.session_state.sessions[st.session_state.active_session]


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
    set_callback(lambda msg: None)
    initial_state: AgentState = {
        "messages": [],
        "user_query": user_query,
        "intent": "",
        "retrieved_schema": "",
        "pruned_schema": "",
        "sql_query": "",
        "sql_result": None,
        "sql_columns": None,
        "error_msg": "",
        "error_code": "",
        "retry_count": 0,
        "chart_config": None,
        "insight": "",
        "needs_review": False,
        "review_verdict": "",
        "review_issues": [],
    }
    return st.session_state.workflow.invoke(initial_state)


def _is_amount_col(name: str) -> bool:
    kw = ["amount", "金额", "price", "价格", "cost", "成本", "profit", "利润",
          "sum", "total", "总计", "合计", "收入", "支出", "退款", "actual"]
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


def _auto_title(first_user_msg: str) -> str:
    try:
        prompt = TITLE_PROMPT.format(query=first_user_msg)
        llm = get_llm(temperature=0.5)
        resp = llm.invoke(prompt)
        title = resp.content.strip()
        return title[:20] if title else first_user_msg[:15] + "..."
    except Exception:
        return first_user_msg[:15] + "..."


def _execute_pending():
    """If the last message is from user and unanswered, run query and append assistant."""
    sess = _current_session()
    msgs = sess["messages"]
    if not msgs or msgs[-1]["role"] == "assistant":
        return
    last_user = msgs[-1]["content"]

    prev_frame = sess.get("last_frame")
    curr_frame = build_frame(last_user, prev_frame)
    cached_result = sess.get("cached_result")
    route = compare_frame(prev_frame, curr_frame)

    if route == CHANGE_CHART and cached_result and cached_result.get("sql_result"):
        with st.spinner("🤖 正在用新图表类型重新渲染..."):
            from src.graph.generate_chart import generate_chart_node
            chart_state = {
                "user_query": last_user,
                "sql_result": cached_result["sql_result"],
            }
            chart_update = generate_chart_node(chart_state)
            result = {**cached_result, **chart_update, "user_query": last_user}
    elif route == CHANGE_NONE and cached_result:
        result = {**cached_result, "user_query": last_user}
    else:
        with st.spinner("🤖 AI Agent 正在分析..."):
            result = run_query(last_user)
        sess["cached_result"] = result

    sess["last_frame"] = curr_frame

    intent = result.get("intent", "")
    if intent == "chat":
        msgs_result = result.get("messages", [])
        content = msgs_result[-1].content if msgs_result else ""
    elif result.get("error_msg") and not result.get("sql_result"):
        content = f"SQL 执行失败：{result['error_msg']}"
    elif result.get("sql_result"):
        content = f"查询完成，共返回 {len(result['sql_result'])} 条数据。"
    else:
        content = "已处理。"

    msgs.append({
        "role": "assistant",
        "content": content,
        "result": result,
    })
    sess["title"] = _auto_title(msgs[0]["content"])
    st.rerun()


# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    # ── Session Switcher ──
    st.markdown("### 💬 对话记录")

    # New chat button — prominent
    if st.button("➕ 新建对话", use_container_width=True):
        sid = str(uuid.uuid4())[:8]
        st.session_state.sessions[sid] = {
            "title": "新对话",
            "messages": [],
            "created": datetime.now().isoformat(),
            "last_frame": None,
            "cached_result": None,
        }
        st.session_state.active_session = sid
        st.rerun()

    # List existing sessions
    sessions_list = sorted(
        st.session_state.sessions.items(),
        key=lambda kv: kv[1].get("created", ""),
        reverse=True,
    )
    for sid, sdata in sessions_list:
        title = sdata.get("title", "未命名")
        is_active = sid == st.session_state.active_session
        editing = st.session_state.editing_sid == sid

        c1, c2 = st.columns([0.82, 0.18])
        with c1:
            btn_type = "primary" if is_active else "secondary"
            prefix = "▸ " if is_active else "  "
            label = f"{prefix}{title}"
            short_label = label[:25] + "..." if len(label) > 25 else label
            if st.button(short_label, key=f"sess_{sid}", use_container_width=True, type=btn_type):
                st.session_state.active_session = sid
                st.session_state.editing_sid = None
                st.rerun()
        with c2:
            edit_label = "✅" if editing else "✏️"
            if st.button(edit_label, key=f"edit_{sid}", use_container_width=True):
                st.session_state.editing_sid = sid if not editing else None
                st.rerun()

        if editing:
            new_title = st.text_input(
                "标题", value=title, key=f"title_input_{sid}",
                label_visibility="collapsed", placeholder="输入标题..."
            )
            if st.button("保存", key=f"save_title_{sid}", use_container_width=True):
                if new_title.strip():
                    st.session_state.sessions[sid]["title"] = new_title.strip()
                st.session_state.editing_sid = None
                st.rerun()

    # Delete current session (only if more than 1)
    if len(st.session_state.sessions) > 1:
        if st.button("🗑 删除当前对话", use_container_width=True):
            del st.session_state.sessions[active]
            # pick the most recent remaining
            remaining = sorted(st.session_state.sessions.keys())
            st.session_state.active_session = remaining[-1]
            st.rerun()

    st.divider()

    st.markdown("### 💬 快捷分析")
    examples = [
        ("📦 售后物流破损分析", "上个月因为物流破损导致退款金额最高的 Top 3 供应商，用柱状图"),
        ("👥 用户等级价值分析", "统计不同用户等级带来的总订单金额占比，画饼图"),
        ("📈 商品品类利润洞察", "查询销量前五的商品品类，以及它们对应的平均单件利润，用柱状图"),
    ]
    for label, query in examples:
        if st.button(label, key=f"ex_{label}", use_container_width=True):
            sess = _current_session()
            sess["messages"].append({"role": "user", "content": query})
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
        st.rerun()

    st.markdown("<div style='text-align:center;padding-top:1rem;opacity:0.4;font-size:0.78rem;'>Powered by LangGraph + DeepSeek</div>", unsafe_allow_html=True)


# ── Main Chat Area ────────────────────────────────────────────
sess = _current_session()
messages = sess["messages"]

# Render title
st.markdown(f"### {sess.get('title', '对话')}")

# Render messages
for msg in messages:
    role = msg["role"]
    content = msg.get("content", "")
    with st.chat_message(role):
        if role == "user":
            st.write(content)
        else:
            result = msg.get("result", {})
            if not result:
                st.write(content)
                continue

            intent = result.get("intent", "")
            if intent == "chat":
                msgs_r = result.get("messages", [])
                st.write(msgs_r[-1].content if msgs_r else content)
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

                metrics = extract_metrics(df)
                if metrics:
                    cols = st.columns(len(metrics))
                    for col, (label, value) in zip(cols, metrics):
                        with col:
                            st.metric(label=label, value=value)

                chart_config = result.get("chart_config")
                if chart_config:
                    st.markdown("#### 📈 可视化图表")
                    try:
                        st_echarts(options=chart_config, height="420px")
                    except Exception as e:
                        st.warning(f"图表渲染失败：{e}")

                if len(result_data) > 0:
                    insight = result.get("insight", "")
                    if insight:
                        st.markdown(f"""
                        <div style="background:linear-gradient(135deg,rgba(129,140,248,0.08) 0%,rgba(129,140,248,0.02) 100%);
                                    border-radius:12px;padding:1rem 1.25rem;border-left:3px solid #818cf8;
                                    margin:0.5rem 0 0.5rem 0;">
                            <span style="font-size:0.8rem;color:#818cf8;font-weight:600;">💡 AI 洞察</span><br>
                            <span style="font-size:0.95rem;">{insight}</span>
                        </div>
                        """, unsafe_allow_html=True)

                st.markdown("#### 📋 数据明细")
                col_config = build_column_config(df)
                st.dataframe(
                    df,
                    column_config=col_config,
                    use_container_width=True,
                    hide_index=True,
                    height=min(400, 35 * len(df) + 38),
                )

                csv = df.to_csv(index=False).encode("utf-8-sig")
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="📥 下载 CSV",
                    data=csv,
                    file_name=f"ecom_bi_{ts}.csv",
                    mime="text/csv",
                )

                sql = result.get("sql_query", "")
                if sql:
                    with st.expander("🛠️ 查看生成的 SQL", expanded=False):
                        st.code(sql, language="sql")

                if len(result_data) == 0 and not error:
                    st.info("查询结果为空，请尝试调整问题描述。")

# ── Input ─────────────────────────────────────────────────────
prompt = st.chat_input("输入你的分析需求，例如：上个月哪个品类退款率最高？")
if prompt and _api_key_ok:
    sess["messages"].append({"role": "user", "content": prompt})
    st.rerun()

# ── Auto-execute pending user message ─────────────────────────
if messages and messages[-1]["role"] == "user" and _api_key_ok:
    _execute_pending()
