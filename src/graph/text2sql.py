from src.graph.state import AgentState
from src.prompts import TEXT2SQL_PROMPT
from src.llm import get_llm
from src.progress import report


def text2sql_node(state: AgentState) -> dict:
    retry = state.get("retry_count", 0)
    if retry > 0:
        report(f"🔁 SQL 报错，正在第 {retry} 次修正重试...")
    else:
        report("✍️ 正在生成 SQL 查询语句...")
    query = state["user_query"]
    schema = state.get("retrieved_schema", "")
    error_msg = state.get("error_msg", "")

    error_context = ""
    if error_msg:
        error_context = f"## 上一次生成的SQL执行报错，请修正：\n{error_msg}\n\n"

    prompt = TEXT2SQL_PROMPT.format(
        schema=schema, query=query, error_context=error_context
    )

    llm = get_llm(temperature=0.0)
    response = llm.invoke(prompt)
    sql = response.content.strip()

    # strip markdown code fences if present
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[-1]
        if sql.endswith("```"):
            sql = sql[:-3]
        sql = sql.strip()

    return {"sql_query": sql, "error_msg": ""}
