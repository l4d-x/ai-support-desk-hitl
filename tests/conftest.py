import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config import get_settings
from src.graph.workflow import build_graph
from src.store import MemoryStore, make_persistence

API_KEY = "test-api-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}
TICKET = {"customer_email": "alice@example.com", "customer_query": "Where is my stuff?"}


def fake_agent(escalate: bool):
    def _run(customer_query, customer_email, order_id=None, refund_amount=None):
        return {
            "draft_response": "DRAFT: thanks for your question.",
            "confidence_score": 0.42 if escalate else 0.91,
            "needs_escalation": escalate,
            "refund_eligibility": None,
            "kb_sources": ["return-policy"],
        }

    return _run


@pytest.fixture(autouse=True)
def base_env(monkeypatch):
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def make_client(monkeypatch):
    """Fresh app + in-memory persistence whose RAG agent is faked (no network, no models).

    `env` overrides settings (e.g. limits); `authed=False` omits the API key header.
    """

    def _make(escalate: bool = True, env: dict | None = None, authed: bool = True) -> TestClient:
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, str(value))
        get_settings.cache_clear()
        monkeypatch.setattr("src.graph.workflow.run_rag_agent", fake_agent(escalate))
        app = create_app(build_graph(), MemoryStore(), init_resources=False)
        return TestClient(app, headers=AUTH_HEADERS if authed else {})

    return _make


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory):
    """A real Postgres: TEST_DATABASE_URL (CI service) or a throwaway embedded server (pgserver)."""
    import os

    if url := os.getenv("TEST_DATABASE_URL"):
        yield url
        return
    try:
        import pgserver

        server = pgserver.get_server(tmp_path_factory.mktemp("pg"))
    except Exception as exc:  # not installed / cannot start on this machine
        pytest.skip(f"no Postgres available (set TEST_DATABASE_URL): {exc}")
    yield server.get_uri()
    server.cleanup()


@pytest.fixture(params=["memory", "postgres"])
def persistence(request, monkeypatch):
    """(checkpointer, store) backed by memory, then by a real Postgres."""
    url = request.getfixturevalue("pg_url") if request.param == "postgres" else None
    checkpointer, store, close = make_persistence(url)
    monkeypatch.setattr("src.graph.workflow.run_rag_agent", fake_agent(True))
    yield checkpointer, store
    close()
