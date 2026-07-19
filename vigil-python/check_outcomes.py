import os
import json
import sqlite3
import requests
import db
import fixtures
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "https://txline-dev.txodds.com/api"
api_token = os.getenv("TXLINE_API_TOKEN")
jwt = os.getenv("TXLINE_JWT")

headers = {
    "Authorization": f"Bearer {jwt}",
    "X-Api-Token": api_token,
}


FINISHED_STATUS_IDS = {5, 10, 13}  # Full-time, after extra time, after penalties

def get_final_result(fixture_id):
    """Returns 'part1', 'draw', or 'part2' for a finished fixture, or None if not finished yet."""
    url = f"{API_BASE_URL}/scores/historical/{fixture_id}"
    response = requests.get(url, headers=headers)  # requests handles Accept-Encoding/decompression itself

    latest_score = None
    match_finished = False

    for line in response.text.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            record = json.loads(line[len("data: "):])
        except json.JSONDecodeError:
            continue

        # Track the most recent score we've seen, whatever action carried it
        if "Score" in record:
            latest_score = record["Score"]

        # Primary signal: TxLINE's own settlement confirmation
        if record.get("Action") == "game_finalised":
            match_finished = True
            if "Score" in record:
                latest_score = record["Score"]

        # Fallback signal: the game clock itself reached a finished state
        if record.get("Action") == "status":
            status_id = record.get("Data", {}).get("StatusId")
            if status_id in FINISHED_STATUS_IDS:
                match_finished = True

    if not match_finished or latest_score is None:
        return None  # genuinely not finished yet, or no score ever recorded

    p1_goals = latest_score["Participant1"].get("Total", {}).get("Goals", 0)
    p2_goals = latest_score["Participant2"].get("Total", {}).get("Goals", 0)

    if p1_goals > p2_goals:
        return "part1"
    elif p2_goals > p1_goals:
        return "part2"
    else:
        p1_pens = latest_score["Participant1"].get("PE", {}).get("Goals", 0)
        p2_pens = latest_score["Participant2"].get("PE", {}).get("Goals", 0)
        if p1_pens > p2_pens:
            return "part1"
        elif p2_pens > p1_pens:
            return "part2"
        return "draw"


def main():
    conn = db.get_connection()
    cur = conn.cursor()

    # Only look at "increasing" signals, a rising probability is the actual prediction
    cur.execute("""
        SELECT id, fixture_id, outcome, old_pct, new_pct, change
        FROM signals
        WHERE change > 0
    """)
    rows = cur.fetchall()

    print(f"Checking {len(rows)} directional signals...\n")

    correct = 0
    incorrect = 0
    unresolved = 0
    checked_fixtures = {}

    for row_id, fixture_id, outcome, old_pct, new_pct, change in rows:
        label = fixtures.describe_fixture(fixture_id)

        if fixture_id not in checked_fixtures:
            checked_fixtures[fixture_id] = get_final_result(fixture_id)

        result = checked_fixtures[fixture_id]

        if result is None:
            print(f"Fixture: {label}\nStatus: not finished yet, skipping\n")
            unresolved += 1
            continue

        outcome_label = fixtures.describe_outcome(fixture_id, outcome)
        result_label = fixtures.describe_outcome(fixture_id, result)
        was_correct = (outcome == result)
        status = "CORRECT" if was_correct else "WRONG"
        print(f"Fixture: {label}\nPredicted: {outcome_label} | Actual: {result_label} -> {status}\n")

        if was_correct:
            correct += 1
        else:
            incorrect += 1

    total_resolved = correct + incorrect
    print(f"\n--- Summary ---")
    print(f"Resolved signals: {total_resolved}")
    print(f"Correct: {correct}")
    print(f"Incorrect: {incorrect}")
    print(f"Unresolved (match not finished): {unresolved}")
    if total_resolved > 0:
        print(f"Accuracy: {correct / total_resolved * 100:.1f}%")


if __name__ == "__main__":
    main()