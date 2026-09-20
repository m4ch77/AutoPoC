#!/usr/bin/env bash
# Run the 6 public targets through the shipped image, fully OFFLINE (no key,
# --network=none), and print an honest scoreboard: vuln targets should be PROVEN,
# clean decoys should ABSTAIN (exit 1). This is the offline (worst-case, no-LLM)
# capability of the agent.
set -uo pipefail

BUNDLE="${1:-/Users/jaeho/Workspace/Hackathon/Trust404/trust404-track04-participant}"
IMAGE="${IMAGE:-track04-agent-mvp}"
DOCKER="docker --context ${DOCKER_CONTEXT:-colima}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/out"
mkdir -p "$OUT"
CLEAN=" SafeVault BoundedOwner "   # decoys: correct behavior = NOT proven (abstain)

echo "public-set OFFLINE run (image=$IMAGE, --network=none, NO api key, seed=42)"
printf "%-16s %-6s %-6s %-20s %-22s %s\n" TARGET KIND EXIT TRIAGE VIOLATED VERDICT
proven=0; abstain=0; bad=0
for d in "$BUNDLE"/targets/*/; do
  name=$(basename "$d")
  src=$(python3 -c "import json;print(json.load(open('$d/manifest.json'))['target']['src'])")
  $DOCKER run --rm --network=none -v "$d:/work/target:ro" -v "$OUT:/work/out" "$IMAGE" \
    --contract "/work/target/$src" --invariants /work/target/Invariants.sol \
    --manifest /work/target/manifest.json --out /work/out --timeout 200 --seed 42 \
    >/dev/null 2>"/tmp/ps_$name.log"
  ec=$?
  viol=$(grep -o 'violated=[^)]*' "/tmp/ps_$name.log" | tail -1)
  top=$(grep -o 'top=[a-z_]*' "/tmp/ps_$name.log" | head -1)
  kind="VULN"; case "$CLEAN" in *" $name "*) kind="CLEAN";; esac
  if [ "$kind" = "VULN" ]; then
    if [ "$ec" = 0 ]; then verdict="PROVEN ok"; proven=$((proven+1)); else verdict="MISS !!"; bad=$((bad+1)); fi
  else
    if [ "$ec" = 0 ]; then verdict="FALSE-POSITIVE !!"; bad=$((bad+1)); else verdict="ABSTAIN ok"; abstain=$((abstain+1)); fi
  fi
  printf "%-16s %-6s %-6s %-20s %-22s %s\n" "$name" "$kind" "$ec" "${top:-<none>}" "${viol:-<none>}" "$verdict"
done
echo "----"
echo "offline: proven_vuln=$proven  correct_abstain=$abstain  wrong=$bad"
