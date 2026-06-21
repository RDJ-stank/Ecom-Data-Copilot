import httpx
from langchain_openai import ChatOpenAI
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, LLM_TEMPERATURE

LLM_TIMEOUT = 20  # seconds per API call

_default_client = None


def _get_http_client():
    global _default_client
    if _default_client is None:
        _default_client = httpx.Client(
            timeout=httpx.Timeout(LLM_TIMEOUT, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=2, max_connections=10),
        )
    return _default_client


def get_llm(temperature=None):
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        max_retries=0,
        http_client=_get_http_client(),
    )
