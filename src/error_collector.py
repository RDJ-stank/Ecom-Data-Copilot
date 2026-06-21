"""ErrorCollector — writes structured error snapshots to data/errors.jsonl.
CLAUDE.md rule: on session start, read errors.jsonl and auto-diagnose.
"""
import json, os, traceback
from datetime import datetime

ERROR_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "errors.jsonl")


ERROR_CODES = {
    "SQL_PARSE": "SQL 语法无法解析",
    "SQL_FORBIDDEN": "SQL 包含禁止关键字",
    "SQL_EXEC": "数据库执行错误",
    "SQL_REVIEW_REJECT": "SQL Reviewer 拦截",
    "CHART_JSON": "图表 JSON 解析失败",
    "LLM_EMPTY": "LLM 返回空内容",
    "LLM_FORMAT": "LLM 返回格式错误",
    "UNKNOWN": "未知错误",
}


def classify_error(exc: Exception, node: str, sql: str = "") -> str:
    """Map exception to error code."""
    msg = str(exc).upper()
    if "SQLITE" in msg or "OPERATIONAL" in msg.upper() or "no such" in msg.lower():
        return "SQL_EXEC"
    if "PARSE" in msg or "syntax" in msg.lower():
        return "SQL_PARSE"
    if "禁止" in msg or "拦截" in msg or "FORBIDDEN" in msg:
        return "SQL_FORBIDDEN"
    if "JSON" in msg or "decode" in msg.lower() or "parse" in msg.lower():
        return "CHART_JSON"
    if not sql and ("empty" in msg.lower()):
        return "LLM_EMPTY"
    if "format" in msg.lower() or "格式" in msg:
        return "LLM_FORMAT"
    return "UNKNOWN"


def capture(node: str, error: Exception, context: dict):
    """Write structured error snapshot."""
    code = classify_error(error, node, context.get("sql_query", ""))
    record = {
        "ts": datetime.now().isoformat(),
        "code": code,
        "code_desc": ERROR_CODES.get(code, "未知"),
        "node": node,
        "error": str(error),
        "traceback": traceback.format_exc()[-500:],
        "context": {
            "user_query": context.get("user_query", "")[:200],
            "sql_query": context.get("sql_query", "")[:500],
            "retry_count": context.get("retry_count", 0),
        },
    }
    os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_recent_errors(limit=10):
    """Read recent errors from the log."""
    if not os.path.exists(ERROR_LOG_PATH):
        return []
    errors = []
    with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                errors.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return errors[-limit:]
