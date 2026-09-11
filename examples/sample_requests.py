import json
import os
import urllib.request


base = os.environ.get("PROPERTY_DESK_URL", "http://127.0.0.1:8000")
payload = {
    "collection": "maple-court-documents",
    "property_id": "maple-court",
    "question": "What needs attention before the next tenant visit?",
}
request = urllib.request.Request(
    f"{base}/questions/answer",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.dumps(json.load(response), indent=2))

