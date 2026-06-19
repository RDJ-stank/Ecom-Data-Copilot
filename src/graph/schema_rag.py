from src.graph.state import AgentState
from src.chromadb_setup import query_schema


def schema_rag_node(state: AgentState) -> dict:
    user_query = state["user_query"]
    schema_str = query_schema(user_query, n_results=3)
    if not schema_str:
        schema_str = "No matching table schema found. Please check database."
    return {"retrieved_schema": schema_str}
