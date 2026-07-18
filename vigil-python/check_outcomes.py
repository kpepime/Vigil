import os
import json
import sqlite3
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "https://txline-dev.txodds.com/api"
api_token = os.getenv("TXLINE_API_TOKEN")
jwt = os.getenv("TXLINE_JWT")

headers = {
    "Authorization": f"Bearer {jwt}",
    "X-Api-Token": api_token,
}


def get_final_result(fixture_id):
    url = f"{API_BASE_URL}/scores/historical/{fixture_id}"
    response = requests.get(url, headers={**headers, "Accept-Encoding": "gzip, deflate"})

    final_message = None
    for line in response.text.splitlines():
        if line.startswith("data: "):
            try:
                record = json.loads(line[len("data: "):])
            except json.JSONDecodeError:
                continue
            if record.get("Action") == "game_finalised":
                final_message = record

    if not final_message:
        return None # match hasn't finished yet

    score = final_message["Score"]
    p1_goals = score["Participant1"].get("Total", {}).get("Goals", 0)
    p2_goals = score["Participant2"].get("Total", {}).get("Goals", 0)

    if p1_goals > p2_goals:
        return "part1"
    elif p2_goals > p1_goals:
        return "part2"
    else:
        # Regular time tied, check penalty shootout
        p1_pens = score["Participant1"].get("PE", {}).get("Goals", 0)
        p2_pens = score["Participant2"].get("PE", {}).get("Goals", 0)
        if p1_pens > p2_pens:
            return "part1"
        elif p2_pens > p1_pens:
            return "part2"
        return "draw"


def main():
    conn = sqlite3.connect("signals.db")
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
        if fixture_id not in checked_fixtures:
            checked_fixtures[fixture_id] = get_final_result(fixture_id)

        result = checked_fixtures[fixture_id]

        if result is None:
            print(f"Fixture {fixture_id}: not finished yet, skipping")
            unresolved += 1
            continue

        was_correct = (outcome == result)
        status = "CORRECT" if was_correct else "WRONG"
        print(f"Fixture {fixture_id}: signal predicted [{outcome}], actual result [{result}] -> {status}")

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