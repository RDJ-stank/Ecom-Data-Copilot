"""Context Frame — semantic cache to skip redundant LLM calls during follow-up questions.

Stored in st.session_state (not LangGraph state) so it survives reruns.
Tracks what the user is currently analyzing and decides routing depth.
"""

FRESH = "full"           # new topic → full pipeline
CHANGE_CHART = "chart"   # same data, just want different visual
CHANGE_FILTER = "filter" # same subject/metric, different time/category
CHANGE_SUBJECT = "full"  # subject changed → full pipeline
CHANGE_NONE = "none"     # exact same frame → replay cached result


def build_frame(user_query: str, prev: dict = None) -> dict:
    """Extract analysis context from user query using keyword heuristics (0 LLM cost).
    Inherits unchanged fields from prev frame for follow-up questions like '用饼图展示'."""
    q = user_query.lower()
    frame = {"raw": user_query}

    # subject detection
    if any(kw in q for kw in ["供应商", "供货"]):
        frame["subject"] = "supplier"
    elif any(kw in q for kw in ["用户等级", "会员", "用户价值"]):
        frame["subject"] = "user_level"
    elif any(kw in q for kw in ["品类", "商品", "产品", "利润"]):
        frame["subject"] = "category"
    elif any(kw in q for kw in ["渠道"]):
        frame["subject"] = "channel"
    elif any(kw in q for kw in ["售后", "退款", "退货", "破损"]):
        frame["subject"] = "after_sales"
    elif prev:
        frame["subject"] = prev.get("subject", "general")
    else:
        frame["subject"] = "general"

    # metric detection
    if any(kw in q for kw in ["退款金额", "退款额", "售后金额"]):
        frame["metric"] = "refund_amount"
    elif any(kw in q for kw in ["利润", "毛利"]):
        frame["metric"] = "profit"
    elif any(kw in q for kw in ["金额", "销售额", "订单金额", "占比"]):
        frame["metric"] = "order_amount"
    elif any(kw in q for kw in ["数量", "销量", "多少", "统计"]):
        frame["metric"] = "count"
    elif prev:
        frame["metric"] = prev.get("metric", "count")
    else:
        frame["metric"] = "count"

    # chart type
    if any(kw in q for kw in ["饼图", "占比", "比例", "构成"]):
        frame["chart"] = "pie"
    elif any(kw in q for kw in ["折线", "趋势", "变化"]):
        frame["chart"] = "line"
    elif any(kw in q for kw in ["柱状", "柱", "bar", "排名", "top", "排序"]):
        frame["chart"] = "bar"
    elif prev:
        frame["chart"] = prev.get("chart", "auto")
    else:
        frame["chart"] = "auto"

    # time filter
    if "上个月" in q or "上月" in q or "最近一个月" in q:
        frame["time"] = "last_month"
    elif "上周" in q or "最近一周" in q:
        frame["time"] = "last_week"
    elif "昨天" in q:
        frame["time"] = "yesterday"
    elif "今天" in q:
        frame["time"] = "today"
    elif prev:
        frame["time"] = prev.get("time", "any")
    else:
        frame["time"] = "any"

    # rank
    if "top" in q or "前" in q or "排名" in q or "最高" in q or "最多" in q:
        frame["rank"] = True
    elif prev:
        frame["rank"] = prev.get("rank", False)
    else:
        frame["rank"] = False

    return frame


def compare_frame(prev: dict, curr: dict) -> str:
    """Compare two context frames and return routing decision."""
    if not prev:
        return FRESH
    # transition keywords suggest intent change even if frame didn't shift
    q = curr.get("raw", "").lower()
    if any(kw in q for kw in ["换成", "改成", "改为", "换一个", "再查", "再帮我", "接下来", "那么"]):
        return CHANGE_FILTER
    if prev.get("subject") != curr.get("subject"):
        return CHANGE_SUBJECT
    if prev.get("metric") != curr.get("metric"):
        return CHANGE_SUBJECT
    if prev.get("time") != curr.get("time"):
        return CHANGE_FILTER
    if prev.get("chart") != curr.get("chart"):
        return CHANGE_CHART
    return CHANGE_NONE
