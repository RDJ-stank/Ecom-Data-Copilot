"""SQL Reviewer — adversarial audit of generated SQL.
Only triggered for complex queries (JOIN / GROUP BY / subquery / HAVING / UNION)
to avoid wasting tokens on simple single-table SELECTs.
"""
import json
from src.graph.state import AgentState
from src.llm import invoke_llm

REVIEW_PROMPT = """Audit this SQL for correctness and safety. Report in JSON.

## User Question
{query}

## Schema
{schema}

## SQL to Audit
{sql}

## Checks
1. Semantic: Does the SQL answer the user's question correctly?
2. Columns: Are all referenced columns real (check against schema)?
3. Performance: Any missing LIMIT? Potential full-table scan?
4. Safety: Any injection risk or dangerous pattern?

Return JSON only:
{{"verdict": "approved"|"risky"|"rejected",
 "issues": ["issue1", ...] or [],
 "fix_suggestion": "..." or ""}}"""


def _is_complex(sql: str) -> bool:
    upper = sql.upper()
    complex_keywords = ["JOIN", "GROUP BY", "HAVING", "UNION"]
    has_subquery = sql.count("SELECT") > 1
    return has_subquery or any(kw in upper for kw in complex_keywords)


def needs_review(state: AgentState) -> bool:
    sql = state.get("sql_query", "")
    if not sql:
        return False
    return _is_complex(sql)


def sql_reviewer_node(state: AgentState) -> dict:
    query = state["user_query"]
    sql = state.get("sql_query", "")
    schema = state.get("pruned_schema", state.get("retrieved_schema", ""))

    try:
        prompt = REVIEW_PROMPT.format(query=query, schema=schema, sql=sql)
        response = invoke_llm(prompt, temperature=0.0)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        result = json.loads(raw)
    except Exception:
        result = {"verdict": "approved", "issues": [], "fix_suggestion": ""}

    verdict = result.get("verdict", "approved")
    issues = result.get("issues", [])
    fix = result.get("fix_suggestion", "")

    if verdict == "rejected" and fix:
        return {
            "review_verdict": verdict,
            "review_issues": issues,
            "error_msg": f"SQL Reviewer 拦截：{'; '.join(issues)}. 建议：{fix}",
        }
    if verdict == "risky" and fix:
        return {
            "review_verdict": verdict,
            "review_issues": issues,
        }
    return {"review_verdict": "approved", "review_issues": issues}
