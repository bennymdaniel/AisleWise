from flask import Blueprint, render_template

customer_bp = Blueprint("customer", __name__, template_folder="../templates")

@customer_bp.route("/")
def index():
    return render_template("customer.html")
