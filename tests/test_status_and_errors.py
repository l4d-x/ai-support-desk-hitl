from tests.conftest import TICKET


def _status(client, ticket_id, email="alice@example.com"):
    return client.post("/status", json={"ticket_id": ticket_id, "customer_email": email})


def test_customer_sees_nothing_until_a_human_decides(make_client):
    client = make_client()
    tid = client.post("/ticket", json=TICKET).json()["ticket_id"]

    pending = _status(client, tid).json()
    assert pending["status"] == "escalated"
    assert pending["final_response"] is None  # the unreviewed draft must not leak

    client.post(f"/review/{tid}", json={"decision": "approve", "edited_response": "Final text"})
    done = _status(client, tid).json()
    assert done["status"] == "sent"
    assert done["final_response"] == "Final text"


def test_status_needs_the_matching_email(make_client):
    client = make_client()
    tid = client.post("/ticket", json=TICKET).json()["ticket_id"]

    assert _status(client, tid, "mallory@example.com").status_code == 404
    assert _status(client, "does-not-exist").status_code == 404
    assert _status(client, tid, " ALICE@example.com ").status_code == 200  # case/space tolerant


def test_model_failure_returns_502_and_marks_ticket_errored(make_client, monkeypatch):
    client = make_client()

    def boom(*args, **kwargs):
        raise RuntimeError("groq is down: secret internals")

    monkeypatch.setattr("src.graph.workflow.run_rag_agent", boom)
    res = client.post("/ticket", json=TICKET)

    assert res.status_code == 502
    assert "secret internals" not in res.text  # no internals leaked to the customer
    assert client.get("/queue").json() == []
