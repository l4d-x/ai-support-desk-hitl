import pytest

from src.config import get_settings
from src.tools import order_tools
from src.tools.order_tools import check_refund_eligibility


@pytest.fixture(autouse=True)
def temp_orders_db(tmp_path, monkeypatch):
    # Nested dir that does not exist: the old code crashed on a fresh clone for this reason.
    monkeypatch.setenv("ORDERS_DB_PATH", str(tmp_path / "nested" / "orders.db"))
    get_settings.cache_clear()
    order_tools._initialized.clear()
    yield
    get_settings.cache_clear()
    order_tools._initialized.clear()


def test_eligible_refund():
    r = check_refund_eligibility("ORD001", 50.0, "alice@example.com")
    assert r["eligible"] is True
    assert r["order"]["product_name"] == "Wireless Headphones"


def test_email_match_is_case_insensitive():
    assert check_refund_eligibility("ORD001", 50.0, " Alice@Example.com ")["eligible"] is True


def test_refund_on_someone_elses_order_is_denied_without_leaking():
    wrong_owner = check_refund_eligibility("ORD001", 50.0, "mallory@example.com")
    no_such_order = check_refund_eligibility("ORD999", 50.0, "mallory@example.com")

    assert wrong_owner["eligible"] is False
    assert wrong_owner["reason"] == no_such_order["reason"]


@pytest.mark.parametrize("amount", [0, -5])
def test_non_positive_amount_is_denied(amount):
    assert check_refund_eligibility("ORD001", amount, "alice@example.com")["eligible"] is False


def test_amount_above_price_is_denied():
    r = check_refund_eligibility("ORD001", 500.0, "alice@example.com")
    assert r["eligible"] is False
    assert "exceeds" in r["reason"]


@pytest.mark.parametrize(
    ("order_id", "email"),
    [("ORD002", "bob@example.com"), ("ORD004", "dave@example.com")],
)
def test_non_delivered_orders_are_denied(order_id, email):
    r = check_refund_eligibility(order_id, 10.0, email)
    assert r["eligible"] is False
    assert "DELIVERED" in r["reason"]
