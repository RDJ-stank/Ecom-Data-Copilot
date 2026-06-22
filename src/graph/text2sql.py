from src.graph.state import AgentState
from src.prompts import TEXT2SQL_PROMPT
from src.llm import invoke_llm
from src.progress import report
from src.error_collector import capture


def text2sql_node(state: AgentState) -> dict:
    retry = state.get("retry_count", 0)
    if retry > 0:
        report(f"🔁 SQL 报错，正在第 {retry} 次修正重试...")
    else:
        report("✍️ 正在生成 SQL 查询语句...")

    query = state["user_query"]
    schema = state.get("pruned_schema") or state.get("retrieved_schema", "")
    error_msg = state.get("error_msg", "")

    error_context = ""
    if error_msg:
        short_err = error_msg[:150]
        error_context = f"## 上一次SQL报错（请修正）：\n{short_err}\n\n"

    prompt = TEXT2SQL_PROMPT.format(
        schema=schema, query=query, error_context=error_context
    )

    try:
        response = invoke_llm(prompt, temperature=0.0)
        sql = response.content.strip()
    except Exception as e:
        capture("text2sql", e, {"user_query": query})
        return {"sql_query": "", "error_msg": f"LLM调用失败：{e}"}

    if sql.startswith("```"):
        sql = sql.split("\n", 1)[-1]
        if sql.endswith("```"):
            sql = sql[:-3]
        sql = sql.strip()

    if not sql:
        capture("text2sql", ValueError("LLM returned empty SQL"), {"user_query": query})
        return {"sql_query": "", "error_msg": "LLM 返回空SQL，请重试"}

    return {"sql_query": sql, "error_msg": "", "error_code": "", "needs_review": _is_complex(sql)}


def _is_complex(sql: str) -> bool:
    upper = sql.upper()
    complex_kw = ["JOIN", "GROUP BY", "HAVING", "UNION"]
    has_subquery = sql.count("SELECT") > 1
    return has_subquery or any(kw in upper for kw in complex_kw)
