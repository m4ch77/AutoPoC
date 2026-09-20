#!/usr/bin/env bash
# Determinism gate: run the grading image N times on the SAME target+seed, fully
# offline (--network=none) and with the solution cache DISABLED (--no-cache), and
# assert every run (a) proves the invariant break and (b) emits a byte-identical
# Exploit.sol. --no-cache forces real GENERATION each time (not a cached replay),
# so a single unique hash proves the generation path itself is deterministic.
#
# Usage: bash selftest_determinism.sh [TARGET_DIR] [N]
set -euo pipefail

TARGET="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/trust404-track04-participant/targets/ReentrantVault}"
N="${2:-10}"
IMAGE="${IMAGE:-autopoc}"
DOCKER="docker --context ${DOCKER_CONTEXT:-colima}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/out"
mkdir -p "$OUT"

SRC=$(python3 -c "import json;print(json.load(open('$TARGET/manifest.json'))['target']['src'])")
NAME=$(python3 -c "import json;print(json.load(open('$TARGET/manifest.json'))['target']['name'])")

echo "determinism check: image=$IMAGE target=$NAME N=$N (offline, --no-cache, seed=42)"
hashes=""
fails=0
for i in $(seq 1 "$N"); do
  if $DOCKER run --rm --network=none \
       -v "$TARGET:/work/target:ro" -v "$OUT:/work/out" \
       "$IMAGE" \
       --contract "/work/target/$SRC" \
       --invariants /work/target/Invariants.sol \
       --manifest  /work/target/manifest.json \
       --out /work/out --timeout 200 --seed 42 --no-cache >/dev/null 2>&1; then
    ec=0
  else
    ec=$?
  fi
  h=$(shasum -a 256 "$OUT/Exploit.sol" | awk '{print $1}')
  echo "  run=$i exit=$ec sha=${h:0:16}"
  hashes="${hashes}${h}"$'\n'
  [ "$ec" = "0" ] || fails=$((fails + 1))
done

uniq=$(printf "%s" "$hashes" | sort -u | grep -c .)
echo "unique_exploit_hashes=$uniq  nonzero_exits=$fails"
if [ "$uniq" = "1" ] && [ "$fails" = "0" ]; then
  echo "DETERMINISM PASS: $N/$N proven, byte-identical Exploit.sol"
else
  echo "DETERMINISM FAIL"
  exit 1
fi
