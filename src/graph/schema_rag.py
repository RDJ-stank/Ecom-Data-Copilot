from src.graph.state import AgentState
from src.chromadb_setup import query_schema
from src.column_meta import prune_columns, build_pruned_ddl


def schema_rag_node(state: AgentState) -> dict:
    user_query = state["user_query"]
    schema_str = query_schema(user_query, n_results=3)
    if not schema_str:
        return {"retrieved_schema": "", "pruned_schema": ""}

    # extract table names from schema string
    tbls = _extract_tables(schema_str)
    if not tbls:
        return {"retrieved_schema": schema_str, "pruned_schema": schema_str}

    pruned = prune_columns(tbls, user_query)
    compact = build_pruned_ddl(tbls, pruned)
    return {"retrieved_schema": schema_str, "pruned_schema": compact}


def _extract_tables(schema_str: str):
    tbls = []
    for line in schema_str.split("\n"):
        line = line.strip()
        if line.startswith("Table:") or line.startswith("## Table:"):
            name = line.split(":")[-1].strip().split()[0]
            if name:
                tbls.append(name)
    return tbls
