import os
import time
import requests
import db
from stats import compute_summary
from detector import get_status

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    try:
        requests.post(f"{API_URL}/sendMessage", data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
    except Exception as e:
        print(f"[telegram] Failed to send message: {e}")


def add_subscriber(chat_id):
    conn = db.get_connection()
    cur = conn.cursor()
    q = f"INSERT INTO telegram_subscribers (chat_id) VALUES ({db.PLACEHOLDER})"
    try:
        cur.execute(q, (chat_id,))
        conn.commit()
    except Exception:
        conn.rollback()  # already subscribed, fine, ignore


def remove_subscriber(chat_id):
    conn = db.get_connection()
    cur = conn.cursor()
    q = f"DELETE FROM telegram_subscribers WHERE chat_id = {db.PLACEHOLDER}"
    cur.execute(q, (chat_id,))
    conn.commit()


def get_subscribers():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM telegram_subscribers")
    return [row[0] for row in cur.fetchall()]


def broadcast_signal(fixture_id, outcome, old_pct, new_pct, change):
    if not TOKEN:
        return
    subscribers = get_subscribers()
    if not subscribers:
        return
    arrow = "📈" if change > 0 else "📉"
    text = (
        f"{arrow} *Signal detected*\n"
        f"Fixture: `{fixture_id}`\n"
        f"Outcome: *{outcome}*\n"
        f"{old_pct:.1f}% → {new_pct:.1f}%  ({change:+.1f})"
    )
    for chat_id in subscribers:
        send_message(chat_id, text)


def handle_command(chat_id, text):
    text = text.strip().lower()

    if text in ("/start", "/subscribe"):
        add_subscriber(chat_id)
        send_message(chat_id,
            "Subscribed. You'll get a message here every time Vigil detects "
            "movement detected.\n\nCommands:\n"
            "/status: connection + activity\n"
            "/accuracy: resolved signal accuracy\n"
            "/recent: last 5 signals\n"
            "/stop: unsubscribe from alerts")

    elif text in ("/stop", "/unsubscribe"):
        remove_subscriber(chat_id)
        send_message(chat_id, "Unsubscribed. You won't get live alerts anymore.")

    elif text == "/status":
        status = get_status()
        send_message(chat_id,
            f"*Vigil status*\n"
            f"Connection: `{status['status']}`\n"
            f"Updates processed: {status['update_count']}")

    elif text == "/accuracy":
        data = compute_summary()
        send_message(chat_id,
            f"*Accuracy*\n"
            f"Resolved: {data['resolved']}\n"
            f"Correct: {data['correct']}\n"
            f"Incorrect: {data['incorrect']}\n"
            f"Unresolved: {data['unresolved']}\n"
            f"Accuracy: {data['accuracy']}")

    elif text == "/recent":
        data = compute_summary()
        rows = data["recent"][:5]
        if not rows:
            send_message(chat_id, "No signals logged yet.")
            return
        lines = ["*Last 5 signals*"]
        for t, fixture_id, outcome, change in rows:
            lines.append(f"`{fixture_id}` {outcome} ({change:+.1f}) — {t[11:19]}")
        send_message(chat_id, "\n".join(lines))

    elif text == "/help":
        send_message(chat_id,
            "/status: connection + activity\n"
            "/accuracy: resolved signal accuracy\n"
            "/recent: last 5 signals\n"
            "/start: subscribe to live alerts\n"
            "/stop: unsubscribe")

    else:
        send_message(chat_id, "Unknown command. Try /help")


def run_bot():
    if not TOKEN:
        print("[telegram] TELEGRAM_BOT_TOKEN not set, bot disabled.")
        return

    print("[telegram] Bot polling started.")
    offset = None

    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            resp = requests.get(f"{API_URL}/getUpdates", params=params, timeout=35)
            updates = resp.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message")
                if not message:
                    continue
                chat_id = message["chat"]["id"]
                text = message.get("text", "")
                if text:
                    handle_command(chat_id, text)

        except Exception as e:
            print(f"[telegram] Polling error: {e}")
            time.sleep(5)