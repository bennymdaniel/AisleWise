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
            aisle TEXT NOT NULL,
            description TEXT
        )
        """
    )

    existing_columns = [row[1] for row in db.execute("PRAGMA table_info(products)").fetchall()]
    if "description" not in existing_columns:
        db.execute("ALTER TABLE products ADD COLUMN description TEXT")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_accounts (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY,
            worker_email TEXT,
            product_id INTEGER,
            action TEXT,
            timestamp TEXT
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_chats (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            user_message TEXT,
            bot_response TEXT,
            timestamp TEXT
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_queries (
            id INTEGER PRIMARY KEY,
            query TEXT,
            response TEXT,
            timestamp TEXT
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
            ("Milk", "Dairy", 2.99, 12, "A1", "Fresh whole milk.") ,
            ("Bread", "Bakery", 1.99, 8, "B2", "Sliced white sandwich bread."),
            ("Eggs", "Dairy", 3.49, 4, "A1", "Carton of a dozen eggs."),
            ("Coffee", "Beverages", 9.99, 3, "C5", "Ground coffee beans, 12 oz."),
            ("Apples", "Produce", 0.99, 15, "D3", "Red apples, sold each."),
            ("Coca-Cola", "Beverages", 1.49, 7, "C5", "330ml can of soft drink."),
            ("Granola Bar", "Snacks", 0.89, 10, "E1", "Healthy oat and fruit snack."),
            ("Orange Juice", "Beverages", 4.99, 5, "C6", "Fresh squeezed orange juice."),
            ("Frozen Pizza", "Frozen Foods", 6.99, 6, "F2", "Family-size frozen pizza."),
            ("Shampoo", "Personal Care", 5.99, 9, "G3", "Daily care shampoo, 250ml."),
            ("Dish Soap", "Household", 2.49, 12, "H1", "Liquid soap for dishes."),
        ]
        for product in sample_products:
            db.execute(
                "INSERT INTO products (name, category, price, stock, aisle, description) VALUES (?, ?, ?, ?, ?, ?)",
                product
            )

    # Seed sample worker accounts if none exist
    worker_count = db.execute("SELECT COUNT(1) FROM worker_accounts").fetchone()[0]
    if worker_count == 0:
        sample_workers = [
            ("John Doe", "john@example.com", "Active"),
            ("Jane Smith", "jane@example.com", "Active"),
            ("Bob Brown", "bob@example.com", "Inactive")
        ]
        for w in sample_workers:
            db.execute(
                "INSERT OR IGNORE INTO worker_accounts (name, email, status) VALUES (?, ?, ?)",
                w
            )

    db.commit()


def init_app(app):
    db_path = app.config["DATABASE"]
    folder = os.path.dirname(db_path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    with app.app_context():
        init_db()
