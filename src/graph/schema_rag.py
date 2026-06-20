from src.graph.state import AgentState
from src.chromadb_setup import query_schema
from src.progress import report


def schema_rag_node(state: AgentState) -> dict:
    report("📚 正在检索相关数据表结构...")
    user_query = state["user_query"]
    schema_str = query_schema(user_query, n_results=3)
    if not schema_str:
        schema_str = "No matching table schema found. Please check database."
    return {"retrieved_schema": schema_str}
