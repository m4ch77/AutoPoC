#!/usr/bin/env bash
# Offline (no key, --network=none) public-set sweep on the V3 image.
# Confirms: 4 vuln -> exit 0 (offline), 2 clean -> exit 1 (no false positives).
set -uo pipefail
DC="docker --context colima"
IMG=autopoc
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
P="${TRUST404_BUNDLE:-$ROOT/trust404-track04-participant}/targets"
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/out/offline_public_v3"
rm -rf "$OUT"; mkdir -p "$OUT"
printf "target\texit\tbrain\texpect\tok\n" > "$OUT/SUMMARY.tsv"
for row in "ReentrantVault:0" "OpenVault:0" "BadAccounting:0" "NaiveOracle:0" "SafeVault:1" "BoundedOwner:1"; do
  t="${row%%:*}"; exp="${row##*:}"; od="$OUT/$t"; mkdir -p "$od"
  $DC run --rm --network=none -v "$P/$t:/work/target:ro" -v "$od:/work/out" "$IMG" \
    --contract "/work/target/src/$t.sol" --invariants /work/target/Invariants.sol \
    --manifest /work/target/manifest.json --out /work/out --timeout 300 --seed 42 --max-attempts 8 --no-cache >"$od/run.log" 2>&1
  ec=$?
  brain=$(grep -E '\] PROVEN:' "$od/run.log" | tail -1 | sed -E 's/^[0-9]+ \[([^/]+)\/.*/\1/')
  [ -z "$brain" ] && brain="-"
  ok=$([ "$ec" = "$exp" ] && echo YES || echo NO)
  printf "%s\t%s\t%s\t%s\t%s\n" "$t" "$ec" "$brain" "$exp" "$ok" | tee -a "$OUT/SUMMARY.tsv"
done
echo "=== OFFLINE PUBLIC (V3, no key) ==="; cat "$OUT/SUMMARY.tsv"; echo OFFLINE_PUBLIC_DONE
