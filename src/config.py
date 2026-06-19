import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ecom.db")
CHROMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma")

LLM_TEMPERATURE = 0.1
MAX_RETRY_COUNT = 3
