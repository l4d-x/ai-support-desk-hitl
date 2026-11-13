from tests.conftest import TICKET


def test_high_confidence_ticket_is_auto_sent(make_client):
    client = make_client(escalate=False)
    body = client.post("/ticket", json=TICKET).json()

    assert body["status"] == "sent"
    assert body["final_response"] == "DRAFT: thanks for your question."
    assert client.get("/queue").json() == []


def test_low_confidence_ticket_waits_in_queue(make_client):
    client = make_client()
    body = client.post("/ticket", json=TICKET).json()

    assert body["status"] == "escalated"
    assert body["final_response"] is None  # nothing is sent until a human decides
    queue = client.get("/queue").json()
    assert [q["ticket_id"] for q in queue] == [body["ticket_id"]]
    assert queue[0]["draft_response"] == "DRAFT: thanks for your question."


def test_approve_sends_the_draft(make_client):
    client = make_client()
    tid = client.post("/ticket", json=TICKET).json()["ticket_id"]

    res = client.post(f"/review/{tid}", json={"decision": "approve"}).json()

    assert res["status"] == "sent"
    assert res["final_response"] == "DRAFT: thanks for your question."
    assert client.get("/queue").json() == []


def test_approve_with_edit_sends_the_edited_text(make_client):
    """Regression: the old as_node='human_review' resume dropped the manager's edit."""
    client = make_client()
    tid = client.post("/ticket", json=TICKET).json()["ticket_id"]

    res = client.post(
        f"/review/{tid}", json={"decision": "approve", "edited_response": "Edited by manager"}
    ).json()

    assert res["status"] == "sent"
    assert res["final_response"] == "Edited by manager"
    state = client.get(f"/ticket/{tid}").json()
    assert state["human_decision"] == "approve"
    assert state["human_edited_response"] == "Edited by manager"


def test_reject_sends_rejection_notice(make_client):
    client = make_client()
    tid = client.post("/ticket", json=TICKET).json()["ticket_id"]

    res = client.post(f"/review/{tid}", json={"decision": "reject"}).json()

    assert res["status"] == "rejected"
    assert "cannot be processed" in res["final_response"]


def test_ticket_cannot_be_reviewed_twice(make_client):
    client = make_client()
    tid = client.post("/ticket", json=TICKET).json()["ticket_id"]
    client.post(f"/review/{tid}", json={"decision": "approve"})

    again = client.post(f"/review/{tid}", json={"decision": "reject"})

    assert again.status_code == 409


def test_auto_sent_ticket_cannot_be_reviewed(make_client):
    client = make_client(escalate=False)
    tid = client.post("/ticket", json=TICKET).json()["ticket_id"]

    assert client.post(f"/review/{tid}", json={"decision": "approve"}).status_code == 409


def test_unknown_ticket_is_404(make_client):
    client = make_client()

    assert client.get("/ticket/nope").status_code == 404
    assert client.post("/review/nope", json={"decision": "approve"}).status_code == 404


def test_invalid_decision_is_rejected(make_client):
    client = make_client()
    tid = client.post("/ticket", json=TICKET).json()["ticket_id"]

    assert client.post(f"/review/{tid}", json={"decision": "maybe"}).status_code == 422


def test_health(make_client):
    assert make_client().get("/health").json() == {"status": "ok"}
