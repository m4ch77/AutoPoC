#!/usr/bin/env python3
"""Print the EXACT messages CloudLLMBrain would send for a target (system + user,
including the triage-selected DeFiHackLabs card). Lets us feed the real agent
prompt to a strong model by hand (no API key) and verify its output via the gate.

Usage: python3 dump_prompt.py <target_dir>
"""
import json
import sys
from pathlib import Path

import triage
import agent_combined as ac
from agent_general import Context

tdir = Path(sys.argv[1])
m = json.loads((tdir / "manifest.json").read_text())
src = (tdir / m["target"]["src"]).read_text()
inv = (tdir / m["invariants"]["contract"]).read_text()
ctx = Context(target_source=src, invariants_source=inv, manifest=m, target_name=m["target"]["name"])
ctx.vuln_class = triage.classify(src).top

msgs = ac._build_messages(ac.CloudLLMBrain._SYSTEM, ctx, [])
print(f"### target={tdir.name}  triage.vuln_class={ctx.vuln_class!r}")
print("\n===== SYSTEM =====")
print(msgs[0]["content"])
print("\n===== USER =====")
print(msgs[1]["content"])
