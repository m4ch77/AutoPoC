#!/usr/bin/env python3
"""Sanity check the LocalLLMBrain against a running Ollama server.

1) confirm the model responds at all,
2) ask it for an Exploit against OpenVault (easy target) and print the result.
No forge here - just proves the local, uncensored model is wired and produces
Solidity we can then verify.
"""
import json
import sys
import time
import urllib.request

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:1.5b"
URL = "http://localhost:11434"

def chat(messages, timeout=180):
    body = json.dumps({"model": MODEL, "stream": False,
                       "options": {"temperature": 0, "seed": 42},
                       "messages": messages}).encode()
    req = urllib.request.Request(f"{URL}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["message"]["content"]

print(f"[1] model responds? (model={MODEL})", flush=True)
t = time.monotonic()
try:
    out = chat([{"role": "user", "content": "Reply with exactly: OK"}])
    print(f"    -> {out.strip()[:60]!r}  ({time.monotonic()-t:.1f}s)", flush=True)
except Exception as e:
    print(f"    ERROR: {e}", flush=True)
    sys.exit(2)

print("[2] LocalLLMBrain on OpenVault ...", flush=True)
sys.path.insert(0, ".")
import agent_combined as ac

target = open("../../trust404-track04-participant/targets/OpenVault/src/OpenVault.sol").read()
inv = open("../../trust404-track04-participant/targets/OpenVault/Invariants.sol").read()
manifest = json.load(open("../../trust404-track04-participant/targets/OpenVault/manifest.json"))
ctx = ac.Context(target_source=target, invariants_source=inv, manifest=manifest, target_name="OpenVault")

# raw output for debugging what the small model actually returns
preds = manifest.get("invariants", {}).get("predicates", [])
user = (f"TARGET:\n```solidity\n{target}\n```\n\nINVARIANT to violate {preds}:\n"
        f"```solidity\n{inv}\n```\n\nWrite Exploit.sol that breaks the invariant.")
raw = chat([{"role": "system", "content": ac.LocalLLMBrain._SYSTEM}, {"role": "user", "content": user}])
print(f"    RAW MODEL OUTPUT:\n{'='*60}\n{raw}\n{'='*60}", flush=True)

brain = ac.LocalLLMBrain(model=MODEL, max_calls=1)
t = time.monotonic()
cand = brain.next(ctx, [])
dt = time.monotonic() - t
if cand is None:
    print(f"    -> None (refusal/parse-fail/no-server)  ({dt:.1f}s)", flush=True)
    sys.exit(1)
print(f"    -> got candidate ({dt:.1f}s):\n{'-'*60}\n{cand.code}\n{'-'*60}", flush=True)

print("[3] verifying LLM candidate via harness (forge) ...", flush=True)
import agent
from pathlib import Path
hdir = agent.harness_dir()
proven, violated, note = agent.verify_candidate(
    hdir, Path("../../trust404-track04-participant/targets/OpenVault/src/OpenVault.sol"),
    Path("../../trust404-track04-participant/targets/OpenVault/Invariants.sol"),
    cand.code, manifest, "OpenVault")
print(f"    -> proven={proven} violated={violated!r} note={note[:120]!r}", flush=True)
sys.exit(0 if proven else 1)
