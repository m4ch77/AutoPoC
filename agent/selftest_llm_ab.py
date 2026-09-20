#!/usr/bin/env python3
"""Exercise the LLM brain END-TO-END against a local Ollama model and measure
the DeFiHackLabs card's effect: SAME target, two arms (no-card vs with-card),
each proven (or not) by the real forge verification gate. Isolates LocalLLMBrain
(no fuzzer/heuristic) so the result reflects the model + card only.

Usage: python3 selftest_llm_ab.py <target_dir> <vuln_class> [max_attempts]
"""

import json
import sys
import time
from pathlib import Path

from agent_general import Context, solve
from agent_combined import LocalLLMBrain, _verify_fn


def load(tdir: str, vuln_class: str):
    td = Path(tdir)
    m = json.loads((td / "manifest.json").read_text())
    src = m["target"]["src"]
    ctx = Context(
        target_source=(td / src).read_text(),
        invariants_source=(td / "Invariants.sol").read_text(),
        manifest=m,
        target_name=m["target"]["name"],
        vuln_class=vuln_class,
    )
    return ctx, str(td / src), str(td / "Invariants.sol")


def run_arm(label: str, tdir: str, vuln_class: str, max_attempts: int) -> bool:
    ctx, cpath, ipath = load(tdir, vuln_class)
    verify = _verify_fn(ctx, cpath, ipath)
    brain = LocalLLMBrain(seed=42, max_calls=max_attempts)
    t0 = time.monotonic()
    res = solve(ctx, [brain], verify, max_attempts, time.monotonic() + 1200)
    dt = time.monotonic() - t0
    print(f"[{label}] vuln_class={vuln_class!r} -> proven={res.found} "
          f"violated={res.violated!r} attempts={len(res.history)} ({dt:.0f}s)")
    for a in res.history:
        print(f"     #{a.n} {a.result}: {a.observation[:90]}")
    outdir = Path(__file__).resolve().parent / ".ab_out"
    outdir.mkdir(exist_ok=True)
    (outdir / f"Exploit_{label}.sol").write_text(res.code or "// no candidate\n")
    return res.found


if __name__ == "__main__":
    tdir = sys.argv[1]
    vclass = sys.argv[2]
    ma = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    print(f"=== LLM A/B  target={Path(tdir).name}  class={vclass}  max_attempts={ma} ===")
    nocard = run_arm("nocard", tdir, "", ma)
    withcard = run_arm("withcard", tdir, vclass, ma)
    print(f"=== RESULT  nocard_proven={nocard}  withcard_proven={withcard} ===")
    sys.exit(0)
