#!/usr/bin/env bash
# Competition-environment validation driver.
# Runs each target inside the FIXED Docker image with the standard CLI,
# per-manifest timeout/max_attempts, seed 42, cloud brain (sonnet-5) enabled,
# network ON (grading sandbox permits the LLM API exception).
#
# Usage: run_compenv.sh <set>   where <set> = public | ported
set -uo pipefail
export PATH="$HOME/.foundry/bin:$PATH"
KEY="$(cat /Users/jaeho/.trust404_key)"
IMG=track04-agent-mvp
DC="docker --context colima"
ROOT=/Users/jaeho/Workspace/Hackathon/Trust404
SET="${1:-public}"

if [ "$SET" = "public" ]; then
  BASE="$ROOT/trust404-track04-participant/targets"
  OUT="$ROOT/track04-agent-mvp/out/compenv_public"
  # name|srcfile|timeout|attempts|expect(FOUND/ABSTAIN)
  TARGETS=(
    "ReentrantVault|ReentrantVault.sol|300|5|FOUND"
    "OpenVault|OpenVault.sol|300|5|FOUND"
    "BadAccounting|BadAccounting.sol|300|5|FOUND"
    "NaiveOracle|NaiveOracle.sol|600|8|FOUND"
    "SafeVault|SafeVault.sol|300|5|ABSTAIN"
    "BoundedOwner|BoundedOwner.sol|300|5|ABSTAIN"
  )
else
  OUT="$ROOT/track04-agent-mvp/out/compenv_ported"
  # dir path is either dvd-track4-targets or cte-track4-targets
  TARGETS=(
    "Truster|dvd-track4-targets/Truster|TrusterLenderPool.sol|300|8|FOUND"
    "SideEntrance|dvd-track4-targets/SideEntrance|SideEntranceLenderPool.sol|300|8|FOUND"
    "Unstoppable|dvd-track4-targets/Unstoppable|UnstoppableVault.sol|300|8|FOUND"
    "Raffle|cte-track4-targets/Raffle|Raffle.sol|300|8|FOUND"
    "TokenBazaar|cte-track4-targets/TokenBazaar|TokenBazaar.sol|300|8|FOUND"
    "SlotBoard|cte-track4-targets/SlotBoard|SlotBoard.sol|300|8|FOUND"
    "GuildToken|cte-track4-targets/GuildToken|GuildToken.sol|300|8|FOUND"
    "Ledger|cte-track4-targets/Ledger|Ledger.sol|300|8|FOUND"
  )
fi

rm -rf "$OUT"; mkdir -p "$OUT"
SUM="$OUT/SUMMARY.tsv"
printf "target\texit\ttime_s\tverdict\tbrain\tattempts\texpect\tok\n" > "$SUM"

for row in "${TARGETS[@]}"; do
  IFS='|' read -r name a b c d e <<< "$row"
  if [ "$SET" = "public" ]; then
    tdir="$BASE/$name"; src="$a"; to="$b"; att="$c"; expect="$d"
  else
    tdir="$ROOT/$a"; src="$b"; to="$c"; att="$d"; expect="$e"
  fi
  odir="$OUT/$name"; mkdir -p "$odir"
  echo "### RUN $name (timeout=$to attempts=$att expect=$expect) ###"
  t0=$(date +%s)
  $DC run --rm \
    -e ANTHROPIC_API_KEY="$KEY" \
    -e TRUST404_CLOUD_MODEL=claude-sonnet-5 \
    -v "$tdir:/work/target:ro" \
    -v "$odir:/work/out" \
    "$IMG" \
    --contract "/work/target/src/$src" \
    --invariants /work/target/Invariants.sol \
    --manifest /work/target/manifest.json \
    --out /work/out \
    --timeout "$to" --seed 42 --max-attempts "$att" \
    > "$odir/run.log" 2>&1
  ec=$?
  t1=$(date +%s); dt=$((t1-t0))
  verdict=$(grep -Eo '^(PROVEN|ABSTAIN|ERROR)' "$odir/run.log" | tail -1)
  [ -z "$verdict" ] && verdict="?"
  brain=$(grep -E '\] PROVEN:' "$odir/run.log" | tail -1 | sed -E 's/^[0-9]+ \[([^/]+)\/.*/\1/')
  [ -z "$brain" ] && brain="-"
  attempts=$(grep -Ec '^[0-9]+ \[' "$odir/run.log")
  # ok check
  ok="NO"
  if [ "$expect" = "FOUND" ] && [ "$ec" = "0" ]; then ok="YES"; fi
  if [ "$expect" = "ABSTAIN" ] && [ "$ec" = "1" ]; then ok="YES"; fi
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$name" "$ec" "$dt" "$verdict" "$brain" "$attempts" "$expect" "$ok" >> "$SUM"
  echo "  -> exit=$ec time=${dt}s verdict=$verdict brain=$brain attempts=$attempts ok=$ok"
done

echo "=== SUMMARY ($SET) ==="
cat "$SUM"
echo "ALL_DONE_$SET"
