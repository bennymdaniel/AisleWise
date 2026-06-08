import inspect
from functools import wraps
from datetime import datetime
from fastapi import APIRouter, Request
from database.db import get_db, query_db
from routes import RedirectException, flash

router = APIRouter()


def admin_login_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request") or (args[0] if args else None)
        if not request or not request.session.get("admin_id"):
            raise RedirectException(url="/admin/login")
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper


@router.get("/", name="admin.index")
def index(request: Request):
    if request.session.get("admin_id"):
        raise RedirectException(url=str(request.url_for("admin.dashboard")))
    raise RedirectException(url=str(request.url_for("admin.login")))


@router.api_route("/login", methods=["GET", "POST"], name="admin.login")
async def login(request: Request):
    error = None
    if request.method == "POST":
        form_data = await request.form()
        store_id = form_data.get("store_id", "").strip()
        password = form_data.get("password", "").strip()
        
        # Verify against updated 'admins' table
        admin = query_db(
            "SELECT * FROM admins WHERE store_id = ? AND password = ?",
            (store_id, password),
            one=True
        )
        if admin is None:
            error = "Invalid store ID or password."
        else:
            request.session.clear()
            request.session["admin_id"] = admin["id"]
            request.session["store_id"] = admin["store_id"]
            raise RedirectException(url=str(request.url_for("admin.dashboard")))
            
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="admin/login.html", context={"error": error})


@router.get("/dashboard", name="admin.dashboard")
@admin_login_required
def dashboard(request: Request):
    total_products = query_db("SELECT COUNT(1) AS count FROM products", one=True)["count"]
    out_of_stock = query_db("SELECT COUNT(1) AS count FROM products WHERE stock = 0", one=True)["count"]
    active_workers = query_db("SELECT COUNT(1) AS count FROM workers WHERE status = 'Active'", one=True)["count"]
    pending_tasks = query_db("SELECT COUNT(1) AS count FROM tasks WHERE status = 'Pending'", one=True)["count"]
    
    low_stock = query_db(
        "SELECT * FROM products WHERE stock < 5 ORDER BY stock ASC"
    )
    
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            "total_products": total_products,
            "out_of_stock": out_of_stock,
            "active_workers": active_workers,
            "pending_tasks": pending_tasks,
            "low_stock": low_stock
        }
    )


# ==========================================
# PRODUCT CRUD
# ==========================================

@router.api_route("/inventory", methods=["GET", "POST"], name="admin.inventory")
@admin_login_required
async def inventory(request: Request):
    if request.method == "POST":
        form_data = await request.form()
        product_id = form_data.get("product_id")
        stock = form_data.get("stock")
        if product_id and stock is not None:
            try:
                stock_value = int(stock)
                if stock_value < 0:
                    flash(request, "Stock level cannot be negative.")
                else:
                    db = get_db()
                    db.execute(
                        "UPDATE products SET stock = ? WHERE id = ?",
                        (stock_value, product_id)
                    )
                    db.commit()
                    flash(request, "Stock updated successfully.")
            except ValueError:
                flash(request, "Stock must be a valid number.")
        raise RedirectException(url=str(request.url_for("admin.inventory")))

    products = query_db("SELECT * FROM products ORDER BY id")
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="admin/inventory.html", context={"products": products})


@router.api_route("/add-product", methods=["GET", "POST"], name="admin.add_product")
@admin_login_required
async def add_product(request: Request):
    error = None
    if request.method == "POST":
        form_data = await request.form()
        name = form_data.get("name", "").strip()
        category = form_data.get("category", "").strip()
        price = form_data.get("price", "").strip()
        stock = form_data.get("stock", "").strip()
        aisle = form_data.get("aisle", "").strip()
        description = form_data.get("description", "").strip()

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
                    flash(request, "Product added to inventory successfully.")
                    raise RedirectException(url=str(request.url_for("admin.inventory")))
            except ValueError:
                error = "Price must be a float and stock must be an integer."

    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="admin/add_product.html", context={"error": error})


@router.api_route("/product/edit/{product_id:int}", methods=["GET", "POST"], name="admin.edit_product")
@admin_login_required
async def edit_product(request: Request, product_id: int):
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if not product:
        flash(request, "Product not found.")
        raise RedirectException(url=str(request.url_for("admin.inventory")))
        
    error = None
    if request.method == "POST":
        form_data = await request.form()
        name = form_data.get("name", "").strip()
        category = form_data.get("category", "").strip()
        price = form_data.get("price", "").strip()
        stock = form_data.get("stock", "").strip()
        aisle = form_data.get("aisle", "").strip()
        description = form_data.get("description", "").strip()

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
                    flash(request, f"Product {name} updated successfully.")
                    raise RedirectException(url=str(request.url_for("admin.inventory")))
            except ValueError:
                error = "Price must be a number and stock must be an integer."
                
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="admin/edit_product.html", context={"product": product, "error": error})


@router.post("/product/delete/{product_id:int}", name="admin.delete_product")
@admin_login_required
def delete_product(request: Request, product_id: int):
    db = get_db()
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product:
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        # Also clean up any pending tasks associated with this product
        db.execute("DELETE FROM tasks WHERE product_id = ?", (product_id,))
        db.commit()
        flash(request, f"Product {product['name']} deleted from inventory.")
    else:
        flash(request, "Product not found.")
    raise RedirectException(url=str(request.url_for("admin.inventory")))


# ==========================================
# WORKER MANAGEMENT
# ==========================================

@router.get("/workers", name="admin.workers")
@admin_login_required
def workers(request: Request):
    workers = query_db("SELECT * FROM workers ORDER BY id")
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="admin/workers.html", context={"workers": workers})


@router.api_route("/workers/add", methods=["GET", "POST"], name="admin.add_worker")
@admin_login_required
async def add_worker(request: Request):
    error = None
    if request.method == "POST":
        form_data = await request.form()
        name = form_data.get("name", "").strip()
        email = form_data.get("email", "").strip().lower()
        status = form_data.get("status", "Inactive")
        
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
                flash(request, f"Worker account for {name} registered.")
                raise RedirectException(url=str(request.url_for("admin.workers")))
            except Exception as e:
                error = "Unable to add worker (email may already exist)."
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="admin/add_worker.html", context={"error": error})


@router.post("/workers/toggle/{worker_id:int}", name="admin.toggle_worker")
@admin_login_required
def toggle_worker(request: Request, worker_id: int):
    db = get_db()
    row = query_db("SELECT * FROM workers WHERE id = ?", (worker_id,), one=True)
    if row:
        new_status = "Active" if row["status"] != "Active" else "Inactive"
        db.execute("UPDATE workers SET status = ? WHERE id = ?", (new_status, worker_id))
        db.commit()
        flash(request, f"Worker status toggled to {new_status}.")
    raise RedirectException(url=str(request.url_for("admin.workers")))


# ==========================================
# WORKER TASK ASSIGNMENT
# ==========================================

@router.get("/tasks", name="admin.tasks")
@admin_login_required
def tasks(request: Request):
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
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="admin/tasks.html", context={"tasks": assigned_tasks})


@router.api_route("/tasks/assign", methods=["GET", "POST"], name="admin.assign_task")
@admin_login_required
async def assign_task(request: Request):
    error = None
    db = get_db()
    
    if request.method == "POST":
        form_data = await request.form()
        worker_id = form_data.get("worker_id")
        product_id = form_data.get("product_id")
        description = form_data.get("description", "").strip()
        
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
                flash(request, "Task successfully assigned to worker.")
                raise RedirectException(url=str(request.url_for("admin.tasks")))
            except Exception as e:
                error = f"Error assigning task: {e}"
                
    # Fetch data for dropdowns
    active_workers = query_db("SELECT id, name FROM workers WHERE status = 'Active'")
    products = query_db("SELECT id, name, stock, aisle FROM products ORDER BY name ASC")
    
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="admin/assign_task.html",
        context={
            "active_workers": active_workers,
            "products": products,
            "error": error
        }
    )


# ==========================================
# QUERY & INVENTORY MONITORING ANALYTICS
# ==========================================

@router.get("/analytics", name="admin.analytics")
@admin_login_required
def analytics(request: Request):
    customer_queries = query_db("SELECT query, response, timestamp FROM customer_queries ORDER BY timestamp DESC LIMIT 50")
    activity_logs = query_db(
        """
        SELECT l.worker_email, l.action, l.timestamp, p.name AS product_name 
        FROM activity_logs l
        LEFT JOIN products p ON l.product_id = p.id
        ORDER BY l.timestamp DESC LIMIT 50
        """
    )
    
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="admin/analytics.html",
        context={
            "customer_queries": customer_queries,
            "activity_logs": activity_logs
        }
    )


@router.get("/logout", name="admin.logout")
@admin_login_required
def logout(request: Request):
    request.session.clear()
    raise RedirectException(url=str(request.url_for("admin.login")))
