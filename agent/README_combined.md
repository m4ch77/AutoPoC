# Combined Agent — triage-routed: fuzzer + reentrancy + LLM + heuristics (finished build)

`agent_combined.py` is the finished exploit-proving agent. It **triages** the
target's vulnerability class, **routes** to the brain strongest for that class,
and accepts only candidates a real execution (the official harness) proves break
an invariant.

```
triage (classify, ~ms) → route (order brains by class):
   reentrancy        → ReentrancyBrain
   access / arith    → FuzzerBrain (quick, time-boxed)
   oracle/delegate/… → CloudLLM (if key)
   fallback          → HeuristicBrain
        └────────────→ VERIFY (forge harness) → accept only PROVEN   (+ solution cache)
        └─ fail → feed the reason back, try the next brain / refine
```

- **triage.py** — fast, no-compile static classifier (reentrancy / access_control
  / arithmetic / delegatecall / tx_origin / storage_read / randomness / oracle /
  selfdestruct_force). Picks which tool runs first so the time budget isn't wasted.
- **FuzzerBrain** — Foundry invariant fuzzing finds an invariant-breaking call
  sequence with zero prior knowledge, then synthesizes a PoC from the shrunk
  counterexample. Offline, uncensored. **Time-boxed** so a fruitless campaign never
  starves the LLM of the budget. Strongest for access-control / arithmetic.
- **ReentrancyBrain** — synthesizes a reentering actor (deposit → vulnerable
  withdraw → re-enter in `receive()`), covering reentrancy that plain fuzzing
  misses (EOA senders don't re-enter).
- **CloudLLMBrain** — a strong cloud model via the grading sandbox's permitted
  LLM-API network exception, called as a fallback chain
  (`claude-sonnet-5 → claude-opus-4-8`). Active only when
  `ANTHROPIC_API_KEY`/`LLM_API_KEY` is set. Best generalization to undisclosed
  targets. Failures are fed back for self-correction.
- **HeuristicBrain** — deterministic static templates (reentrancy / access
  control / unchecked-underflow drain) as a last resort.

The exploit itself always runs LOCALLY (no fork). Only the (optional) cloud-LLM
call uses the network — the one exception the grading sandbox permits.

## Standard CLI

```
python3 agent_combined.py --contract <path> --invariants <path> --manifest <path> \
        --out <dir> --timeout <sec> --seed <int> --max-attempts <int> [--no-cache]
```
Exit codes: `0` PROVEN · `1` not found in budget · `2` usage/internal error.
Outputs to `--out`: `Exploit.sol` (best/proven candidate) and `attempts.log`.

## Run

```bash
export TRUST404_HARNESS_DIR="$(cd .. && pwd)/harness"   # this bundle ships ../harness
export FOUNDRY_OFFLINE=true                              # solc 0.8.24 is cached
python3 agent_combined.py \
  --contract ../../trust404-track04-participant/targets/OpenVault/src/OpenVault.sol \
  --invariants ../../trust404-track04-participant/targets/OpenVault/Invariants.sol \
  --manifest  ../../trust404-track04-participant/targets/OpenVault/manifest.json \
  --out ./out --timeout 600 --seed 42 --max-attempts 8
cat ./out/attempts.log
```

## Verified (offline, on this machine)

- **FuzzerBrain**: discovered `setOwner` on OpenVault autonomously (shrunk to 1
  call) → synthesized PoC → harness **PROVEN** (`ownerUnchanged`).
- **HeuristicBrain**: BadAccounting unchecked-underflow drain → **PROVEN**.
- Loop mechanics unit-tested without forge/LLM: `python3 selftest_loop.py` (3/3).

## Self-tests

```bash
python3 selftest_loop.py                       # control loop (fast, offline)
python3 selftest_knowledge.py                  # knowledge-card injection (offline)
```

## Notes / limits
- Fuzzer is strong on access-control/arithmetic; weak on reentrancy (needs an
  actor) and puzzle bugs (storage reads, gas). Those fall to the LLM/heuristics.
- The solution cache (`.solution_cache.json`) pins a proven PoC by (target hash,
  seed) so re-runs are byte-identical; use `--no-cache` to disable.
