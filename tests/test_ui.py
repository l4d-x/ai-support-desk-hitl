"""Smoke tests: the Streamlit pages render and behave, with the API client stubbed out."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

UI = str(Path(__file__).resolve().parent.parent / "ui")


@pytest.fixture(autouse=True)
def ui_on_path(monkeypatch):
    monkeypatch.syspath_prepend(UI)
    sys.modules.pop("api", None)  # ui/api.py, not src/api
    monkeypatch.setenv("AGENT_PASSWORD", "hunter2")
    yield
    sys.modules.pop("api", None)


def _stub_api(monkeypatch, responses):
    import api

    calls = []

    def fake_call(method, path, **kwargs):
        calls.append((method, path, kwargs.get("json")))
        return responses[(method, path.split("/")[1] if path.startswith("/review") else path)]

    monkeypatch.setattr(api, "call", fake_call)
    return calls


def test_customer_page_auto_answer(monkeypatch):
    calls = _stub_api(
        monkeypatch,
        {("POST", "/ticket"): {"ticket_id": "t1", "status": "sent", "final_response": "3-5 days"}},
    )
    at = AppTest.from_file(f"{UI}/Home.py").run()
    assert not at.exception

    at.text_input[0].set_value("alice@example.com")
    at.text_area[0].set_value("How long is shipping?")
    at.button[0].click().run()

    assert not at.exception
    assert any("3-5 days" in m.value for m in at.markdown)
    assert calls[0][2]["customer_email"] == "alice@example.com"


def test_customer_page_requires_email_and_question(monkeypatch):
    calls = _stub_api(monkeypatch, {})
    at = AppTest.from_file(f"{UI}/Home.py").run()
    at.button[0].click().run()

    assert at.warning
    assert calls == []


def test_agent_page_is_locked_until_password(monkeypatch):
    queue = [
        {
            "ticket_id": "t1",
            "customer_email": "alice@example.com",
            "customer_query": "refund please",
            "draft_response": "draft",
            "confidence_score": 0.4,
            "refund_eligibility": None,
            "kb_sources": ["refund-process"],
        }
    ]
    calls = _stub_api(monkeypatch, {("GET", "/queue"): queue})

    at = AppTest.from_file(f"{UI}/pages/1_Agent_Dashboard.py").run()
    assert not at.exception
    assert calls == []  # nothing fetched before login
    at.text_input[0].set_value("wrong")
    at.button[0].click().run()
    assert at.error and calls == []

    at.text_input[0].set_value("hunter2")
    at.button[0].click().run()
    assert not at.exception
    assert calls == [("GET", "/queue", None)]
    assert any("refund please" in e.label for e in at.expander)


def test_agent_page_locked_when_password_not_configured(monkeypatch):
    monkeypatch.setenv("AGENT_PASSWORD", "")
    calls = _stub_api(monkeypatch, {})
    at = AppTest.from_file(f"{UI}/pages/1_Agent_Dashboard.py").run()

    assert at.error and calls == []
