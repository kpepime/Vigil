import os
import json
import time
import requests
from dotenv import load_dotenv
from check_outcomes import get_final_result

load_dotenv()

API_BASE_URL = "https://txline-dev.txodds.com/api"
api_token = os.getenv("TXLINE_API_TOKEN")
jwt = os.getenv("TXLINE_JWT")

headers = {
    "Authorization": f"Bearer {jwt}",
    "X-Api-Token": api_token,
}

now = time.time()
seen_fixtures = set()

# scan the last 30 days, checking every 3 hours, to collect fixture IDs
for i, hours_back in enumerate(range(0, 720, 6)):
    if i % 20 == 0:
        print(f"...scanned {i} time windows so far")
    ts = now - hours_back * 3600
    epoch_day = int(ts // 86400)
    hour_of_day = int((ts % 86400) // 3600)
    # rest of the loop stays the same

    url = f"{API_BASE_URL}/fixtures/updates/{epoch_day}/{hour_of_day}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200 and response.text.strip() not in ("[]", ""):
        try:
            fixtures = response.json()
        except Exception:
            continue
        for f in fixtures:
            fid = f.get("FixtureId")
            p1 = f.get("Participant1")
            p2 = f.get("Participant2")
            if fid and fid not in seen_fixtures:
                seen_fixtures.add(fid)
                print(f"Found fixture {fid}: {p1} vs {p2}")

print(f"\nTotal unique fixtures found: {len(seen_fixtures)}")
print("\nChecking which ones are finished, and how...\n")

for fid in seen_fixtures:
    url = f"{API_BASE_URL}/scores/historical/{fid}"
    check_response = requests.get(url, headers=headers)
    if not check_response.text.strip():
        continue  # no scores data at all for this fixture — skip silently

    result = get_final_result(fid)
    if result:
        print(f"Fixture {fid}: FINISHED, result = {result}")