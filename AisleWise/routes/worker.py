import re
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database.db import get_db, query_db
from datetime import datetime

worker_bp = Blueprint("worker", __name__, template_folder="../templates/worker")


def worker_login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("worker_email") is None:
            return redirect(url_for("worker.login"))
        return view(**kwargs)
    return wrapped_view


@worker_bp.route("/", methods=["GET"])
def index():
    return redirect(url_for("worker.login"))


@worker_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        
        # Enforce approved Gmail validation
        if not email.endswith("@gmail.com"):
            error = "Login email must be an approved Gmail account (e.g., worker@gmail.com)."
        else:
            worker = query_db(
                "SELECT * FROM workers WHERE email = ?",
                (email,),
                one=True
            )
            if worker is None:
                error = "Access denied: unknown worker email."
            elif worker["status"] != "Active":
                error = "Access denied: worker account is Inactive."
            else:
                session.clear()
                session["worker_email"] = worker["email"]
                session["worker_name"] = worker["name"]
                session["worker_id"] = worker["id"]
                return redirect(url_for("worker.dashboard"))
                
    return render_template("login.html", error=error)


@worker_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("worker.login"))


@worker_bp.route("/dashboard")
@worker_login_required
def dashboard():
    worker_id = session.get("worker_id")
    worker_email = session.get("worker_email")
    
    # Retrieve assigned pending tasks count
    pending_tasks_row = query_db(
        "SELECT COUNT(1) AS c FROM tasks WHERE worker_id = ? AND status = 'Pending'",
        (worker_id,),
        one=True
    )
    assigned_tasks = pending_tasks_row["c"] if pending_tasks_row else 0
    
    # Retrieve total low stock products in store
    low_stock_row = query_db(
        "SELECT COUNT(1) AS c FROM products WHERE stock < 5",
        one=True
    )
    low_stock_count = low_stock_row["c"] if low_stock_row else 0

    # Products updated today by this worker
    today = datetime.now().strftime("%Y-%m-%d")
    updated_today_row = query_db(
        "SELECT COUNT(DISTINCT product_id) AS c FROM activity_logs WHERE DATE(timestamp) = ? AND worker_email = ?",
        (today, worker_email),
        one=True
    )
    updated_today = updated_today_row["c"] if updated_today_row else 0

    # Fetch assigned pending tasks list
    assigned_tasks_list = query_db(
        """
        SELECT t.id AS task_id, t.description AS task_desc, t.timestamp AS task_time,
               p.id AS product_id, p.name AS product_name, p.stock AS product_stock,
               p.aisle AS product_aisle, p.category AS product_category
        FROM tasks t
        JOIN products p ON t.product_id = p.id
        WHERE t.worker_id = ? AND t.status = 'Pending'
        ORDER BY t.timestamp DESC
        """,
        (worker_id,)
    )

    return render_template(
        "dashboard.html",
        assigned_tasks=assigned_tasks,
        low_stock_count=low_stock_count,
        updated_today=updated_today,
        assigned_tasks_list=assigned_tasks_list
    )


@worker_bp.route("/low-stock")
@worker_login_required
def low_stock():
    items = query_db("SELECT * FROM products WHERE stock < 5 ORDER BY stock ASC")
    return render_template("low_stock.html", items=items)


@worker_bp.route("/restock/<int:product_id>", methods=["GET", "POST"])
@worker_login_required
def restock(product_id):
    db = get_db()
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        flash("Product not found.")
        return redirect(url_for("worker.dashboard"))

    if request.method == "POST":
        qty = request.form.get("stock")
        try:
            new_stock = int(qty)
            if new_stock < 0:
                flash("Stock level cannot be negative.")
                return redirect(url_for("worker.restock", product_id=product_id))
                
            old_stock = product["stock"]
            db.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
            
            # Mark matching pending tasks for this product as completed
            worker_id = session.get("worker_id")
            db.execute(
                "UPDATE tasks SET status = 'Completed' WHERE worker_id = ? AND product_id = ? AND status = 'Pending'",
                (worker_id, product_id)
            )
            
            # Create activity log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            worker_email = session.get("worker_email")
            action = f"Restocked {product['name']} (Aisle {product['aisle']}): stock updated from {old_stock} to {new_stock}"
            db.execute(
                "INSERT INTO activity_logs (worker_email, product_id, action, timestamp) VALUES (?, ?, ?, ?)",
                (worker_email, product_id, action, timestamp)
            )
            db.commit()
            flash(f"Stock for {product['name']} updated successfully.")
            return redirect(url_for("worker.dashboard"))
        except ValueError:
            flash("Stock must be a valid integer.")

    return render_template("restock.html", product=product)


@worker_bp.route("/profile")
@worker_login_required
def profile():
    email = session.get("worker_email")
    worker = query_db("SELECT * FROM workers WHERE email = ?", (email,), one=True)
    total_updates_row = query_db("SELECT COUNT(1) AS c FROM activity_logs WHERE worker_email = ?", (email,), one=True)
    total_updates = total_updates_row["c"] if total_updates_row else 0
    return render_template("profile.html", worker=worker, total_updates=total_updates)
