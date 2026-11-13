"""Environment-driven configuration. Nothing here talks to the network at import time."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # no-op if there is no .env (e.g. on Render / Streamlit Cloud)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
COLLECTION_NAME = "support_kb"

# Groq retired llama-3.3-70b-versatile; both models are overridable via env.
DEFAULT_LLM_MODEL = "openai/gpt-oss-120b"
DEFAULT_JUDGE_MODEL = "qwen/qwen3.8-27b"  # different family from the generator, used by eval only
DEFAULT_GUARD_MODEL = "openai/gpt-oss-safeguard-20b"  # policy classifier for injection screening


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None
    llm_model: str
    judge_model: str
    qdrant_url: str | None
    qdrant_api_key: str | None
    confidence_threshold: float
    kb_dir: str
    orders_db_path: str
    database_url: str | None
    api_key: str | None
    daily_ticket_limit: int  # global, all customers: protects the LLM quota
    email_daily_limit: int  # per customer email
    minute_ticket_limit: int  # global burst limit (Groq free tier is ~30 requests/min)
    guard_enabled: bool
    guard_model: str


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        groq_api_key=_clean(os.getenv("GROQ_API_KEY")),
        llm_model=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
        judge_model=os.getenv("JUDGE_MODEL", DEFAULT_JUDGE_MODEL),
        qdrant_url=_clean(os.getenv("QDRANT_URL")),
        qdrant_api_key=_clean(os.getenv("QDRANT_API_KEY")),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.50")),
        kb_dir=os.getenv("KB_DIR", "kb"),
        orders_db_path=os.getenv("ORDERS_DB_PATH", "data/orders.db"),
        database_url=_clean(os.getenv("DATABASE_URL")),
        api_key=_clean(os.getenv("API_KEY")),
        daily_ticket_limit=int(os.getenv("DAILY_TICKET_LIMIT", "200")),
        email_daily_limit=int(os.getenv("EMAIL_DAILY_LIMIT", "10")),
        minute_ticket_limit=int(os.getenv("MINUTE_TICKET_LIMIT", "12")),
        guard_enabled=os.getenv("INJECTION_GUARD_ENABLED", "true").strip().lower()
        not in ("0", "false", "no", "off"),
        guard_model=os.getenv("GUARD_MODEL", DEFAULT_GUARD_MODEL),
    )
