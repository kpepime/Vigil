import os
import time
import threading
import requests
from dotenv import load_dotenv
import db

load_dotenv()

API_BASE_URL = "https://txline-dev.txodds.com/api"
api_token = os.getenv("TXLINE_API_TOKEN")

_lock = threading.Lock()
_fixture_cache = {}


def _headers():
    import detector
    return {
        "Authorization": f"Bearer {detector.get_current_jwt()}",
        "X-Api-Token": api_token,
        "Accept-Encoding": "gzip, deflate",
    }


def load_from_db():
    """Instant startup load — no API calls, no waiting."""
    try:
        saved = db.load_all_fixture_names()
        with _lock:
            _fixture_cache.update(saved)
        print(f"[fixtures] Loaded {len(saved)} fixture names from database instantly.")
    except Exception as e:
        print(f"[fixtures] Could not load from database: {e}")


def _refresh_once():
    now = time.time()
    for i, hours_back in enumerate(range(0, 24 * 7)):
        if i % 20 == 0:
            print(f"[fixtures] ...scanned {i} hours so far, {len(_fixture_cache)} fixtures known")
        ts = now - hours_back * 3600
        epoch_day = int(ts // 86400)
        hour_of_day = int((ts % 86400) // 3600)
        url = f"{API_BASE_URL}/fixtures/updates/{epoch_day}/{hour_of_day}"

        try:
            resp = requests.get(url, headers=_headers(), timeout=15)
        except Exception as e:
            print(f"[fixtures] Request failed for {epoch_day}/{hour_of_day}: {e}")
            continue

        if resp.status_code == 200 and resp.text.strip() not in ("[]", ""):
            try:
                items = resp.json()
            except Exception as e:
                print(f"[fixtures] JSON parse failed for {epoch_day}/{hour_of_day}: {e}")
                continue

            for f in items:
                fid = f.get("FixtureId")
                p1 = f.get("Participant1")
                p2 = f.get("Participant2")
                if fid and p1 and p2:
                    is_new = fid not in _fixture_cache
                    with _lock:
                        _fixture_cache[fid] = (p1, p2)
                    if is_new:
                        try:
                            db.save_fixture_name(fid, p1, p2)
                        except Exception as e:
                            print(f"[fixtures] Failed to save {fid} to database: {e}")

        elif resp.status_code != 200:
            print(f"[fixtures] Got status {resp.status_code} for {epoch_day}/{hour_of_day}")

    print(f"[fixtures] Cache refreshed — {len(_fixture_cache)} fixtures known.")


def run_fixture_refresher():
    load_from_db()  # instant — do this first, before anything else
    while True:
        _refresh_once()
        time.sleep(1800)


def team_names(fixture_id):
    with _lock:
        return _fixture_cache.get(fixture_id)


def describe_fixture(fixture_id):
    names = team_names(fixture_id)
    if names:
        return f"{names[0]} vs {names[1]}"
    return str(fixture_id)


def describe_outcome(fixture_id, outcome_code):
    names = team_names(fixture_id)
    if not names:
        return outcome_code
    team1, team2 = names
    if outcome_code == "part1":
        return team1
    elif outcome_code == "part2":
        return team2
    elif outcome_code == "draw":
        return "Draw"
    return outcome_code


def list_known_fixtures():
    with _lock:
        return [f"{p1} vs {p2}" for p1, p2 in _fixture_cache.values()]