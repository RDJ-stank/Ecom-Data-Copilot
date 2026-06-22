import os
import httpx
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from langchain_openai import ChatOpenAI
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, LLM_TEMPERATURE

os.environ["LANGCHAIN_OPENAI_TCP_KEEPALIVE"] = "0"

LLM_TIMEOUT = 25  # seconds — hard thread-level cap per LLM call


def _invoke_with_timeout(llm, prompt, timeout=LLM_TIMEOUT):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(llm.invoke, prompt)
        return future.result(timeout=timeout)


def get_llm(temperature=None):
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        max_retries=0,
        timeout=LLM_TIMEOUT,
        request_timeout=LLM_TIMEOUT,
    )


def invoke_llm(prompt, temperature=None, timeout=None):
    llm = get_llm(temperature=temperature)
    try:
        return _invoke_with_timeout(llm, prompt, timeout or LLM_TIMEOUT)
    except FutureTimeout:
        raise TimeoutError(f"LLM API 调用超时（>{timeout or LLM_TIMEOUT}秒），请重试")
    except Exception:
        raise
