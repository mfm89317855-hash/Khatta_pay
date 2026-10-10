"""Configuration settings for KhataTalk."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Paths
    BASE_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(BASE_DIR / ".env", override=True)
except ImportError:
    BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = os.getenv("KHATATALK_DB_PATH", str(BASE_DIR / "khatatalk.db"))

# Models
DEFAULT_LLM_MODEL = os.getenv("KHATATALK_MODEL", "qwen2.5:3b")
DEFAULT_WHISPER_MODEL = os.getenv("KHATATALK_WHISPER_MODEL", "small")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("WHISPER_API_KEY")

# Business Rules / Validation
MAX_TRANSACTION_AMOUNT = int(os.getenv("KHATATALK_MAX_AMOUNT", "1000000"))  # 1 million PKR limit for sanity check
FUZZY_MATCH_THRESHOLD = float(os.getenv("KHATATALK_FUZZY_THRESHOLD", "82.0"))
FUZZY_AMBIGUITY_MARGIN = float(os.getenv("KHATATALK_AMBIGUITY_MARGIN", "5.0"))
