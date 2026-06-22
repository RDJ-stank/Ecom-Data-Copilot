from langchain_core.messages import AIMessage
from src.graph.state import AgentState
from src.prompts import ROUTER_PROMPT
from src.llm import invoke_llm
from src.progress import report

DANGEROUS_KEYWORDS = {
    "删除", "删掉", "清除", "清空", "删了", "移除",
    "修改", "更改", "改成", "改为", "更新", "变更",
    "插入", "新增", "添加记录", "插入数据",
    "drop", "delete", "update", "insert", "truncate", "alter",
}


def _is_dangerous(q: str) -> bool:
    q_lower = q.lower()
    return any(kw in q_lower for kw in DANGEROUS_KEYWORDS)


def router_node(state: AgentState) -> dict:
    report("🔍 正在识别查询意图...")
    query = state["user_query"]

    if _is_dangerous(query):
        return {
            "intent": "chat",
            "messages": [AIMessage(content="抱歉，本系统仅支持只读的 SELECT 数据查询，无法执行删除、修改或插入操作。如有数据分析需求，请换一种方式描述。")],
        }

    prompt = ROUTER_PROMPT.format(user_query=query)
    try:
        response = invoke_llm(prompt, temperature=0.0)
        intent = response.content.strip().lower()
    except Exception:
        intent = "chat"

    if "chat" in intent:
        try:
            chat_response = invoke_llm(
                f"用户说：{query}\n你是电商数据助手，请友好简短地回复。",
                temperature=0.7,
            )
            return {
                "intent": "chat",
                "messages": [AIMessage(content=chat_response.content)],
            }
        except Exception:
            return {
                "intent": "chat",
                "messages": [AIMessage(content="你好！我是电商数据分析助手，可以帮你查询和分析销售数据、售后数据、用户价值等。请直接告诉我你想分析什么。")],
            }
    return {"intent": "query"}
