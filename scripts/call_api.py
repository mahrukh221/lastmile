"""Calls the public API with an API key.   python -m scripts.call_api lm_yourkey"""
import sys

import httpx

if len(sys.argv) != 2:
    sys.exit("Usage: python -m scripts.call_api <your-api-key>")

key = sys.argv[1]
base = "http://127.0.0.1:8000"
for path in ["/api/v1/ping", "/api/v1/stats/cases"]:
    response = httpx.get(base + path, headers={"X-API-Key": key}, timeout=5.0)
    print(path, "->", response.status_code, response.json())