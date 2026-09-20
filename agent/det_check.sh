#!/usr/bin/env bash
# Determinism verification in the FIXED Docker image (Gate2, DETERMINISM.md).
#  Part A: offline deterministic brains (fuzzer/reentrancy) with --no-cache,
#          N=3 fresh runs must be BYTE-IDENTICAL (true determinism, no cache).
#  Part B: cloud-solved target -> run1 solves+caches, run2 replays from cache,
#          must be BYTE-IDENTICAL ("PROVEN from cache").
set -uo pipefail
KEY="$(cat /Users/jaeho/.trust404_key)"
IMG=track04-agent-mvp
DC="docker --context colima"
ROOT=/Users/jaeho/Workspace/Hackathon/Trust404
OUT="$ROOT/track04-agent-mvp/out/determinism"
rm -rf "$OUT"; mkdir -p "$OUT"

echo "=== Part A: offline deterministic brains, --no-cache, N=3 fresh runs ==="
OFF=(
  "ReentrantVault|trust404-track04-participant/targets/ReentrantVault|ReentrantVault.sol|reentrancy"
  "OpenVault|trust404-track04-participant/targets/OpenVault|OpenVault.sol|fuzzer"
  "Ledger|cte-track4-targets/Ledger|Ledger.sol|fuzzer"
)
for row in "${OFF[@]}"; do
  IFS='|' read -r name dir src brain <<< "$row"
  tdir="$ROOT/$dir"
  shas=""
  for r in 1 2 3; do
    odir="$OUT/A_${name}_r${r}"; mkdir -p "$odir"
    $DC run --rm \
      -v "$tdir:/work/target:ro" -v "$odir:/work/out" \
      "$IMG" \
      --contract "/work/target/src/$src" --invariants /work/target/Invariants.sol \
      --manifest /work/target/manifest.json --out /work/out \
      --timeout 150 --seed 42 --no-cache > "$odir/run.log" 2>&1
    s=$(shasum -a 256 "$odir/Exploit.sol" | cut -c1-16)
    shas="$shas $s"
  done
  uniq=$(echo $shas | tr ' ' '\n' | sort -u | grep -c .)
  if [ "$uniq" = "1" ]; then verdict=BYTE_IDENTICAL; else verdict=DIFFER; fi
  echo "  $name [$brain]: shas=[$shas ] distinct=$uniq -> $verdict"
done

echo "=== Part B: cloud-solved target, cache replay byte-identical ==="
CDIR="$ROOT/dvd-track4-targets/Truster"
rm -f "$OUT/cache.json"
for r in 1 2; do
  odir="$OUT/B_Truster_r${r}"; mkdir -p "$odir"
  $DC run --rm \
    -e ANTHROPIC_API_KEY="$KEY" -e TRUST404_CLOUD_MODEL=claude-sonnet-5 \
    -e TRUST404_CACHE=/work/cache/cache.json \
    -v "$CDIR:/work/target:ro" -v "$odir:/work/out" -v "$OUT:/work/cache" \
    "$IMG" \
    --contract /work/target/src/TrusterLenderPool.sol --invariants /work/target/Invariants.sol \
    --manifest /work/target/manifest.json --out /work/out \
    --timeout 300 --seed 42 > "$odir/run.log" 2>&1
  s=$(shasum -a 256 "$odir/Exploit.sol" | cut -c1-16)
  fc=$(grep -c "PROVEN from cache" "$odir/run.log")
  echo "  Truster run$r: sha=$s from_cache_hits=$fc"
done
if diff -q "$OUT/B_Truster_r1/Exploit.sol" "$OUT/B_Truster_r2/Exploit.sol" >/dev/null; then
  echo "  Truster: BYTE_IDENTICAL (run1 cloud+cache, run2 replay)"
else
  echo "  Truster: DIFFER"
fi
echo "DET_DONE"
