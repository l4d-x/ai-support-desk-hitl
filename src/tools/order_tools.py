import sqlite3
import os

DB_PATH = "data/orders.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_email TEXT,
            product_name TEXT,
            purchase_price REAL,
            status TEXT
        )
    ''')

    # Sample orders
    sample_orders = [
        ("ORD001", "alice@example.com", "Wireless Headphones", 89.99, "DELIVERED"),
        ("ORD002", "bob@example.com", "Mechanical Keyboard", 129.99, "SHIPPING"),
        ("ORD003", "carol@example.com", "USB-C Hub", 45.00, "DELIVERED"),
        ("ORD004", "dave@example.com", "Webcam HD", 75.00, "CANCELLED"),
        ("ORD005", "eve@example.com", "Laptop Stand", 55.00, "DELIVERED"),
    ]

    cursor.executemany('''
        INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?)
    ''', sample_orders)

    conn.commit()
    conn.close()
    print("Orders DB initialized.")

def get_order(order_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "order_id": row[0],
        "customer_email": row[1],
        "product_name": row[2],
        "purchase_price": row[3],
        "status": row[4]
    }

def check_refund_eligibility(order_id: str, refund_amount: float):
    order = get_order(order_id)

    if not order:
        return {"eligible": False, "reason": "Order does not exist."}

    if order["status"] != "DELIVERED":
        return {"eligible": False, "reason": f"Order status is {order['status']}. Refunds only allowed for DELIVERED orders."}

    if refund_amount > order["purchase_price"]:
        return {"eligible": False, "reason": f"Refund amount ${refund_amount} exceeds purchase price ${order['purchase_price']}."}

    return {"eligible": True, "reason": "Order is eligible for refund. Requires manager approval.", "order": order}

# Run on import
init_db()