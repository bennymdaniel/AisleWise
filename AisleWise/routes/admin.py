from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database.db import get_db, query_db
from datetime import datetime

admin_bp = Blueprint("admin", __name__, template_folder="../templates")


def admin_login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("admin_id") is None:
            return redirect(url_for("admin.login"))
        return view(**kwargs)
    return wrapped_view


@admin_bp.route("/")
def index():
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("admin.login"))


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        store_id = request.form.get("store_id", "").strip()
        password = request.form.get("password", "").strip()
        
        # Verify against updated 'admins' table
        admin = query_db(
            "SELECT * FROM admins WHERE store_id = ? AND password = ?",
            (store_id, password),
            one=True
        )
        if admin is None:
            error = "Invalid store ID or password."
        else:
            session.clear()
            session["admin_id"] = admin["id"]
            session["store_id"] = admin["store_id"]
            return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html", error=error)


@admin_bp.route("/dashboard")
@admin_login_required
def dashboard():
    total_products = query_db("SELECT COUNT(1) AS count FROM products", one=True)["count"]
    
    out_of_stock = query_db("SELECT COUNT(1) AS count FROM products WHERE stock = 0", one=True)["count"]
    
    active_workers = query_db("SELECT COUNT(1) AS count FROM workers WHERE status = 'Active'", one=True)["count"]
    
    pending_tasks = query_db("SELECT COUNT(1) AS count FROM tasks WHERE status = 'Pending'", one=True)["count"]
    
    low_stock = query_db(
        "SELECT * FROM products WHERE stock < 5 ORDER BY stock ASC"
    )
    
    return render_template(
        "admin/dashboard.html",
        total_products=total_products,
        out_of_stock=out_of_stock,
        active_workers=active_workers,
        pending_tasks=pending_tasks,
        low_stock=low_stock
    )


# ==========================================
# PRODUCT CRUD
# ==========================================

@admin_bp.route("/inventory", methods=["GET", "POST"])
@admin_login_required
def inventory():
    if request.method == "POST":
        product_id = request.form.get("product_id")
        stock = request.form.get("stock")
        if product_id and stock is not None:
            try:
                stock_value = int(stock)
                if stock_value < 0:
                    flash("Stock level cannot be negative.")
                else:
                    db = get_db()
                    db.execute(
                        "UPDATE products SET stock = ? WHERE id = ?",
                        (stock_value, product_id)
                    )
                    db.commit()
                    flash("Stock updated successfully.")
            except ValueError:
                flash("Stock must be a valid number.")
        return redirect(url_for("admin.inventory"))

    products = query_db("SELECT * FROM products ORDER BY id")
    return render_template("admin/inventory.html", products=products)


@admin_bp.route("/add-product", methods=["GET", "POST"])
@admin_login_required
def add_product():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        price = request.form.get("price", "").strip()
        stock = request.form.get("stock", "").strip()
        aisle = request.form.get("aisle", "").strip()
        description = request.form.get("description", "").strip()

        if not (name and category and price and stock and aisle):
            error = "Name, Category, Price, Stock, and Aisle fields are required."
        else:
            try:
                price_value = float(price)
                stock_value = int(stock)
                if price_value < 0 or stock_value < 0:
                    error = "Price and stock levels cannot be negative."
                else:
                    db = get_db()
                    db.execute(
                        "INSERT INTO products (name, category, price, stock, aisle, description) VALUES (?, ?, ?, ?, ?, ?)",
                        (name, category, price_value, stock_value, aisle, description)
                    )
                    db.commit()
                    flash("Product added to inventory successfully.")
                    return redirect(url_for("admin.inventory"))
            except ValueError:
                error = "Price must be a float and stock must be an integer."

    return render_template("admin/add_product.html", error=error)


@admin_bp.route("/product/edit/<int:product_id>", methods=["GET", "POST"])
@admin_login_required
def edit_product(product_id):
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if not product:
        flash("Product not found.")
        return redirect(url_for("admin.inventory"))
        
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        price = request.form.get("price", "").strip()
        stock = request.form.get("stock", "").strip()
        aisle = request.form.get("aisle", "").strip()
        description = request.form.get("description", "").strip()

        if not (name and category and price and stock and aisle):
            error = "All fields except description are required."
        else:
            try:
                price_val = float(price)
                stock_val = int(stock)
                if price_val < 0 or stock_val < 0:
                    error = "Price and stock levels cannot be negative."
                else:
                    db = get_db()
                    db.execute(
                        """
                        UPDATE products 
                        SET name = ?, category = ?, price = ?, stock = ?, aisle = ?, description = ? 
                        WHERE id = ?
                        """,
                        (name, category, price_val, stock_val, aisle, description, product_id)
                    )
                    db.commit()
                    flash(f"Product {name} updated successfully.")
                    return redirect(url_for("admin.inventory"))
            except ValueError:
                error = "Price must be a number and stock must be an integer."
                
    return render_template("admin/edit_product.html", product=product, error=error)


@admin_bp.route("/product/delete/<int:product_id>", methods=["POST"])
@admin_login_required
def delete_product(product_id):
    db = get_db()
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product:
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        # Also clean up any pending tasks associated with this product
        db.execute("DELETE FROM tasks WHERE product_id = ?", (product_id,))
        db.commit()
        flash(f"Product {product['name']} deleted from inventory.")
    else:
        flash("Product not found.")
    return redirect(url_for("admin.inventory"))


# ==========================================
# WORKER MANAGEMENT
# ==========================================

@admin_bp.route("/workers")
@admin_login_required
def workers():
    # Use updated 'workers' table
    workers = query_db("SELECT * FROM workers ORDER BY id")
    return render_template("admin/workers.html", workers=workers)


@admin_bp.route("/workers/add", methods=["GET", "POST"])
@admin_login_required
def add_worker():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        status = request.form.get("status", "Inactive")
        
        if not (name and email):
            error = "Name and email are required."
        elif not email.endswith("@gmail.com"):
            error = "Worker email must be an approved Gmail account (ending in @gmail.com)."
        else:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO workers (name, email, status) VALUES (?, ?, ?)",
                    (name, email, status)
                )
                db.commit()
                flash(f"Worker account for {name} registered.")
                return redirect(url_for("admin.workers"))
            except Exception as e:
                error = "Unable to add worker (email may already exist)."
    return render_template("admin/add_worker.html", error=error)


@admin_bp.route("/workers/toggle/<int:worker_id>", methods=["POST"])
@admin_login_required
def toggle_worker(worker_id):
    db = get_db()
    row = query_db("SELECT * FROM workers WHERE id = ?", (worker_id,), one=True)
    if row:
        new_status = "Active" if row["status"] != "Active" else "Inactive"
        db.execute("UPDATE workers SET status = ? WHERE id = ?", (new_status, worker_id))
        db.commit()
        flash(f"Worker status toggled to {new_status}.")
    return redirect(url_for("admin.workers"))


# ==========================================
# WORKER TASK ASSIGNMENT
# ==========================================

@admin_bp.route("/tasks", methods=["GET", "POST"])
@admin_login_required
def tasks():
    # Fetch all tasks
    assigned_tasks = query_db(
        """
        SELECT t.id AS task_id, t.description AS task_desc, t.status AS task_status, t.timestamp AS task_time,
               w.name AS worker_name, p.name AS product_name, p.aisle AS product_aisle
        FROM tasks t
        JOIN workers w ON t.worker_id = w.id
        JOIN products p ON t.product_id = p.id
        ORDER BY t.timestamp DESC
        """
    )
    return render_template("admin/tasks.html", tasks=assigned_tasks)


@admin_bp.route("/tasks/assign", methods=["GET", "POST"])
@admin_login_required
def assign_task():
    error = None
    db = get_db()
    
    if request.method == "POST":
        worker_id = request.form.get("worker_id")
        product_id = request.form.get("product_id")
        description = request.form.get("description", "").strip()
        
        if not (worker_id and product_id and description):
            error = "All fields are required to assign a task."
        else:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    "INSERT INTO tasks (worker_id, product_id, description, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (worker_id, product_id, description, 'Pending', timestamp)
                )
                db.commit()
                flash("Task successfully assigned to worker.")
                return redirect(url_for("admin.tasks"))
            except Exception as e:
                error = f"Error assigning task: {e}"
                
    # Fetch data for dropdowns
    active_workers = query_db("SELECT id, name FROM workers WHERE status = 'Active'")
    products = query_db("SELECT id, name, stock, aisle FROM products ORDER BY name ASC")
    
    return render_template(
        "admin/assign_task.html",
        active_workers=active_workers,
        products=products,
        error=error
    )


# ==========================================
# QUERY & INVENTORY MONITORING ANALYTICS
# ==========================================

@admin_bp.route("/analytics")
@admin_login_required
def analytics():
    # Query logs: Customer search questions and AI responses
    customer_queries = query_db("SELECT query, response, timestamp FROM customer_queries ORDER BY timestamp DESC LIMIT 50")
    
    # Inventory Monitoring logs: Workers restocking inventory
    activity_logs = query_db(
        """
        SELECT l.worker_email, l.action, l.timestamp, p.name AS product_name 
        FROM activity_logs l
        LEFT JOIN products p ON l.product_id = p.id
        ORDER BY l.timestamp DESC LIMIT 50
        """
    )
    
    return render_template("admin/analytics.html", customer_queries=customer_queries, activity_logs=activity_logs)


@admin_bp.route("/logout")
@admin_login_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"))
