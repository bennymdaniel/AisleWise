import contextvars
import sqlite3

DATABASE_PATH = "database/aislewise.db"
db_cv = contextvars.ContextVar("db")


def get_db():
    conn = db_cv.get(None)
    if conn is None:
        # Fallback/default for scripts running outside request scope (e.g. init db)
        conn = sqlite3.connect(DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
    return conn


def query_db(query, args=(), one=False):
    db = get_db()
    cursor = db.execute(query, args)
    rows = cursor.fetchall()
    cursor.close()
    return (rows[0] if rows else None) if one else rows

