import os
from .db import get_db


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            aisle TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY,
            store_id TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
        """
    )

    admin_row = db.execute(
        "SELECT id FROM admin WHERE store_id = ?", ("admin",)
    ).fetchone()
    if admin_row is None:
        db.execute(
            "INSERT INTO admin (store_id, password) VALUES (?, ?)",
            ("admin", "password123")
        )

    product_count = db.execute("SELECT COUNT(1) FROM products").fetchone()[0]
    if product_count == 0:
        sample_products = [
            ("Milk", "Dairy", 2.99, 12, "A1"),
            ("Bread", "Bakery", 1.99, 8, "B2"),
            ("Eggs", "Dairy", 3.49, 4, "A1"),
            ("Coffee", "Beverages", 9.99, 3, "C5"),
            ("Apples", "Produce", 0.99, 15, "D3")
        ]
        for product in sample_products:
            db.execute(
                "INSERT INTO products (name, category, price, stock, aisle) VALUES (?, ?, ?, ?, ?)",
                product
            )

    db.commit()


def init_app(app):
    db_path = app.config["DATABASE"]
    folder = os.path.dirname(db_path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    with app.app_context():
        init_db()
