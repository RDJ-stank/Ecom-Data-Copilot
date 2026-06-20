import json
from src.graph.state import AgentState
from src.prompts import CHART_PROMPT
from src.llm import get_llm
from src.progress import report


def generate_chart_node(state: AgentState) -> dict:
    report("📈 正在生成可视化图表配置...")
    query = state["user_query"]
    result = state.get("sql_result")

    if not result:
        return {"chart_config": None}

    top_rows = result[:20]
    data_json = json.dumps(top_rows, ensure_ascii=False, default=str)

    prompt = CHART_PROMPT.format(query=query, data_json=data_json)
    llm = get_llm(temperature=0.0)
    response = llm.invoke(prompt)
    raw = response.content.strip()

    # strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        config = None

    return {"chart_config": config}
