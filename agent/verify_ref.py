#!/usr/bin/env python3
"""Validate a ported target by running a REFERENCE Exploit through the real forge
gate (the same agent.verify_candidate the pipeline uses). Confirms:
  (a) checkAll(target) is healthy right after deploy (port well-formed), and
  (b) the reference exploit breaks it (port is actually solvable).
This is NOT the agent's output — it only proves the port is valid & solvable.

Usage: python3 verify_ref.py <target_dir> <reference_exploit.sol>
"""
import json
import sys
from pathlib import Path

import agent

tdir = Path(sys.argv[1])
ref = Path(sys.argv[2])
m = json.loads((tdir / "manifest.json").read_text())
src = tdir / m["target"]["src"]
inv = tdir / m["invariants"]["contract"]
hdir = agent.harness_dir()
code = ref.read_text()
proven, violated, note = agent.verify_candidate(hdir, src, inv, code, m, m["target"]["name"])
print(f"[{tdir.name}] reference-exploit proven={proven} violated={violated!r}")
if note:
    print("note:", note[:600])
