import inspect
from functools import wraps
from datetime import datetime
from fastapi import APIRouter, Request
from database.db import get_db, query_db
from routes import RedirectException, flash

router = APIRouter()


def worker_login_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request") or (args[0] if args else None)
        if not request or not request.session.get("worker_email"):
            raise RedirectException(url="/worker/login")
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper


@router.get("/", name="worker.index")
def index(request: Request):
    raise RedirectException(url=str(request.url_for("worker.login")))


@router.api_route("/login", methods=["GET", "POST"], name="worker.login")
async def login(request: Request):
    error = None
    if request.method == "POST":
        form_data = await request.form()
        email = form_data.get("email", "").strip().lower()
        
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
                request.session.clear()
                request.session["worker_email"] = worker["email"]
                request.session["worker_name"] = worker["name"]
                request.session["worker_id"] = worker["id"]
                raise RedirectException(url=str(request.url_for("worker.dashboard")))
                
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="worker/login.html", context={"error": error})


@router.get("/logout", name="worker.logout")
def logout(request: Request):
    request.session.clear()
    raise RedirectException(url=str(request.url_for("worker.login")))


@router.get("/dashboard", name="worker.dashboard")
@worker_login_required
def dashboard(request: Request):
    worker_id = request.session.get("worker_id")
    worker_email = request.session.get("worker_email")
    
    # Retrieve action permissions
    action_perms_raw = query_db("SELECT * FROM worker_action_permissions")
    action_perms = {row["action_name"]: row["is_enabled"] for row in action_perms_raw}
    
    # Retrieve field permissions
    field_perms_raw = query_db("SELECT * FROM worker_field_permissions")
    viewable_fields = {row["field_name"]: row["can_edit"] for row in field_perms_raw if row["can_view"] == 1}

    # If View Inventory is disabled, show empty dashboard with access warning
    if not action_perms.get("View Inventory", 1):
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="worker/dashboard.html",
            context={
                "assigned_tasks": 0,
                "low_stock_count": 0,
                "updated_today": 0,
                "assigned_tasks_list": [],
                "viewable_fields": {},
                "action_perms": action_perms,
                "error_message": "Access Denied: View Inventory is disabled by administrator."
            }
        )

    pending_tasks_row = query_db(
        "SELECT COUNT(1) AS c FROM tasks WHERE worker_id = ? AND status = 'Pending'",
        (worker_id,),
        one=True
    )
    assigned_tasks = pending_tasks_row["c"] if pending_tasks_row else 0
    
    low_stock_row = query_db(
        "SELECT COUNT(1) AS c FROM products WHERE stock < 5",
        one=True
    )
    low_stock_count = low_stock_row["c"] if low_stock_row else 0

    today = datetime.now().strftime("%Y-%m-%d")
    updated_today_row = query_db(
        "SELECT COUNT(DISTINCT product_id) AS c FROM activity_logs WHERE DATE(timestamp) = ? AND worker_email = ?",
        (today, worker_email),
        one=True
    )
    updated_today = updated_today_row["c"] if updated_today_row else 0

    assigned_tasks_list = query_db(
        """
        SELECT t.id AS task_id, t.description AS task_desc, t.timestamp AS task_time,
               p.id AS product_id, p.*
        FROM tasks t
        JOIN products p ON t.product_id = p.id
        WHERE t.worker_id = ? AND t.status = 'Pending'
        ORDER BY t.timestamp DESC
        """,
        (worker_id,)
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="worker/dashboard.html",
        context={
            "assigned_tasks": assigned_tasks,
            "low_stock_count": low_stock_count,
            "updated_today": updated_today,
            "assigned_tasks_list": assigned_tasks_list,
            "viewable_fields": viewable_fields,
            "action_perms": action_perms
        }
    )


@router.get("/low-stock", name="worker.low_stock")
@worker_login_required
def low_stock(request: Request):
    # Retrieve action permissions
    action_perms_raw = query_db("SELECT * FROM worker_action_permissions")
    action_perms = {row["action_name"]: row["is_enabled"] for row in action_perms_raw}
    
    if not action_perms.get("View Low Stock Alerts", 1):
        flash(request, "Access denied: View Low Stock Alerts operation is disabled.")
        raise RedirectException(url=str(request.url_for("worker.dashboard")))

    # Retrieve field permissions
    field_perms_raw = query_db("SELECT * FROM worker_field_permissions")
    viewable_fields = {row["field_name"]: row["can_edit"] for row in field_perms_raw if row["can_view"] == 1}

    items = query_db("SELECT * FROM products WHERE stock < 5 ORDER BY stock ASC")
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="worker/low_stock.html",
        context={
            "items": items,
            "viewable_fields": viewable_fields,
            "action_perms": action_perms
        }
    )


@router.api_route("/restock/{product_id:int}", methods=["GET", "POST"], name="worker.restock")
@worker_login_required
async def restock(request: Request, product_id: int):
    # Retrieve action permissions
    action_perms_raw = query_db("SELECT * FROM worker_action_permissions")
    action_perms = {row["action_name"]: row["is_enabled"] for row in action_perms_raw}
    
    if not action_perms.get("Restock Products", 1):
        flash(request, "Access denied: Restock Products operation is disabled.")
        raise RedirectException(url=str(request.url_for("worker.dashboard")))

    # Retrieve field permissions
    field_perms_raw = query_db("SELECT * FROM worker_field_permissions")
    viewable_fields = {row["field_name"]: row["can_edit"] for row in field_perms_raw if row["can_view"] == 1}

    db = get_db()
    product = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        flash(request, "Product not found.")
        raise RedirectException(url=str(request.url_for("worker.dashboard")))

    if request.method == "POST":
        # Check Update Stock action
        if not action_perms.get("Update Stock", 1):
            flash(request, "Access denied: Update Stock operation is disabled.")
            raise RedirectException(url=str(request.url_for("worker.dashboard")))
            
        # Check field edit permission for stock
        if not viewable_fields.get("stock", 0):
            flash(request, "Access denied: You do not have permission to modify stock level.")
            raise RedirectException(url=str(request.url_for("worker.dashboard")))

        form_data = await request.form()
        qty = form_data.get("stock")
        try:
            new_stock = int(qty)
            if new_stock < 0:
                flash(request, "Stock level cannot be negative.")
                raise RedirectException(url=str(request.url_for("worker.restock", product_id=product_id)))
                
            old_stock = product["stock"]
            db.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
            
            worker_id = request.session.get("worker_id")
            db.execute(
                "UPDATE tasks SET status = 'Completed' WHERE worker_id = ? AND product_id = ? AND status = 'Pending'",
                (worker_id, product_id)
            )
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            worker_email = request.session.get("worker_email")
            action = f"Restocked {product['name']} (Aisle {product['aisle']}): stock updated from {old_stock} to {new_stock}"
            db.execute(
                "INSERT INTO activity_logs (worker_email, product_id, action, timestamp) VALUES (?, ?, ?, ?)",
                (worker_email, product_id, action, timestamp)
            )
            db.commit()
            flash(request, f"Stock for {product['name']} updated successfully.")
            raise RedirectException(url=str(request.url_for("worker.dashboard")))
        except ValueError:
            flash(request, "Stock must be a valid integer.")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="worker/restock.html",
        context={
            "product": product,
            "viewable_fields": viewable_fields,
            "action_perms": action_perms
        }
    )


@router.get("/profile", name="worker.profile")
@worker_login_required
def profile(request: Request):
    email = request.session.get("worker_email")
    worker = query_db("SELECT * FROM workers WHERE email = ?", (email,), one=True)
    total_updates_row = query_db("SELECT COUNT(1) AS c FROM activity_logs WHERE worker_email = ?", (email,), one=True)
    total_updates = total_updates_row["c"] if total_updates_row else 0
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="worker/profile.html", context={"worker": worker, "total_updates": total_updates})
