from langgraph.graph import StateGraph, END
from src.graph.state import AgentState
from src.graph.router import router_node
from src.graph.schema_rag import schema_rag_node
from src.graph.text2sql import text2sql_node
from src.graph.execute_sql import execute_sql_node
from src.graph.generate_chart import generate_chart_node
from src.config import MAX_RETRY_COUNT


def route_intent(state: AgentState) -> str:
    if state.get("intent") == "chat":
        return "end"
    return "schema_rag"


def route_execute(state: AgentState) -> str:
    error = state.get("error_msg", "")
    retry = state.get("retry_count", 0)
    if not error:
        return "generate_chart"
    if retry < MAX_RETRY_COUNT:
        return "text2sql"
    return "end"


def build_workflow() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("schema_rag", schema_rag_node)
    workflow.add_node("text2sql", text2sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("generate_chart", generate_chart_node)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges(
        "router",
        route_intent,
        {
            "end": END,
            "schema_rag": "schema_rag",
        },
    )

    workflow.add_edge("schema_rag", "text2sql")
    workflow.add_edge("text2sql", "execute_sql")

    workflow.add_conditional_edges(
        "execute_sql",
        route_execute,
        {
            "generate_chart": "generate_chart",
            "text2sql": "text2sql",
            "end": END,
        },
    )

    workflow.add_edge("generate_chart", END)

    return workflow.compile()
