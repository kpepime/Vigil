import os
import json
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

fixture_id = 18202783

url = f"{API_BASE_URL}/scores/historical/{fixture_id}"
response = requests.get(url, headers=headers)

messages = []
for line in response.text.splitlines():
    if line.startswith("data: "):
        payload = line[len("data: "):]
        try:
            messages.append(json.loads(payload))
        except json.JSONDecodeError:
            continue

final_messages = [m for m in messages if m.get("Action") == "game_finalised"]
print(f"game_finalised messages: {len(final_messages)}")

if final_messages:
    print(json.dumps(final_messages[-1], indent=2))