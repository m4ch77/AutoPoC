#!/usr/bin/env python3
"""Smoke-test the CloudLLMBrain HTTP path against the real Anthropic API.
Reads ANTHROPIC_API_KEY + TRUST404_CLOUD_MODEL from env. Never prints the key.
"""
import json
import os
import sys
import urllib.request

from agent_combined import CloudLLMBrain

b = CloudLLMBrain()
if not b.api_key:
    print("NO_KEY_IN_ENV")
    sys.exit(1)
print(f"model={b.model}  key_present=True  key_len={len(b.api_key)}")

# 1) Raw diagnostic call (surfaces HTTP errors that _post would swallow).
body = json.dumps({
    "model": b.model, "max_tokens": 16,
    "system": "Reply with exactly: OK",
    "messages": [{"role": "user", "content": "Say OK"}],
}).encode()
req = urllib.request.Request(
    "https://api.anthropic.com/v1/messages", data=body,
    headers={"Content-Type": "application/json", "x-api-key": b.api_key,
             "anthropic-version": "2023-06-01"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode())
    text = "".join(x.get("text", "") for x in payload.get("content", []) if x.get("type") == "text")
    print("RAW_OK resp=", repr(text[:60]))
except urllib.error.HTTPError as e:
    print("RAW_HTTP_ERROR", e.code, e.read().decode()[:300])
    sys.exit(2)
except Exception as e:
    print("RAW_FAIL", type(e).__name__, str(e)[:200])
    sys.exit(2)

# 2) Exercise the actual _post code path used by the agent.
out = b._post([{"role": "system", "content": "Reply with exactly: OK"},
               {"role": "user", "content": "Say OK"}])
print("POST_PATH_RETURNS", "text" if out else "None", repr((out or "")[:60]))
print("SMOKE_OK" if out else "SMOKE_POST_NONE")
