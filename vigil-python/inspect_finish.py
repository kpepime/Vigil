import os
import json
import requests
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

API_BASE_URL = "https://txline-dev.txodds.com/api"
api_token = os.getenv("TXLINE_API_TOKEN")
jwt = os.getenv("TXLINE_JWT")

headers = {
    "Authorization": f"Bearer {jwt}",
    "X-Api-Token": api_token,
    "Accept-Encoding": "gzip, deflate",
}

FIXTURE_ID = 17588391 # <-- paste the draw fixture ID here

url = f"{API_BASE_URL}/scores/historical/{FIXTURE_ID}"
response = requests.get(url, headers=headers)

print("Status code:", response.status_code)
print("Response length:", len(response.text))
print("First 300 chars:", repr(response.text[:300]))

messages = []
for line in response.text.splitlines():
    if line.startswith("data: "):
        try:
            messages.append(json.loads(line[len("data: "):]))
        except json.JSONDecodeError:
            continue

print(f"Total messages: {len(messages)}")

action_counts = Counter(m.get("Action") for m in messages)
print("\nAction breakdown:")
for action, count in action_counts.most_common():
    print(f"  {action}: {count}")

# Show the LAST 8 messages in full, in order — this is where the match actually ends
print("\nLast 8 messages (in order):")
for m in messages[-8:]:
    print(json.dumps(m, indent=2)[:500])
    print("---")

# Specifically show every "status" action's StatusId, in order
print("\nAll 'status' actions seen:")
for m in messages:
    if m.get("Action") == "status":
        print(f"  Ts={m.get('Ts')}  StatusId={m.get('StatusId')}  Data.StatusId={m.get('Data', {}).get('StatusId')}  Data.StatusName={m.get('Data', {}).get('StatusName')}")