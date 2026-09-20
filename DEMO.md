# DEMO — AutoPoC 동작 확인

레포에 **데모 문제 3개**가 번들돼 있어([`demo-targets/`](demo-targets)), **클론 → 빌드 → 실행**만으로
외부 폴더 없이 세 장면(실행 증명 · 클라우드 일반화 · 오탐 0)이 다 돌아간다.

> **Docker 컨텍스트:** 로컬(colima) 시연 명령은 `docker --context colima`를 쓴다(아래 런북에 반영).
> 채점자 재현 시에는 순정 `docker`.
>
> **경로/키:** 세 장면 모두 레포 안의 `demo-targets/`만 쓰므로 **외부 폴더가 필요 없다.**
> 데모 1·3(취약/정상)은 **무키 오프라인**, 데모 2(클라우드 일반화)만 `ANTHROPIC_API_KEY`가 필요하다.

---

## 0. 클론 + 이미지 빌드 (1회, 녹화 전)

```bash
git clone https://github.com/m4ch77/AutoPoC.git
cd AutoPoC
docker build -f agent/Dockerfile -t autopoc .
docker images autopoc            # autopoc:latest 확인
```

빌드 결과: Foundry `v1.0.0` + solc 0.8.24 + Python 3.12 + 오프라인 두뇌 내장 이미지.

---

## 시연 영상 녹화 스크립트 (≤5분, 클론하면 3개 다 됨)

각 코드블록이 **"한 번 복붙"** 단위다. 통째로 붙여넣고 → 끝나면 다음 블록. **전부 같은 터미널**에서.
번들 타깃이라 외부 폴더가 필요 없고, 실행은 장면당 1~4초다.

> **명령만 담은 실행 파일:** [`demo.sh`](demo.sh) — `DC="docker --context colima" bash demo.sh` 로 한 번에도 가능.

### 준비 (녹화 시작 전)
```bash
cd AutoPoC
docker --context colima images autopoc                     # autopoc:latest 확인
export ANTHROPIC_API_KEY="$(cat ~/.trust404_key)"          # 데모 2(클라우드)용. 화면 노출 안 됨
```

### 장면 ① 취약 타깃 → 실행 증명 + 결정론 (PiggyBank, 무키·오프라인, 자동 2회)
```bash
rm -rf out/d1a out/d1b && mkdir -p out/d1a out/d1b
for r in a b; do
  docker --context colima run --rm --network=none \
    -v "$PWD/demo-targets/PiggyBank:/work/target:ro" -v "$PWD/out/d1$r:/work/out" \
    autopoc \
    --contract /work/target/src/PiggyBank.sol \
    --invariants /work/target/Invariants.sol \
    --manifest  /work/target/manifest.json \
    --out /work/out --timeout 120 --seed 42 --no-cache
  echo "run $r exit=$?"                          # 0 = PROVEN
done
cat out/d1a/attempts.log                         # 1  reentrancy  PROVEN  bankSolvent  ← 오프라인
shasum -a 256 out/d1a/Exploit.sol out/d1b/Exploit.sol   # 두 해시 동일 = 결정론
```

### 장면 ② 클라우드 일반화 (LockBox, 키 필요)
인출 키가 소스에 박힌 타깃. 퍼저는 256비트 키를 못 맞혀 오프라인은 기권하지만, LLM은 소스에서 읽어 푼다.
```bash
rm -rf out/d2 && mkdir -p out/d2
docker --context colima run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$PWD/demo-targets/LockBox:/work/target:ro" -v "$PWD/out/d2:/work/out" \
  autopoc \
  --contract /work/target/src/LockBox.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8
echo "exit=$?"                                   # 0 = PROVEN
cat out/d2/attempts.log                          # cloud-llm  PROVEN  boxFunded  ← 클라우드
cat out/d2/Exploit.sol                           # 소스에서 읽은 OPEN_KEY 사용
```

### 장면 ③ 정상 타깃 → 오탐 0 기권 (GuardedBank, 무키·오프라인)
```bash
rm -rf out/d3 && mkdir -p out/d3
docker --context colima run --rm --network=none \
  -v "$PWD/demo-targets/GuardedBank:/work/target:ro" -v "$PWD/out/d3:/work/out" \
  autopoc \
  --contract /work/target/src/GuardedBank.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 120 --seed 42 --max-attempts 5
echo "exit=$?"                                   # 1 = 기권
cat out/d3/Exploit.sol                           # "// no candidate" (채택 후보 없음)
```

### 마무리 컷 — 종료코드 규약
`0` 증명(PROVEN) · `1` 기권 · `2` 사용법/내부 오류. 취약 타깃은 실행된 PoC로 증명하고,
정상 타깃은 기권하며, 같은 입력은 바이트 동일하게 재현된다.

### 편집 메모
- 오프닝에 `git clone`(2초)을 넣으면 "공개 레포에서 받은 그대로 동작"을 보여줄 수 있다(빌드는 컷).
- 오프라인/클라우드 구분: `attempts.log` 두 번째 칸이 `reentrancy`/`fuzzer`/`heuristic`이면 오프라인,
  `cloud-llm`이면 클라우드. 장면 ①③은 `--network=none`이라 물리적으로 오프라인이다.

---

## 번들 데모 타깃 ([`demo-targets/`](demo-targets))

| 타깃 | 유형 | 경로(오프라인/클라우드) | 기대 결과 |
|---|---|---|---|
| `PiggyBank` | 재진입 취약(외부콜 후 상태갱신) | 오프라인 · 무키 | `exit 0` · reentrancy PROVEN · 바이트 동일 |
| `LockBox` | 키가 소스에 박힌 접근제어 | 클라우드(키 필요) | `exit 0` · cloud-llm PROVEN (소스에서 키 추론) |
| `GuardedBank` | 안전(checks-effects-interactions) | 오프라인 · 무키 | `exit 1` · `Exploit.sol = // no candidate` |

> 조직위 공개셋을 재배포하지 않으려고 **직접 작성한 원본 데모 타깃**이다(MIT). 조직위 번들이나
> 미공개 타깃도 같은 CLI로 동일하게 동작한다.

## 명령 레퍼런스 (상황별)

전체 복붙 명령은 위 녹화 스크립트/`demo.sh`에 있다. 상황별 핵심만:

| 목적 | 핵심 실행 | 기대 결과 |
|---|---|---|
| 오프라인 증명 (무키) | `--network=none` + 취약 타깃 | `exit 0` · 결정론 두뇌가 PROVEN |
| 클라우드 일반화 | `-e ANTHROPIC_API_KEY` + 소스추론 타깃 | `exit 0` · `cloud-llm` PROVEN |
| 오탐 0 | `--network=none` + 정상 타깃 | `exit 1` · `Exploit.sol = // no candidate` |
| 생성 결정론 | 같은 입력·시드로 `--no-cache` N회 | `Exploit.sol` 해시 동일 |

도커 이미지에서 결정론을 한 번에 검증(오프라인 N=3 + 클라우드 캐시 리플레이): `bash agent/det_check.sh`.

---

## 종료코드 · 산출물 규약

| exit | 의미 | 산출물 |
|---|---|---|
| **0** | PROVEN (하네스 불변식 실제 파손) | `out/Exploit.sol` (무수정) + `out/attempts.log` |
| **1** | 예산 내 미발견 → 기권 | `out/attempts.log` (후보가 없으면 빈 로그 + `Exploit.sol = // no candidate`) |
| **2** | 사용법/내부 오류 | stderr 진단 |

## 실측 요약 (최종 이미지, 대회 타깃)

| 세트 | 결과 | 비고 |
|---|---|---|
| 공개 6 | 6/6 | 취약 4 발견 + 멀쩡 2 기권, **전부 오프라인** |
| 포팅(미공개 유형) 8 | 8/8 | 클라우드 폴백, 전부 예산 내 |
| 종료코드 | 14/14 정확 | 발견=0 / 기권=1 |
| 결정론 | 바이트 동일 | 오프라인 N=3 · 클라우드 캐시 리플레이 |

상세 근거: [docs/SOLVE_CONDITIONS_REPORT.md](docs/SOLVE_CONDITIONS_REPORT.md) ·
[docs/COMPLIANCE_AUDIT.md](docs/COMPLIANCE_AUDIT.md)
