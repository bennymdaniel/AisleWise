import json
import uuid
import inspect
from functools import wraps
from datetime import datetime
from fastapi import APIRouter, Request
from database.db import get_db, query_db
from services.rag_engine import answer_customer_question
from routes import RedirectException

router = APIRouter()


def customer_login_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request") or (args[0] if args else None)
        if not request or not request.session.get("customer_google_user"):
            raise RedirectException(url="/customer/login")
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper


def get_customer_session_id(request: Request):
    if not request.session.get("customer_session_id"):
        request.session["customer_session_id"] = str(uuid.uuid4())
    return request.session["customer_session_id"]


@router.api_route("/login", methods=["GET", "POST"], name="customer.login")
async def login(request: Request):
    if request.session.get("customer_google_user"):
        raise RedirectException(url=str(request.url_for("customer.index")))
    
    if request.method == "POST":
        request.session.clear()
        request.session["customer_google_user"] = {
            "name": "Alex Shopper",
            "email": "alex.shopper@gmail.com",
            "picture": "/static/images/google-avatar.png"
        }
        raise RedirectException(url=str(request.url_for("customer.index")))
        
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="customer/login.html")


@router.get("/logout", name="customer.logout")
def logout(request: Request):
    request.session.clear()
    raise RedirectException(url=str(request.url_for("customer.login")))


@router.get("/", name="customer.index")
@customer_login_required
def index(request: Request):
    categories = [
        "Dairy",
        "Snacks",
        "Beverages",
        "Bakery",
        "Frozen Foods",
        "Personal Care",
        "Household"
    ]
    templates = request.app.state.templates
    return templates.TemplateResponse(request=request, name="customer.html", context={"categories": categories})


@router.api_route("/chat", methods=["GET", "POST"], name="customer.chat")
@customer_login_required
async def chat(request: Request):
    session_id = get_customer_session_id(request)
    categories = [
        "Dairy",
        "Snacks",
        "Beverages",
        "Bakery",
        "Frozen Foods",
        "Personal Care",
        "Household"
    ]
    
    user_query = None
    if request.method == "POST":
        form_data = await request.form()
        user_query = form_data.get("message", "").strip()
    else:
        user_query = request.query_params.get("query", "").strip()

    bot_response = None
    products_list = []
    
    if user_query:
        bot_data = answer_customer_question(user_query)
        bot_response = bot_data["response"]
        products_list = bot_data["products"]
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        db.execute(
            "INSERT INTO customer_chats (session_id, user_message, bot_response, timestamp, products_json) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_query, bot_response, timestamp, json.dumps(products_list))
        )
        db.execute(
            "INSERT INTO customer_queries (query, response, timestamp) VALUES (?, ?, ?)",
            (user_query, bot_response, timestamp)
        )
        db.commit()

    # Fetch chat logs
    chats_raw = query_db(
        "SELECT * FROM customer_chats WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    )
    
    chats = []
    for chat_row in chats_raw:
        p_list = []
        if chat_row["products_json"]:
            try:
                p_list = json.loads(chat_row["products_json"])
            except Exception:
                p_list = []
        chats.append({
            "user_message": chat_row["user_message"],
            "bot_response": chat_row["bot_response"],
            "timestamp": chat_row["timestamp"],
            "products": p_list
        })
        
    # Fetch distinct query history
    query_history = query_db(
        "SELECT DISTINCT user_message FROM customer_chats WHERE session_id = ? ORDER BY timestamp DESC LIMIT 8",
        (session_id,)
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="customer/chat.html",
        context={
            "chats": chats,
            "categories": categories,
            "query_history": query_history,
            "user_query": user_query,
            "bot_response": bot_response
        }
    )
