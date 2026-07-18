import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "https://txline-dev.txodds.com/api"
api_token = os.getenv("TXLINE_API_TOKEN")
jwt = os.getenv("TXLINE_JWT")

headers = {
    "Authorization": f"Bearer {jwt}",
    "X-Api-Token": api_token,
    "Accept": "text/event-stream",
}

url = f"{API_BASE_URL}/odds/stream"

print("Vigil is online. Connecting to odds stream...")
with requests.get(url, headers=headers, stream=True) as response:
    print("Status code:", response.status_code)
    for line in response.iter_lines():
        if line:
            print(line.decode("utf-8"))