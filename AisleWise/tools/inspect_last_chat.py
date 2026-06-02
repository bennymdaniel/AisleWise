import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from database.db import get_db

app = create_app()
with app.app_context():
    db = get_db()
    row = db.execute('SELECT session_id, user_message, bot_response, timestamp FROM customer_chats ORDER BY id DESC LIMIT 1').fetchone()
    if row:
        print('USER:', row['user_message'])
        print('BOT:', row['bot_response'])
        print('TIME:', row['timestamp'])
    else:
        print('No chats found')
