from flask import Flask, render_template
from dotenv import load_dotenv
import os
from database.db import get_db, close_db
from database.init_db import init_app
from routes.customer import customer_bp
from routes.admin import admin_bp
from routes.worker import worker_bp


def create_app():
    # Load .env into environment (GEMINI_API_KEY, GEMINI_MODEL, etc.)
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_mapping(
        DATABASE="database/aislewise.db",
        SECRET_KEY="devkey"
    )

    init_app(app)
    app.teardown_appcontext(close_db)

    app.register_blueprint(customer_bp, url_prefix="/customer")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(worker_bp, url_prefix="/worker")

    @app.route("/")
    def home():
        return render_template("home.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
