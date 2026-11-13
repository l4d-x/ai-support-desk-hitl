import pytest

from tests.conftest import TICKET


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/ticket"),
        ("post", "/status"),
        ("get", "/queue"),
        ("post", "/review/abc"),
        ("get", "/ticket/abc"),
    ],
)
def test_endpoints_require_api_key(make_client, method, path):
    client = make_client(authed=False)
    assert getattr(client, method)(path).status_code == 401


def test_wrong_api_key_is_rejected(make_client):
    client = make_client(authed=False)
    res = client.get("/queue", headers={"X-API-Key": "nope"})
    assert res.status_code == 401


def test_health_is_public(make_client):
    assert make_client(authed=False).get("/health").status_code == 200


def test_fails_closed_when_api_key_is_not_configured(make_client, monkeypatch):
    client = make_client(authed=False)
    monkeypatch.setenv("API_KEY", "")
    from src.config import get_settings

    get_settings.cache_clear()

    # Even a request that "matches" an empty key must not get through.
    assert client.get("/queue", headers={"X-API-Key": ""}).status_code == 503
    assert client.get("/queue").status_code == 503


def test_per_email_daily_limit(make_client):
    client = make_client(env={"EMAIL_DAILY_LIMIT": 2})

    assert client.post("/ticket", json=TICKET).status_code == 200
    assert client.post("/ticket", json=TICKET).status_code == 200
    third = client.post("/ticket", json=TICKET)

    assert third.status_code == 429
    other = {**TICKET, "customer_email": "bob@example.com"}
    assert client.post("/ticket", json=other).status_code == 200


def test_global_daily_limit(make_client):
    client = make_client(env={"DAILY_TICKET_LIMIT": 2})

    for i in range(2):
        body = {**TICKET, "customer_email": f"user{i}@example.com"}
        assert client.post("/ticket", json=body).status_code == 200
    blocked = client.post("/ticket", json={**TICKET, "customer_email": "late@example.com"})

    assert blocked.status_code == 429
    assert "daily limit" in blocked.json()["detail"]


def test_per_minute_burst_limit(make_client):
    client = make_client(env={"MINUTE_TICKET_LIMIT": 2})
    codes = [
        client.post("/ticket", json={**TICKET, "customer_email": f"u{i}@example.com"}).status_code
        for i in range(3)
    ]
    assert codes == [200, 200, 429]


def test_input_validation(make_client):
    client = make_client()
    assert (
        client.post("/ticket", json={**TICKET, "customer_email": "not-an-email"}).status_code == 422
    )
    assert client.post("/ticket", json={**TICKET, "customer_query": "x" * 1001}).status_code == 422
    assert client.post("/ticket", json={**TICKET, "refund_amount": -5}).status_code == 422
