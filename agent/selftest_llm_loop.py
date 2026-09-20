#!/usr/bin/env python3
"""End-to-end proof of the LOCAL-LLM axis with the feedback loop.

Runs the real solve() control loop with ONLY the LocalLLMBrain (Ollama, offline)
against OpenVault, using the real forge verifier. Shows Reason->Act->Observe:
a first attempt that fails to compile is fed back and corrected until PROVEN.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
import agent
import agent_combined as ac
from agent_general import solve

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:7b"
BASE = "../../trust404-track04-participant/targets/OpenVault"

manifest = json.load(open(f"{BASE}/manifest.json"))
ctx = ac.Context(
    target_source=open(f"{BASE}/src/OpenVault.sol").read(),
    invariants_source=open(f"{BASE}/Invariants.sol").read(),
    manifest=manifest, target_name="OpenVault",
)

hdir = agent.harness_dir()
def verify(code):
    return agent.verify_candidate(hdir, Path(f"{BASE}/src/OpenVault.sol"),
                                  Path(f"{BASE}/Invariants.sol"), code, manifest, "OpenVault")

brains = [ac.LocalLLMBrain(model=MODEL, max_calls=5)]
print(f"solve() with ONLY local-llm ({MODEL}) + feedback loop ...", flush=True)
t = time.monotonic()
res = solve(ctx, brains, verify, max_attempts=5)
print(f"\nfinished in {time.monotonic()-t:.0f}s, found={res.found} violated={res.violated!r}", flush=True)
for a in res.history:
    print(f"  attempt {a.n} [{a.brain}] {a.result}: {a.observation[:90]}", flush=True)
if res.found:
    print("\n=== PROVEN Exploit.sol (produced by the LOCAL model) ===", flush=True)
    print(res.code, flush=True)
sys.exit(0 if res.found else 1)
