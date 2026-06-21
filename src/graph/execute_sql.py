import sqlparse
from sqlalchemy import text
from src.graph.state import AgentState
from src.database import get_session
from src.progress import report
from src.error_collector import capture, classify_error

FORBIDDEN_KEYWORDS = {"DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE"}
ALLOWED_STATEMENTS = {"SELECT", "EXPLAIN", "WITH"}

ERROR_HINTS = {
    "SQL_EXEC": "错误类型：数据库执行错误。请检查字段名拼写、表名是否正确。",
    "SQL_PARSE": "错误类型：SQL语法错误。请检查SQL语句结构。",
    "SQL_FORBIDDEN": "错误类型：安全拦截。仅允许只读SELECT查询。",
    "SQL_REVIEW_REJECT": "错误类型：审查未通过。请根据审查意见修正SQL。",
    "LLM_EMPTY": "错误类型：模型返回空。请重试。",
    "LLM_FORMAT": "错误类型：模型返回格式错误。请检查输出格式要求。",
}


def _validate_sql(sql: str):
    sql = sql.strip()
    if not sql:
        raise ValueError("SQL 语句为空")

    clean = sql.rstrip(";")
    stmts = sqlparse.parse(clean)
    if not stmts:
        raise ValueError("无法解析SQL语句")

    for stmt in stmts:
        if not stmt.tokens:
            continue
        first_keyword = None
        for token in stmt.tokens:
            if token.ttype in (sqlparse.tokens.Keyword, sqlparse.tokens.Keyword.DML, sqlparse.tokens.Keyword.DDL):
                first_keyword = token.value.upper()
                break

        if first_keyword is None:
            raise ValueError("无法识别SQL语句类型")

        if first_keyword not in ALLOWED_STATEMENTS:
            raise ValueError(f"安全拦截：不允许执行 {first_keyword} 语句，仅允许 SELECT 查询")

        sql_upper = str(stmt).upper()
        for kw in FORBIDDEN_KEYWORDS:
            if kw in sql_upper:
                raise ValueError(f"安全拦截：SQL中包含危险关键字 {kw}")


def execute_sql_node(state: AgentState) -> dict:
    report("⚡ 正在安全校验并执行查询...")
    sql = state["sql_query"]
    retry_count = state.get("retry_count", 0)

    try:
        _validate_sql(sql)
    except ValueError as e:
        code = classify_error(e, "execute_sql", sql)
        hint = ERROR_HINTS.get(code, "")
        capture("execute_sql", e, {"user_query": state.get("user_query", ""), "sql_query": sql, "retry_count": retry_count})
        return {
            "sql_result": None,
            "sql_columns": None,
            "error_msg": f"{hint}\n详情：{e}",
            "error_code": code,
            "retry_count": retry_count + 1,
        }

    session = get_session()
    try:
        result = session.execute(text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        session.commit()
    except Exception as e:
        session.rollback()
        code = classify_error(e, "execute_sql", sql)
        hint = ERROR_HINTS.get(code, "")
        capture("execute_sql", e, {"user_query": state.get("user_query", ""), "sql_query": sql, "retry_count": retry_count})
        return {
            "sql_result": None,
            "sql_columns": None,
            "error_msg": f"{hint}\n详情：{e}",
            "error_code": code,
            "retry_count": retry_count + 1,
        }
    finally:
        session.close()

    data = [dict(zip(columns, row)) for row in rows]
    return {
        "sql_result": data,
        "sql_columns": columns,
        "error_msg": "",
        "error_code": "",
        "retry_count": 0,
    }
