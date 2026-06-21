from typing import TypedDict, Annotated, Optional, List
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_query: str
    intent: str
    retrieved_schema: str
    pruned_schema: str
    sql_query: str
    sql_result: Optional[List[dict]]
    sql_columns: Optional[List[str]]
    error_msg: str
    error_code: str
    retry_count: int
    chart_config: Optional[dict]
    insight: str
    needs_review: bool
    review_verdict: str
    review_issues: List[str]
