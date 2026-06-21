import json
from src.graph.state import AgentState
from src.prompts import CHART_INSIGHT_PROMPT
from src.llm import get_llm
from src.progress import report
from src.error_collector import capture


def generate_chart_node(state: AgentState) -> dict:
    report("📈 正在生成图表与分析结论...")
    query = state["user_query"]
    result = state.get("sql_result")

    if not result:
        return {"chart_config": None, "insight": ""}

    sample = _sample_rows(result)
    data_json = json.dumps(sample, ensure_ascii=False, default=str)

    prompt = CHART_INSIGHT_PROMPT.format(query=query, data_json=data_json)
    llm = get_llm(temperature=0.0)
    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
    except Exception as e:
        capture("generate_chart", e, {"user_query": query})
        return {"chart_config": None, "insight": ""}

    # strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    config = None
    insight = ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            config = parsed.get("chart")
            insight = parsed.get("insight", "")
        else:
            config = None
    except json.JSONDecodeError as e:
        capture("generate_chart", e, {"user_query": query, "raw": raw[:200]})

    return {"chart_config": config, "insight": insight}


def _sample_rows(rows: list, max_rows=20) -> list:
    if len(rows) <= max_rows:
        return rows
    step = max(len(rows) // max_rows, 2)
    sampled = rows[0:5]
    sampled += rows[5::step]
    if rows[-1] not in sampled:
        sampled.append(rows[-1])
    return sampled[:max_rows]
