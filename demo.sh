#!/usr/bin/env bash
# AutoPoC 시연 스크립트 — 클론하면 바로 되는 무키 오프라인 데모.
#
# 번들 타깃(demo-targets/)만 쓰므로 API 키도, 외부 타깃 번들도 필요 없다.
# 레포 루트에서 실행:
#   로컬 colima:  DC="docker --context colima" bash demo.sh
#   채점 재현:    bash demo.sh
#
# (블록별로 복붙해 장면마다 나레이션해도 되고, 통째로 실행해도 된다.)
# 선택: 클라우드 일반화 장면은 맨 아래 주석 참고(키 + 외부 타깃 필요).

DC="${DC:-docker}"                                          # colima면: DC="docker --context colima"

# ── 데모 1: 취약 타깃(PiggyBank) → 실행 증명 + 결정론 (오프라인, 무키, 2회) ──
echo "== 데모 1: 취약 타깃 PiggyBank → 실행 증명 + 결정론 =="
rm -rf out/pb_a out/pb_b && mkdir -p out/pb_a out/pb_b
for r in a b; do
  $DC run --rm --network=none \
    -v "$PWD/demo-targets/PiggyBank:/work/target:ro" -v "$PWD/out/pb_$r:/work/out" \
    autopoc \
    --contract /work/target/src/PiggyBank.sol \
    --invariants /work/target/Invariants.sol \
    --manifest  /work/target/manifest.json \
    --out /work/out --timeout 120 --seed 42 --no-cache
  echo "run $r exit=$?"                                     # 0 = PROVEN
done
cat out/pb_a/attempts.log                                   # 1  reentrancy  PROVEN  bankSolvent
cat out/pb_a/Exploit.sol                                    # 생성된 PoC(무수정)
shasum -a 256 out/pb_a/Exploit.sol out/pb_b/Exploit.sol     # 두 해시 동일 = 결정론

# ── 데모 2: 정상 타깃(GuardedBank) → 오탐 0 기권 (오프라인, 무키) ───────────
echo "== 데모 2: 정상 타깃 GuardedBank → 오탐 0 기권 =="
rm -rf out/gb && mkdir -p out/gb
$DC run --rm --network=none \
  -v "$PWD/demo-targets/GuardedBank:/work/target:ro" -v "$PWD/out/gb:/work/out" \
  autopoc \
  --contract /work/target/src/GuardedBank.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 120 --seed 42 --max-attempts 5
echo "exit=$?"                                              # 1 = 기권
cat out/gb/Exploit.sol                                      # "// no candidate" (채택 후보 없음)

# ── (선택) 데모 3: 클라우드 일반화 — 키 + 공개셋 외 타깃 있을 때만 ──────────
# 오프라인 두뇌가 못 잡는 타깃을 클라우드 LLM이 추론으로 증명(self-validation 루프).
# export ANTHROPIC_API_KEY="$(cat ~/.trust404_key)"
# T=../dvd-track4-targets/Truster                           # 로컬 보유 포팅 타깃(레포 미포함)
# rm -rf out/cloud && mkdir -p out/cloud
# $DC run --rm -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
#   -v "$PWD/$T:/work/target:ro" -v "$PWD/out/cloud:/work/out" autopoc \
#   --contract /work/target/src/TrusterLenderPool.sol --invariants /work/target/Invariants.sol \
#   --manifest /work/target/manifest.json --out /work/out --timeout 300 --seed 42 --max-attempts 8
# echo "exit=$?"; cat out/cloud/attempts.log                # cloud-llm#1 실패→피드백→#2 PROVEN
