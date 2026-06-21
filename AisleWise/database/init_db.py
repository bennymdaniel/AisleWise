import os
from .db import get_db


def init_db():
    db = get_db()

    # Create products table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            aisle TEXT NOT NULL,
            description TEXT
        )
        """
    )

    # Check for description column
    existing_columns = [row[1] for row in db.execute("PRAGMA table_info(products)").fetchall()]
    if "description" not in existing_columns:
        db.execute("ALTER TABLE products ADD COLUMN description TEXT")

    # Rename worker_accounts to workers if it exists
    worker_accounts_exists = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='worker_accounts'").fetchone()
    if worker_accounts_exists:
        workers_exists = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workers'").fetchone()
        if not workers_exists:
            db.execute("ALTER TABLE worker_accounts RENAME TO workers")
        else:
            db.execute("DROP TABLE worker_accounts")

    # Create workers table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL
        )
        """
    )

    # Rename admin to admins if it exists
    admin_exists = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin'").fetchone()
    if admin_exists:
        admins_exists = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admins'").fetchone()
        if not admins_exists:
            db.execute("ALTER TABLE admin RENAME TO admins")
        else:
            db.execute("DROP TABLE admin")

    # Create admins table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
        """
    )

    # Create tasks table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            timestamp TEXT NOT NULL,
            FOREIGN KEY (worker_id) REFERENCES workers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )

    # Create activity_logs table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_email TEXT,
            product_id INTEGER,
            action TEXT,
            timestamp TEXT
        )
        """
    )

    # Create customer_chats table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_message TEXT,
            bot_response TEXT,
            timestamp TEXT,
            products_json TEXT
        )
        """
    )

    # Create customer_queries table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            response TEXT,
            timestamp TEXT
        )
        """
    )

    # Create display_settings table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS display_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT UNIQUE,
            is_visible INTEGER DEFAULT 1
        )
        """
    )

    # Create uploaded_files table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            upload_date TEXT
        )
        """
    )

    # Create worker_field_permissions table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_field_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT UNIQUE,
            can_view INTEGER DEFAULT 1,
            can_edit INTEGER DEFAULT 0
        )
        """
    )

    # Create worker_action_permissions table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_action_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_name TEXT UNIQUE,
            is_enabled INTEGER DEFAULT 1
        )
        """
    )

    # Seed admins table
    admin_row = db.execute(
        "SELECT id FROM admins WHERE store_id = ?", ("admin",)
    ).fetchone()
    if admin_row is None:
        db.execute(
            "INSERT INTO admins (store_id, password) VALUES (?, ?)",
            ("admin", "password123")
        )

    # Seed display_settings table with default product fields
    default_fields = ["name", "category", "price", "stock", "aisle", "description"]
    for field in default_fields:
        db.execute(
            "INSERT OR IGNORE INTO display_settings (field_name, is_visible) VALUES (?, 1)",
            (field,)
        )

    # Seed worker_field_permissions table with default product fields
    # Stock is typically editable by worker, other fields are read-only/view-only by default.
    for field in default_fields:
        can_edit = 1 if field == "stock" else 0
        db.execute(
            "INSERT OR IGNORE INTO worker_field_permissions (field_name, can_view, can_edit) VALUES (?, 1, ?)",
            (field, can_edit)
        )

    # Seed worker_action_permissions table with default actions
    default_actions = [
        "View Inventory",
        "Update Stock",
        "Restock Products",
        "View Product Details",
        "View Low Stock Alerts",
        "View Analytics",
        "View Product Metadata"
    ]
    for action in default_actions:
        db.execute(
            "INSERT OR IGNORE INTO worker_action_permissions (action_name, is_enabled) VALUES (?, 1)",
            (action,)
        )


    # Seed products table
    product_count = db.execute("SELECT COUNT(1) FROM products").fetchone()[0]
    if product_count == 0:
        sample_products = [
            ("Milk", "Dairy", 90.00, 12, "A1", "Fresh whole milk, 1 Liter."),
            ("Bread", "Bakery", 50.00, 8, "B2", "Sliced white sandwich bread, 400g."),
            ("Eggs", "Dairy", 60.00, 4, "A1", "Carton of a dozen fresh white eggs."),
            ("Coffee", "Beverages", 120.00, 3, "C5", "Ground dark roast coffee beans, 12 oz."),
            ("Apples", "Produce", 100.00, 15, "D3", "Crisp red apples, 1 kg pack."),
            ("Coca-Cola", "Beverages", 60.00, 7, "C5", "330ml can of carbonated soft drink."),
            ("Granola Bar", "Snacks", 30.00, 10, "E1", "Healthy oat and fruit snack bar, 40g."),
            ("Orange Juice", "Beverages", 40.00, 5, "C6", "Pure fresh squeezed orange juice, 500ml."),
            ("Frozen Pizza", "Frozen Foods", 130.00, 2, "F2", "Family-size frozen cheese pizza, 400g."),
            ("Shampoo", "Personal Care", 120.00, 9, "G3", "Daily care moisturizing shampoo, 250ml."),
            ("Dish Soap", "Household", 60.00, 12, "H1", "Liquid degreasing soap for dishes, 500ml."),
        ]
        for product in sample_products:
            db.execute(
                "INSERT INTO products (name, category, price, stock, aisle, description) VALUES (?, ?, ?, ?, ?, ?)",
                product
            )

    # Seed workers table with approved Gmail accounts
    worker_count = db.execute("SELECT COUNT(1) FROM workers").fetchone()[0]
    if worker_count == 0:
        sample_workers = [
            ("John Doe", "john.doe@gmail.com", "Active"),
            ("Jane Smith", "jane.smith@gmail.com", "Active"),
            ("Bob Brown", "bob.brown@gmail.com", "Inactive")
        ]
        for w in sample_workers:
            db.execute(
                "INSERT OR IGNORE INTO workers (name, email, status) VALUES (?, ?, ?)",
                w
            )

    db.commit()
