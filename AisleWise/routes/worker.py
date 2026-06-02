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
        worker = query_db(
            "SELECT * FROM worker_accounts WHERE email = ?",
            (email,),
            one=True
        )
        if worker is None:
            error = "Access denied: unknown worker email."
        elif worker["status"] != "Active":
            error = "Access denied: worker not active."
        else:
            session.clear()
            session["worker_email"] = worker["email"]
            session["worker_name"] = worker["name"]
            return redirect(url_for("worker.dashboard"))
    return render_template("login.html", error=error)


@worker_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("worker.login"))


@worker_bp.route("/dashboard")
@worker_login_required
def dashboard():
    # Summary cards
    low_stock_count = query_db("SELECT COUNT(1) AS c FROM products WHERE stock < 5", one=True)["c"]
    total_low_stock = low_stock_count
    # Assigned Tasks: use low stock count as proxy
    assigned_tasks = total_low_stock
    # Products updated today
    today = datetime.now().strftime("%Y-%m-%d")
    updated_today_row = query_db(
        "SELECT COUNT(DISTINCT product_id) AS c FROM activity_logs WHERE DATE(timestamp) = ?",
        (today,),
        one=True
    )
    updated_today = updated_today_row["c"] if updated_today_row else 0

    low_stock_items = query_db("SELECT * FROM products WHERE stock < 5 ORDER BY stock ASC")

    return render_template(
        "dashboard.html",
        assigned_tasks=assigned_tasks,
        low_stock_count=total_low_stock,
        updated_today=updated_today,
        low_stock_items=low_stock_items
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
            old_stock = product["stock"]
            db.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
            # create activity log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            worker_email = session.get("worker_email")
            action = f"Updated {product['name']} stock from {old_stock} to {new_stock}"
            db.execute(
                "INSERT INTO activity_logs (worker_email, product_id, action, timestamp) VALUES (?, ?, ?, ?)",
                (worker_email, product_id, action, timestamp)
            )
            db.commit()
            flash("Stock updated successfully.")
            return redirect(url_for("worker.dashboard"))
        except ValueError:
            flash("Stock must be an integer.")

    return render_template("restock.html", product=product)


@worker_bp.route("/profile")
@worker_login_required
def profile():
    email = session.get("worker_email")
    worker = query_db("SELECT * FROM worker_accounts WHERE email = ?", (email,), one=True)
    total_updates_row = query_db("SELECT COUNT(1) AS c FROM activity_logs WHERE worker_email = ?", (email,), one=True)
    total_updates = total_updates_row["c"] if total_updates_row else 0
    return render_template("profile.html", worker=worker, total_updates=total_updates)
