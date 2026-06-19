from langchain_core.messages import AIMessage
from src.graph.state import AgentState
from src.prompts import ROUTER_PROMPT
from src.llm import get_llm


def router_node(state: AgentState) -> dict:
    query = state["user_query"]
    llm = get_llm(temperature=0.0)
    prompt = ROUTER_PROMPT.format(user_query=query)
    response = llm.invoke(prompt)
    intent = response.content.strip().lower()

    if "chat" in intent:
        chat_llm = get_llm(temperature=0.7)
        chat_response = chat_llm.invoke(
            f"用户说：{query}\n你是电商数据助手，请友好简短地回复。"
        )
        return {
            "intent": "chat",
            "messages": [AIMessage(content=chat_response.content)],
        }
    return {"intent": "query"}
