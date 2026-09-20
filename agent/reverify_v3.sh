#!/usr/bin/env bash
# Re-verify the V3 image: offline (no key) coverage incl. the 2 new templates,
# determinism on the new templates, and one cloud run on the default chain.
set -uo pipefail
DC="docker --context colima"
IMG=track04-agent-mvp
ROOT=/Users/jaeho/Workspace/Hackathon/Trust404
N="$ROOT/neutral-track4-targets"
OUT="$ROOT/track04-agent-mvp/out/reverify_v3"; rm -rf "$OUT"; mkdir -p "$OUT"

run_off () {  # target reps
  local t="$1" reps="$2"
  for r in $(seq 1 "$reps"); do
    local od="$OUT/off_${t}_r${r}"; mkdir -p "$od"
    $DC run --rm --network=none -v "$N/$t:/work/target:ro" -v "$od:/work/out" "$IMG" \
      --contract "/work/target/src/$t.sol" --invariants /work/target/Invariants.sol \
      --manifest /work/target/manifest.json --out /work/out --timeout 150 --seed 42 --max-attempts 8 --no-cache >"$od/run.log" 2>&1
    local ec=$?; local sha=$(shasum -a 256 "$od/Exploit.sol" 2>/dev/null | cut -c1-16)
    local brain=$(grep -E '\] PROVEN:' "$od/run.log" | tail -1 | sed -E 's/^[0-9]+ \[([^/]+)\/.*/\1/')
    echo "  OFFLINE $t r$r exit=$ec brain=${brain:--} sha=$sha"
    if [ "$r" = 2 ]; then
      if diff -q "$OUT/off_${t}_r1/Exploit.sol" "$od/Exploit.sol" >/dev/null 2>&1; then echo "    -> $t BYTE_IDENTICAL"; else echo "    -> $t DIFFER"; fi
    fi
  done
}

echo "== OFFLINE (--network=none, no key) =="
run_off Fallout 1
run_off Reentrance 1
run_off Telephone 1
run_off Delegation 2     # new template + determinism
run_off Elevator 2       # new template + determinism

echo "== CLOUD (default chain sonnet-5 -> opus-4-8), GatekeeperTwo, 1 run =="
od="$OUT/cloud_GatekeeperTwo"; mkdir -p "$od"
$DC run --rm -e ANTHROPIC_API_KEY="$(cat /Users/jaeho/.trust404_key)" \
  -v "$N/GatekeeperTwo:/work/target:ro" -v "$od:/work/out" "$IMG" \
  --contract /work/target/src/GatekeeperTwo.sol --invariants /work/target/Invariants.sol \
  --manifest /work/target/manifest.json --out /work/out --timeout 300 --seed 42 --max-attempts 8 --no-cache >"$od/run.log" 2>&1
ec=$?; brain=$(grep -E '\] PROVEN:' "$od/run.log" | tail -1 | sed -E 's/^[0-9]+ \[([^/]+)\/.*/\1/')
echo "  CLOUD GatekeeperTwo exit=$ec brain=${brain:--}"
echo "REVERIFY_DONE"
