# Track 04 — Improved Exploit-Proving Agent (MVP)

Reads a target contract + `Invariants.sol` + `manifest.json`, generates candidate
`Exploit.sol` PoCs, and **verifies each one for real** through the official
harness (`harness/src/Harness.sol` via `forge test`). It emits the first PoC that
actually makes `Invariants.checkAll` return `false`, or **abstains** (exit 1) when
nothing breaks — so it does not fabricate exploits on clean contracts.

## Standard CLI

```
python3 agent.py --contract <path> --invariants <path> --manifest <path> --out <dir> \
                 --timeout <sec> --seed <int> --max-attempts <int>
```

Exit codes: `0` found (PROVEN) · `1` not found in budget · `2` usage/internal error.
Outputs to `--out`: `Exploit.sol` (best candidate) and `attempts.log`
(one line per attempt: number, strategy, result, violated predicate / note).

## Results on the public target set (offline, no LLM key)

| Target | Expected | Agent | Strategy | Violated |
|---|---|---|---|---|
| ReentrantVault | vulnerable | **PROVEN** | reentrancy | `vaultSolvent` |
| OpenVault | vulnerable | **PROVEN** | access-control (set-owner) | `ownerUnchanged` |
| BadAccounting | vulnerable | **PROVEN** | unchecked-underflow drain (2-step) | `vaultSolvent` |
| NaiveOracle | vulnerable | **PROVEN** | oracle price manipulation | `protocolSolvent` |
| SafeVault | clean | **exit 1** (abstain) | — | — |
| BoundedOwner | clean | **exit 1** (abstain) | — | — |

4/4 vulnerable proven, 0 false positives on the 2 clean targets. (The provided
baseline agent solves 2/4 — it misses BadAccounting and NaiveOracle.)

## Run locally (no Docker)

```bash
# point at the harness (this bundle ships a copy under ../harness)
export TRUST404_HARNESS_DIR="$(cd .. && pwd)/harness"
# one-time: forge-std + solc 0.8.24 (needs network once)
git -C "$TRUST404_HARNESS_DIR" clone --depth 1 https://github.com/foundry-rs/forge-std lib/forge-std
forge build --root "$TRUST404_HARNESS_DIR"

python3 agent.py \
  --contract ../../trust404-track04-participant/targets/BadAccounting/src/BadAccounting.sol \
  --invariants ../../trust404-track04-participant/targets/BadAccounting/Invariants.sol \
  --manifest ../../trust404-track04-participant/targets/BadAccounting/manifest.json \
  --out ./out --timeout 300 --seed 42 --max-attempts 5
cat ./out/attempts.log
```

## Docker (build once with network, run offline)

```bash
# from the bundle root (parent of agent/ and harness/)
docker build -f agent/Dockerfile -t autopoc .
docker run --rm --network=none \
  -v "$PWD/../trust404-track04-participant/targets/BadAccounting:/work/target:ro" \
  -v "$PWD/out:/work/out" \
  autopoc \
  --contract /work/target/src/BadAccounting.sol \
  --invariants /work/target/Invariants.sol \
  --manifest /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 5
```

## LLM (optional)

If `ANTHROPIC_API_KEY` (or `LLM_API_KEY`) is set, the agent tries one LLM-authored
candidate first (temperature 0), then falls back to the verified offline
heuristics. With `--network=none` or no key, it runs offline only. The key is
read from the environment; never hard-code it.
