#!/usr/bin/env python3
"""General, execution-grounded exploit agent (Reason -> Act -> Observe).

Design goals
------------
* No hardcoded per-target answers. The "brain" proposes an Exploit.sol from the
  target source + the goal (invariants) + feedback from previous failed attempts.
* Every proposal is proven by EXECUTION (the harness). Only a candidate that
  actually breaks an invariant is accepted; otherwise the failure is fed back and
  the brain tries again. This is what makes it generalize beyond templates.
* Pluggable brains, tried in order:
    1. LLMBrain      - reasons about the specific target (needs an API key)
    2. HeuristicBrain - offline template library (degrade path, deterministic)
  A ScriptedBrain is provided for testing the loop without a key or forge.
* The verifier is dependency-injected, so the control loop is unit-testable
  without Foundry (see selftest_loop.py).

This module reuses the verified forge pipeline from agent.py for the real run.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol


# ── data types ───────────────────────────────────────────────────────────────

@dataclass
class Context:
    target_source: str
    invariants_source: str
    manifest: dict
    target_name: str
    vuln_class: str = ""   # set by the router (triage.top); selects a knowledge card


@dataclass
class Candidate:
    strategy: str
    code: str


@dataclass
class Attempt:
    n: int
    brain: str
    strategy: str
    result: str        # "PROVEN" | "NOT_PROVEN" | "COMPILE_ERROR"
    observation: str    # what the brain sees next time


@dataclass
class Result:
    found: bool
    code: Optional[str]
    violated: str
    history: list[Attempt] = field(default_factory=list)


# verify_fn(code) -> (proven, violated_predicate, note/error)
VerifyFn = Callable[[str], tuple[bool, str, str]]


class Brain(Protocol):
    name: str
    def next(self, ctx: Context, history: list[Attempt]) -> Optional[Candidate]: ...


# ── the control loop (Reason -> Act -> Observe) ──────────────────────────────

def solve(ctx: Context, brains: list[Brain], verify: VerifyFn,
          max_attempts: int, deadline: Optional[float] = None) -> Result:
    history: list[Attempt] = []
    best: Optional[str] = None
    n = 0
    for brain in brains:
        while n < max_attempts:
            if deadline is not None and time.monotonic() >= deadline:
                return Result(False, best, "", history)
            cand = brain.next(ctx, history)      # Reason: propose (informed by feedback)
            if cand is None:
                break                            # brain exhausted -> next brain
            n += 1
            best = cand.code
            proven, violated, note = verify(cand.code)   # Act: run it for real
            if proven:                                    # Observe: did the invariant break?
                history.append(Attempt(n, brain.name, cand.strategy, "PROVEN", violated))
                return Result(True, cand.code, violated, history)
            obs = _observation(note, violated)
            result = "COMPILE_ERROR" if note else "NOT_PROVEN"
            history.append(Attempt(n, brain.name, cand.strategy, result, obs))
    return Result(False, best, "", history)


def _observation(note: str, violated: str) -> str:
    if note:
        return f"컴파일/실행 실패: {note[:300]}"
    return "실행됐지만 어떤 불변식도 깨지지 않음(모두 여전히 성립). 다른 상태 변수/호출 경로를 노려라."


# ── Brain 1: LLM (reasons about the specific target) ─────────────────────────

_SYSTEM = (
    "You are an expert smart-contract exploit developer. Given a target contract "
    "and an invariant that must NOT hold after your attack, output ONE Exploit.sol.\n"
    "Rules:\n"
    "- Output ONLY solidity in a single ```solidity code block.\n"
    "- Exactly: contract Exploit { function run(address target) external payable { ... } }\n"
    "- Define any interfaces inline (NO imports, no remappings).\n"
    "- Include SPDX and pragma ^0.8.20.\n"
    "- The harness funds your Exploit with 10 ETH before calling run().\n"
    "- block.number/timestamp are fixed; do not rely on time passing.\n"
    "- Make the named invariant predicate evaluate to false after run()."
)


class LLMBrain:
    name = "llm"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, max_calls: int = 4):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
        self.model = model or os.environ.get("TRUST404_AGENT_MODEL", "claude-sonnet-4-5")
        self.max_calls = max_calls
        self._calls = 0

    def next(self, ctx: Context, history: list[Attempt]) -> Optional[Candidate]:
        if not self.api_key or self._calls >= self.max_calls:
            return None
        self._calls += 1
        code = self._ask(ctx, history)
        if code is None:
            return None
        return Candidate(strategy=f"llm#{self._calls}", code=code)

    def _ask(self, ctx: Context, history: list[Attempt]) -> Optional[str]:
        import urllib.request
        import urllib.error

        feedback = ""
        if history:
            lines = [f"- 시도 {a.n} [{a.strategy}] -> {a.result}: {a.observation}" for a in history[-4:]]
            feedback = "이전 시도와 실패 이유(반복하지 말고 개선하라):\n" + "\n".join(lines) + "\n\n"

        preds = ctx.manifest.get("invariants", {}).get("predicates", [])
        user = (
            f"타깃 컨트랙트:\n```solidity\n{ctx.target_source}\n```\n\n"
            f"불변식(이 술어가 false가 되게 하라): {preds}\n"
            f"```solidity\n{ctx.invariants_source}\n```\n\n"
            f"{feedback}"
            "위 타깃을 깨는 Exploit.sol을 출력하라."
        )
        body = json.dumps({
            "model": self.model,
            "max_tokens": 3000,
            "temperature": 0,
            "system": _SYSTEM,
            "messages": [{"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"Content-Type": "application/json", "x-api-key": self.api_key,
                     "anthropic-version": "2023-06-01"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode())
            text = "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
        except Exception:
            return None
        m = re.search(r"```(?:solidity)?\s*(.*?)```", text, re.DOTALL)
        code = m.group(1).strip() if m else text.strip()
        if "contract Exploit" in code and "function run(address" in code:
            return code
        return None


# ── Brain 2: Heuristic templates (offline degrade path) ──────────────────────

class HeuristicBrain:
    name = "heuristic"

    def __init__(self):
        self._candidates: Optional[list[tuple[str, str]]] = None
        self._i = 0

    def next(self, ctx: Context, history: list[Attempt]) -> Optional[Candidate]:
        if self._candidates is None:
            try:
                import agent  # reuse the verified template library
                self._candidates = agent.build_candidates(ctx.target_source)
            except Exception:
                self._candidates = []
        if self._i >= len(self._candidates):
            return None
        strategy, code = self._candidates[self._i]
        self._i += 1
        return Candidate(strategy=strategy, code=code)


# ── Brain (test only): scripted proposals ────────────────────────────────────

class ScriptedBrain:
    name = "scripted"

    def __init__(self, codes: list[str]):
        self._codes = list(codes)
        self._i = 0

    def next(self, ctx: Context, history: list[Attempt]) -> Optional[Candidate]:
        if self._i >= len(self._codes):
            return None
        code = self._codes[self._i]
        self._i += 1
        return Candidate(strategy=f"scripted#{self._i}", code=code)


# ── real wiring (forge verifier via agent.py) ────────────────────────────────

def _real_verify_fn(ctx: Context, contract_path: str, invariants_path: str):
    import agent
    from pathlib import Path
    hdir = agent.harness_dir()

    def verify(code: str) -> tuple[bool, str, str]:
        return agent.verify_candidate(hdir, Path(contract_path), Path(invariants_path),
                                      code, ctx.manifest, ctx.target_name)
    return verify


def main(argv: list[str]) -> int:
    import argparse
    from pathlib import Path
    p = argparse.ArgumentParser(prog="agent_general")
    p.add_argument("--contract", required=True)
    p.add_argument("--invariants", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-attempts", type=int, default=6, dest="max_attempts")
    args = p.parse_args(argv)

    manifest = json.loads(Path(args.manifest).read_text())
    ctx = Context(
        target_source=Path(args.contract).read_text(),
        invariants_source=Path(args.invariants).read_text(),
        manifest=manifest,
        target_name=manifest.get("target", {}).get("name", ""),
    )
    brains: list[Brain] = [LLMBrain(), HeuristicBrain()]  # LLM first, degrade to heuristics
    verify = _real_verify_fn(ctx, args.contract, args.invariants)

    res = solve(ctx, brains, verify, args.max_attempts, time.monotonic() + args.timeout)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "Exploit.sol").write_text(res.code or "// no candidate\n")
    (out / "attempts.log").write_text(
        "\n".join(f"{a.n}\t{a.brain}\t{a.strategy}\t{a.result}\t{a.observation}" for a in res.history) + "\n"
    )
    for a in res.history:
        sys.stderr.write(f"{a.n} [{a.brain}/{a.strategy}] {a.result}: {a.observation}\n")
    if res.found:
        sys.stderr.write(f"PROVEN (violated={res.violated})\n")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
