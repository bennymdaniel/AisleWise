from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database.db import get_db, query_db

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
        admin = query_db(
            "SELECT * FROM admin WHERE store_id = ? AND password = ?",
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
    low_stock = query_db(
        "SELECT * FROM products WHERE stock < 5 ORDER BY stock ASC"
    )
    return render_template(
        "admin/dashboard.html",
        total_products=total_products,
        low_stock=low_stock
    )


@admin_bp.route("/inventory", methods=["GET", "POST"])
@admin_login_required
def inventory():
    if request.method == "POST":
        product_id = request.form.get("product_id")
        stock = request.form.get("stock")
        if product_id and stock is not None:
            try:
                stock_value = int(stock)
                db = get_db()
                db.execute(
                    "UPDATE products SET stock = ? WHERE id = ?",
                    (stock_value, product_id)
                )
                db.commit()
                flash("Stock updated successfully.")
            except ValueError:
                flash("Stock must be a number.")
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

        if not (name and category and price and stock and aisle):
            error = "All fields are required."
        else:
            try:
                price_value = float(price)
                stock_value = int(stock)
                db = get_db()
                db.execute(
                    "INSERT INTO products (name, category, price, stock, aisle) VALUES (?, ?, ?, ?, ?)",
                    (name, category, price_value, stock_value, aisle)
                )
                db.commit()
                return redirect(url_for("admin.inventory"))
            except ValueError:
                error = "Price must be a number and stock must be an integer."

    return render_template("admin/add_product.html", error=error)


@admin_bp.route("/logout")
@admin_login_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"))
