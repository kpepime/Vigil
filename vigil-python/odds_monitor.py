import os
import json
import sqlite3
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from datetime import datetime, timedelta

COOLDOWN_SECONDS = 120 # don't re-flag the same outcome within 2 minutes
last_signal_time = {}

load_dotenv()

API_BASE_URL = "https://txline-dev.txodds.com/api"
api_token = os.getenv("TXLINE_API_TOKEN")
jwt = os.getenv("TXLINE_JWT")

headers = {
    "Authorization": f"Bearer {jwt}",
    "X-Api-Token": api_token,
    "Accept": "text/event-stream",
}

# how big a probability swing counts as "sharp" (in percentage points)
MOVE_THRESHOLD = 2.5

# ----- Set up the database -----
conn = sqlite3.connect("signals.db")
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER,
    detected_at TEXT,
    outcome TEXT,
    old_pct REAL,
    new_pct REAL,
    change REAL
)
""")
conn.commit()

# keeps the last known percentages per (fixture, outcome)
# e.g. last_known[(18257865, "part1")] = 40.388
last_known = {}


update_count = 0

def handle_update(record):
    global update_count

    if "Prices" not in record or record.get("SuperOddsType") != "1X2_PARTICIPANT_RESULT":
        return

    update_count += 1
    if update_count % 20 == 0:
        print(f"...Vigil is still running, processed {update_count} updates so far")

    fixture_id = record["FixtureId"]
    names = record["PriceNames"]
    pcts = record["Pct"]

    for name, pct_str in zip(names, pcts):
        if pct_str == "NA":
            continue
        new_pct = float(pct_str)
        key = (fixture_id, name)

        if key in last_known:
            old_pct = last_known[key]
            change = new_pct - old_pct

            if abs(change) >= MOVE_THRESHOLD:
                now = datetime.utcnow()
                last_fired = last_signal_time.get(key)

                if last_fired is None or (now - last_fired) > timedelta(seconds=COOLDOWN_SECONDS):
                    print(f"SIGNAL:fixture {fixture_id} [{name}] moved {old_pct:.1f}% -> {new_pct:.1f}% ({change:+.1f})")
                    cur.execute(
                        "INSERT INTO signals (fixture_id, detected_at, outcome, old_pct, new_pct, change) VALUES (?, ?, ?, ?, ?, ?)",
                        (fixture_id, now.isoformat(), name, old_pct, new_pct, change)
                    )
                    conn.commit()
                    last_signal_time[key] = now

        last_known[key] = new_pct


def run():
    url = f"{API_BASE_URL}/odds/stream"
    print("Vigil is online. Connecting to odds stream...")
    with requests.get(url, headers=headers, stream=True) as response:
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
            handle_update(record)



if __name__ == "__main__":
    while True:
        try:
            run()
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"\nStream dropped ({e}). Vigil is reconnecting in 5 seconds...")
            time.sleep(5)