#!/usr/bin/env bash
# AutoPoC 시연 스크립트 — 클론하면 바로 되는 데모. 문제 3개가 레포에 번들돼 있다
# (demo-targets/). 외부 타깃·형제 폴더가 필요 없다.
#
# 레포 루트에서 실행:
#   로컬 colima:  DC="docker --context colima" bash demo.sh
#   채점 재현:    bash demo.sh
#
# 데모 1,3(취약/정상)은 무키 오프라인. 데모 2(클라우드 일반화)만 ANTHROPIC_API_KEY 필요.
# (블록별로 복붙해 장면마다 나레이션해도 되고, 통째로 실행해도 된다.)

DC="${DC:-docker}"                                          # colima면: DC="docker --context colima"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$(cat ~/.trust404_key 2>/dev/null)}"

# ── 데모 1: 취약 타깃(PiggyBank) → 실행 증명 + 결정론 (오프라인, 무키, 2회) ──
echo "== 데모 1: 취약 타깃 PiggyBank → 실행 증명 + 결정론 (오프라인) =="
rm -rf out/d1a out/d1b && mkdir -p out/d1a out/d1b
for r in a b; do
  $DC run --rm --network=none \
    -v "$PWD/demo-targets/PiggyBank:/work/target:ro" -v "$PWD/out/d1$r:/work/out" \
    autopoc \
    --contract /work/target/src/PiggyBank.sol \
    --invariants /work/target/Invariants.sol \
    --manifest  /work/target/manifest.json \
    --out /work/out --timeout 120 --seed 42 --no-cache
  echo "run $r exit=$?"                                     # 0 = PROVEN
done
cat out/d1a/attempts.log                                    # 1  reentrancy  PROVEN  bankSolvent  (오프라인)
cat out/d1a/Exploit.sol
shasum -a 256 out/d1a/Exploit.sol out/d1b/Exploit.sol       # 두 해시 동일 = 결정론

# ── 데모 2: 클라우드 일반화(LockBox) → 소스 추론으로 증명 (키 필요) ─────────
echo "== 데모 2: LockBox → 클라우드 일반화 (오프라인 두뇌는 키를 못 맞혀 기권, LLM은 소스에서 읽음) =="
if [ -z "$ANTHROPIC_API_KEY" ]; then echo "  (건너뜀: ANTHROPIC_API_KEY 미설정)"; else
  rm -rf out/d2 && mkdir -p out/d2
  $DC run --rm -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    -v "$PWD/demo-targets/LockBox:/work/target:ro" -v "$PWD/out/d2:/work/out" \
    autopoc \
    --contract /work/target/src/LockBox.sol \
    --invariants /work/target/Invariants.sol \
    --manifest  /work/target/manifest.json \
    --out /work/out --timeout 300 --seed 42 --max-attempts 8
  echo "exit=$?"                                            # 0 = PROVEN (클라우드)
  cat out/d2/attempts.log                                   # cloud-llm  PROVEN  boxFunded
  cat out/d2/Exploit.sol                                    # 소스에서 읽은 OPEN_KEY 사용
fi

# ── 데모 3: 정상 타깃(GuardedBank) → 오탐 0 기권 (오프라인, 무키) ───────────
echo "== 데모 3: 정상 타깃 GuardedBank → 오탐 0 기권 (오프라인) =="
rm -rf out/d3 && mkdir -p out/d3
$DC run --rm --network=none \
  -v "$PWD/demo-targets/GuardedBank:/work/target:ro" -v "$PWD/out/d3:/work/out" \
  autopoc \
  --contract /work/target/src/GuardedBank.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 120 --seed 42 --max-attempts 5
echo "exit=$?"                                              # 1 = 기권
cat out/d3/Exploit.sol                                      # "// no candidate" (채택 후보 없음)
