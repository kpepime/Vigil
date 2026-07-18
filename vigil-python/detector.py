import os
import json
import time
import threading
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
import db

load_dotenv()

API_BASE_URL = "https://txline-dev.txodds.com/api"
api_token = os.getenv("TXLINE_API_TOKEN")

MOVE_THRESHOLD = 2.5
COOLDOWN_SECONDS = 120

_lock = threading.Lock()
_state = {
    "jwt": os.getenv("TXLINE_JWT"),
    "last_known": {},
    "last_signal_time": {},
    "update_count": 0,
    "status": "starting",
}


def get_headers():
    with _lock:
        jwt = _state["jwt"]
    return {
        "Authorization": f"Bearer {jwt}",
        "X-Api-Token": api_token,
        "Accept": "text/event-stream",
        "Accept-Encoding": "gzip, deflate",
    }


def refresh_jwt():
    response = requests.post(f"{API_BASE_URL}/auth/guest/start")
    response.raise_for_status()
    new_jwt = response.json()["token"]
    with _lock:
        _state["jwt"] = new_jwt
    print("JWT refreshed.")


def handle_update(record, cur, conn):
    if "Prices" not in record or record.get("SuperOddsType") != "1X2_PARTICIPANT_RESULT":
        return

    with _lock:
        _state["update_count"] += 1

    fixture_id = record["FixtureId"]
    names = record["PriceNames"]
    pcts = record["Pct"]

    for name, pct_str in zip(names, pcts):
        if pct_str == "NA":
            continue
        new_pct = float(pct_str)
        key = (fixture_id, name)

        with _lock:
            old_pct = _state["last_known"].get(key)

        if old_pct is not None:
            change = new_pct - old_pct
            if abs(change) >= MOVE_THRESHOLD:
                now = datetime.utcnow()
                with _lock:
                    last_fired = _state["last_signal_time"].get(key)
                if last_fired is None or (now - last_fired) > timedelta(seconds=COOLDOWN_SECONDS):
                    print(f"SIGNAL: fixture {fixture_id} [{name}] {old_pct:.1f}% -> {new_pct:.1f}% ({change:+.1f})")
                    q = f"INSERT INTO signals (fixture_id, detected_at, outcome, old_pct, new_pct, change) VALUES ({db.PLACEHOLDER}, {db.PLACEHOLDER}, {db.PLACEHOLDER}, {db.PLACEHOLDER}, {db.PLACEHOLDER}, {db.PLACEHOLDER})"
                    cur.execute(q, (fixture_id, now.isoformat(), name, old_pct, new_pct, change))
                    conn.commit()
                    with _lock:
                        _state["last_signal_time"][key] = now

        with _lock:
            _state["last_known"][key] = new_pct


def run_detector():
    conn, cur = db.init_db()
    url = f"{API_BASE_URL}/odds/stream"

    while True:
        try:
            with _lock:
                _state["status"] = "connecting"
            print("Vigil is online. Connecting to odds stream...")
            with requests.get(url, headers=get_headers(), stream=True, timeout=90) as response:
                if response.status_code in (401, 403):
                    print("Stream auth rejected. Refreshing JWT...")
                    refresh_jwt()
                    continue

                with _lock:
                    _state["status"] = "connected"
                print("Status code:", response.status_code)

                for line in response.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if not decoded.startswith("data: "):
                        continue
                    payload = decoded[len("data: "):]
                    try:
                        record = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    handle_update(record, cur, conn)

        except Exception as e:
            with _lock:
                _state["status"] = f"reconnecting ({e})"
            print(f"Stream dropped ({e}). Reconnecting in 5 seconds...")
            time.sleep(5)


def get_status():
    with _lock:
        return {
            "status": _state["status"],
            "update_count": _state["update_count"],
        }