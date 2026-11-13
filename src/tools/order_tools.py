"""Sample order store + refund eligibility rules (SQLite dev fallback; Postgres comes in step 2)."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing

from src.config import get_settings

SAMPLE_ORDERS = [
    ("ORD001", "alice@example.com", "Wireless Headphones", 89.99, "DELIVERED"),
    ("ORD002", "bob@example.com", "Mechanical Keyboard", 129.99, "SHIPPING"),
    ("ORD003", "carol@example.com", "USB-C Hub", 45.00, "DELIVERED"),
    ("ORD004", "dave@example.com", "Webcam HD", 75.00, "CANCELLED"),
    ("ORD005", "eve@example.com", "Laptop Stand", 55.00, "DELIVERED"),
]

_initialized: set[str] = set()


def _connect() -> sqlite3.Connection:
    path = get_settings().orders_db_path
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return sqlite3.connect(path)


def init_db() -> None:
    """Create the orders table and seed sample rows. Idempotent."""
    path = get_settings().orders_db_path
    with closing(_connect()) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_email TEXT,
                product_name TEXT,
                purchase_price REAL,
                status TEXT
            )"""
        )
        conn.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?)", SAMPLE_ORDERS)
        conn.commit()
    _initialized.add(path)


def get_order(order_id: str) -> dict | None:
    if get_settings().orders_db_path not in _initialized:
        init_db()
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT order_id, customer_email, product_name, purchase_price, status "
            "FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "order_id": row[0],
        "customer_email": row[1],
        "product_name": row[2],
        "purchase_price": row[3],
        "status": row[4],
    }


def check_refund_eligibility(order_id: str, refund_amount: float, customer_email: str) -> dict:
    """Rules: order exists AND belongs to this email, is DELIVERED, 0 < amount <= price."""
    if refund_amount is None or refund_amount <= 0:
        return {"eligible": False, "reason": "Refund amount must be greater than zero."}

    order = get_order(order_id)
    # Same message for "no such order" and "someone else's order" so order ids can't be probed.
    if not order or order["customer_email"].lower() != customer_email.strip().lower():
        return {"eligible": False, "reason": "No order with that ID was found for this email."}

    if order["status"] != "DELIVERED":
        return {
            "eligible": False,
            "reason": f"Order status is {order['status']}. "
            "Refunds only allowed for DELIVERED orders.",
        }

    if refund_amount > order["purchase_price"]:
        return {
            "eligible": False,
            "reason": f"Refund amount ${refund_amount} exceeds purchase price "
            f"${order['purchase_price']}.",
        }

    return {
        "eligible": True,
        "reason": "Order is eligible for refund. Requires manager approval.",
        "order": order,
    }
