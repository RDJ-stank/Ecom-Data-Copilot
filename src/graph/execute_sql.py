import sqlparse
import pandas as pd
from sqlalchemy import text
from src.graph.state import AgentState
from src.database import get_session

FORBIDDEN_KEYWORDS = {"DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE"}
ALLOWED_STATEMENTS = {"SELECT", "EXPLAIN", "WITH"}


def _validate_sql(sql: str):
    sql = sql.strip()
    if not sql:
        raise ValueError("SQL 语句为空")

    # strip trailing semicolons for parsing
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

        # whitelist check
        if first_keyword not in ALLOWED_STATEMENTS:
            raise ValueError(f"安全拦截：不允许执行 {first_keyword} 语句，仅允许 SELECT 查询")

        # blacklist check for nested dangerous keywords
        sql_upper = str(stmt).upper()
        for kw in FORBIDDEN_KEYWORDS:
            if kw in sql_upper:
                raise ValueError(f"安全拦截：SQL中包含危险关键字 {kw}")


def execute_sql_node(state: AgentState) -> dict:
    sql = state["sql_query"]
    retry_count = state.get("retry_count", 0)

    try:
        _validate_sql(sql)
    except ValueError as e:
        return _handle_error(str(e), retry_count)

    session = get_session()
    try:
        result = session.execute(text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        session.commit()  # not strictly needed for SELECT but good practice
    except Exception as e:
        session.rollback()
        return _handle_error(f"数据库执行错误: {str(e)}", retry_count)
    finally:
        session.close()

    data = [dict(zip(columns, row)) for row in rows]
    return {
        "sql_result": data,
        "sql_columns": columns,
        "error_msg": "",
        "retry_count": 0,
    }


def _handle_error(error_str: str, retry_count: int) -> dict:
    return {
        "sql_result": None,
        "sql_columns": None,
        "error_msg": error_str,
        "retry_count": retry_count + 1,
    }
