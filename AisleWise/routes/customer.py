import json
import uuid
from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from database.db import get_db, query_db
from services.rag_engine import answer_customer_question

customer_bp = Blueprint("customer", __name__, template_folder="../templates")


def customer_login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("customer_google_user") is None:
            return redirect(url_for("customer.login"))
        return view(**kwargs)
    return wrapped_view


def get_customer_session_id():
    if not session.get("customer_session_id"):
        session["customer_session_id"] = str(uuid.uuid4())
    return session["customer_session_id"]


@customer_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("customer_google_user"):
        return redirect(url_for("customer.index"))
    
    if request.method == "POST":
        # Simulate Google sign in authentication
        session.clear()
        session["customer_google_user"] = {
            "name": "Alex Shopper",
            "email": "alex.shopper@gmail.com",
            "picture": "/static/images/google-avatar.png"
        }
        return redirect(url_for("customer.index"))
        
    return render_template("customer/login.html")


@customer_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("customer.login"))


@customer_bp.route("/")
@customer_login_required
def index():
    categories = [
        "Dairy",
        "Snacks",
        "Beverages",
        "Bakery",
        "Frozen Foods",
        "Personal Care",
        "Household"
    ]
    return render_template("customer.html", categories=categories)


@customer_bp.route("/chat", methods=["GET", "POST"])
@customer_login_required
def chat():
    session_id = get_customer_session_id()
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
        user_query = request.form.get("message", "").strip()
    else:
        user_query = request.args.get("query", "").strip()

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

    return render_template(
        "customer/chat.html",
        chats=chats,
        categories=categories,
        query_history=query_history,
        user_query=user_query,
        bot_response=bot_response
    )
