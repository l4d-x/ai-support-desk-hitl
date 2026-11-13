"""The escalation queue must survive an API restart.

A "restart" is simulated by building a brand-new app + graph on top of the same persistence
objects. Runs against in-memory always, and against real Postgres when TEST_DATABASE_URL is set.
"""

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.graph.workflow import build_graph
from tests.conftest import AUTH_HEADERS, TICKET


def _boot(checkpointer, store):
    return TestClient(create_app(build_graph(checkpointer), store, False), headers=AUTH_HEADERS)


def test_pending_ticket_survives_restart_and_can_be_reviewed(persistence):
    checkpointer, store = persistence
    before = _boot(checkpointer, store)
    tid = before.post("/ticket", json=TICKET).json()["ticket_id"]
    assert [q["ticket_id"] for q in before.get("/queue").json()] == [tid]

    after = _boot(checkpointer, store)  # "restart"
    queue = after.get("/queue").json()
    assert [q["ticket_id"] for q in queue] == [tid]
    assert queue[0]["draft_response"] == "DRAFT: thanks for your question."

    res = after.post(f"/review/{tid}", json={"decision": "approve", "edited_response": "Edited"})
    assert res.json()["final_response"] == "Edited"
    assert after.get("/queue").json() == []


def test_usage_limits_survive_restart(persistence):
    _, store = persistence
    key = "email:test-persistence"

    assert store.hit(key, 2) is True
    assert store.hit(key, 2) is True
    # A new process sees the same counter, so sleeping/waking the host can't reset the cap.
    assert store.hit(key, 2) is False
