import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, session, redirect, url_for
from database.db import get_db, query_db
from services.rag_engine import answer_customer_question

customer_bp = Blueprint("customer", __name__, template_folder="../templates")


def get_customer_session_id():
    if not session.get("customer_session_id"):
        session["customer_session_id"] = str(uuid.uuid4())
    return session["customer_session_id"]


@customer_bp.route("/")
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
def chat():
    session_id = get_customer_session_id()
    error = None
    user_query = None
    if request.method == "POST":
        user_query = request.form.get("message", "").strip()
    else:
        user_query = request.args.get("query", "").strip()

    bot_response = None
    if user_query:
        bot_response = answer_customer_question(user_query)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        db.execute(
            "INSERT INTO customer_chats (session_id, user_message, bot_response, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, user_query, bot_response, timestamp)
        )
        db.execute(
            "INSERT INTO customer_queries (query, response, timestamp) VALUES (?, ?, ?)",
            (user_query, bot_response, timestamp)
        )
        db.commit()

    chats = query_db(
        "SELECT * FROM customer_chats WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    )
    return render_template(
        "customer/chat.html",
        chats=chats,
        error=error,
        user_query=user_query,
        bot_response=bot_response
    )
