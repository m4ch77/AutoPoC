#!/usr/bin/env python3
"""Fast, no-compile vulnerability triage.

Classifies a target's likely vulnerability class from source structure (reusing
agent.extract_functions), so the orchestrator can dispatch to the tool that is
STRONGEST for that class instead of running a fixed order. This is the cheap
"router brain" (deterministic, offline, ~ms). A Slither-backed enhancer can be
layered on later; the router works without it.

Usage (standalone, for verification):
    python3 triage.py <file.sol>
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

import agent  # extract_functions, has_owner_guard, has_reentrancy_guard

VULN_CLASSES = (
    "reentrancy", "access_control", "arithmetic", "delegatecall",
    "tx_origin", "storage_read", "randomness", "oracle", "selfdestruct_force",
)

_SENSITIVE = ("setowner", "transferownership", "changeowner", "claimownership",
              "withdraw", "adminwithdraw", "drain", "sweep", "rescue", "emergency",
              "mint", "migrate", "upgrade", "setimplementation", "initialize", "init")
_SELF_BOUND = ("balances[msg.sender]", "balanceof[msg.sender]",
               "_balances[msg.sender]", "credit[msg.sender]", "deposits[msg.sender]")


@dataclass
class Triage:
    ranked: list[str]                 # classes with score>0, highest first
    scores: dict[str, int] = field(default_factory=dict)
    signals: dict[str, list] = field(default_factory=dict)

    @property
    def top(self) -> str:
        return self.ranked[0] if self.ranked else "unknown"


def classify(source: str) -> Triage:
    funcs = agent.extract_functions(source)
    score = {c: 0 for c in VULN_CLASSES}
    sig: dict[str, list] = {}

    def mark(cls: str, ev: str, w: int = 1):
        score[cls] += w
        sig.setdefault(cls, [])
        if ev and ev not in sig[cls]:
            sig[cls].append(ev)

    for f in funcs:
        b = f.body
        low = b.lower()
        state_changing = f.mutability not in ("view", "pure")

        # reentrancy: external value call, then a state write AFTER it, no guard
        idx = b.find(".call{value:")
        if idx == -1:
            idx = b.find(".call{ value:")
        if idx != -1:
            after = b[idx:]
            wrote_after = ("-=" in after or "= 0" in after or "delete " in after
                           or re.search(r"balances?\s*\[[^\]]+\]\s*=", after)
                           or re.search(r"balanceOf\s*\[[^\]]+\]\s*=", after))
            if wrote_after and not agent.has_reentrancy_guard(f):
                mark("reentrancy", f.name, 3)

        # delegatecall backdoor / storage collision
        if re.search(r"\.\s*delegatecall\s*\(", b):
            mark("delegatecall", f.name, 3)

        # tx.origin auth
        if "tx.origin" in b:
            mark("tx_origin", f.name, 3)

        # arithmetic: unchecked +/- on a balance map with no balance guard
        if "unchecked" in low and ("-=" in b or "+=" in b) and re.search(r"balanceof|balances|credit", low):
            if not re.search(r"require\s*\([^;]*(balanceOf|balances|credit)\s*\[\s*msg\.sender\s*\]\s*>=", b):
                mark("arithmetic", f.name, 3)

        # weak randomness: blockhash/prevrandao, or timestamp used to DERIVE a
        # pseudo-random value (%/keccak) - NOT a plain timestamp deadline/timelock
        if state_changing:
            if re.search(r"blockhash\s*\(", b) or re.search(r"block\.(prevrandao|difficulty)", b):
                mark("randomness", f.name, 2)
            elif re.search(r"block\.timestamp", b) and re.search(r"%|keccak256\s*\(", b):
                mark("randomness", f.name, 2)

        # missing access control on a sensitive state-changing function
        if f.visible and state_changing:
            guarded = agent.has_owner_guard(f)
            writes_owner = re.search(r"\b(owner|_owner|admin|_admin)\s*=\s*[^=]", b) is not None
            sends_param = re.search(r"(\w+)\s*\.\s*call\s*\{\s*value\s*:", b) is not None
            name_sensitive = any(x in f.name.lower() for x in _SENSITIVE)
            self_bound = any(x in low for x in _SELF_BOUND)
            if not guarded and (writes_owner or (sends_param and not self_bound) or (name_sensitive and not self_bound)):
                mark("access_control", f.name, 2)

        # selfdestruct present (force-feed / teardown)
        if re.search(r"selfdestruct\s*\(", b):
            mark("selfdestruct_force", f.name, 2)

    # oracle / price manipulation (contract-level)
    if ("spotprice" in source.lower() or re.search(r"getPrice|latestAnswer|\bprice\s*\(", source)):
        if re.search(r"\bborrow\b|\bswap\w*\s*\(|reserve", source):
            mark("oracle", "price-based lending/pool", 3)

    # "private is not secret": a private state var compared to a param in a gate
    priv = re.findall(r"\b(?:bytes32|bytes16|bytes|uint\d*|address)\s+private\s+(\w+)", source)
    if priv:
        for f in funcs:
            for p in priv:
                if re.search(rf"\b{re.escape(p)}\s*==|\b==\s*{re.escape(p)}\b", f.body):
                    mark("storage_read", f.name, 2)
                    break

    ranked = sorted((c for c in VULN_CLASSES if score[c] > 0), key=lambda c: -score[c])
    return Triage(ranked=ranked, scores=score, signals=sig)


if __name__ == "__main__":
    src = open(sys.argv[1], encoding="utf-8").read()
    t = classify(src)
    print(f"top={t.top}")
    print(f"ranked={t.ranked}")
    for c in t.ranked:
        print(f"  {c}: score={t.scores[c]} signals={t.signals.get(c)}")
