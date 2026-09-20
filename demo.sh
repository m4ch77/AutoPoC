#!/usr/bin/env bash
# AutoPoC 시연 녹화용 명령 스크립트 (세 문제를 한 영상에).
#
# 실행 위치: 레포 루트(track04-agent-mvp/). 형제 폴더로 타깃 번들이 있어야 함:
#   ../trust404-track04-participant/targets  (조직위 공개셋)
#   ../dvd-track4-targets/Truster            (장면 ②, 로컬 보유 포팅 타깃)
#
# 실행 방법:
#   로컬 colima:  DC="docker --context colima" bash demo.sh
#   채점 재현:    bash demo.sh            # 순정 docker (공개셋 = 장면 ①③만)
#
# 클라우드 장면(②)은 ANTHROPIC_API_KEY 필요. 아래는 파일에서 읽어 화면 노출 방지.
# (블록별로 복붙해 장면마다 나레이션해도 되고, 통째로 bash demo.sh 해도 된다.)

DC="${DC:-docker}"                                          # colima면: DC="docker --context colima"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$(cat ~/.trust404_key 2>/dev/null)}"
P=../trust404-track04-participant/targets                   # 조직위 공개셋

# ── 장면 ① 오프라인 증명 + 결정론 (ReentrantVault, --network=none, 2회) ──────
echo "== 장면 ① 오프라인 증명 + 결정론 =="
rm -rf out/d1a out/d1b && mkdir -p out/d1a out/d1b
for r in a b; do
  $DC run --rm --network=none \
    -v "$PWD/$P/ReentrantVault:/work/target:ro" -v "$PWD/out/d1$r:/work/out" \
    autopoc \
    --contract /work/target/src/ReentrantVault.sol \
    --invariants /work/target/Invariants.sol \
    --manifest  /work/target/manifest.json \
    --out /work/out --timeout 150 --seed 42 --no-cache
  echo "run $r exit=$?"                                     # 0 = PROVEN
done
cat out/d1a/attempts.log                                    # 1  reentrancy  PROVEN  vaultSolvent
cat out/d1a/Exploit.sol                                     # 생성된 PoC(무수정)
shasum -a 256 out/d1a/Exploit.sol out/d1b/Exploit.sol       # 두 해시 동일 = 결정론

# ── 장면 ② 클라우드 일반화 (Truster, 키 필요) ──────────────────────────────
echo "== 장면 ② 클라우드 일반화 =="
T=../dvd-track4-targets/Truster                             # 공개 CTF(DVD) 포팅 = 공개셋 외 타깃
rm -rf out/d2 && mkdir -p out/d2
$DC run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$PWD/$T:/work/target:ro" -v "$PWD/out/d2:/work/out" \
  autopoc \
  --contract /work/target/src/TrusterLenderPool.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8
echo "exit=$?"                                              # 0 = PROVEN (클라우드)
cat out/d2/attempts.log                                     # cloud-llm 전략으로 PROVEN

# ── 장면 ③ 오탐 0 (SafeVault, --network=none) ──────────────────────────────
echo "== 장면 ③ 오탐 0 (정상 타깃 기권) =="
rm -rf out/d3 && mkdir -p out/d3
$DC run --rm --network=none \
  -v "$PWD/$P/SafeVault:/work/target:ro" -v "$PWD/out/d3:/work/out" \
  autopoc \
  --contract /work/target/src/SafeVault.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8
echo "exit=$?"                                              # 1 = 기권
cat out/d3/Exploit.sol                                      # "// no candidate" (채택 후보 없음)
