# DEMO — AutoPoC 동작 확인

레포에 **번들 데모 타깃**([`demo-targets/`](demo-targets))이 들어 있어, **클론 → 빌드 → 실행**만으로
API 키·외부 번들 없이 바로 돌아간다. AutoPoC의 핵심 성질(실행 증명 · 결정론 · 오탐 없음)을
한 영상에 보여주는 **녹화 런북**과 상황별 **명령 레퍼런스**를 담는다.

> **Docker 컨텍스트:** 로컬(colima) 시연 명령은 `docker --context colima`를 쓴다(아래 런북에 반영).
> 채점자 재현 시에는 순정 `docker`.
>
> **경로:** 핵심 데모(장면 ①②)는 레포 안의 `demo-targets/`만 쓰므로 **외부 폴더가 필요 없다.**
> (선택 장면 ③ 클라우드만 공개셋 외 타깃을 형제 폴더로 둔다.)

---

## 0. 이미지 빌드 (1회, 녹화 전)

```bash
git clone https://github.com/m4ch77/AutoPoC.git
cd AutoPoC
docker build -f agent/Dockerfile -t autopoc .
docker images autopoc            # autopoc:latest 확인
```

빌드 결과: Foundry `v1.0.0` + solc 0.8.24 + Python 3.12 + 오프라인 두뇌 내장 이미지.

---

## 시연 영상 녹화 스크립트 (≤5분, 클론하면 바로)

핵심 두 장면은 **번들 타깃 + 무키 오프라인**이라 설정이 전혀 없다. 실행은 장면당 약 1초.

> 빌드는 위 0단계에서 미리 끝내 두고, 녹화에서는 실행 장면만 보여준다.
>
> **명령만 순서대로 담은 실행 파일:** [`demo.sh`](demo.sh) — 레포 루트에서
> `DC="docker --context colima" bash demo.sh` 로 한 번에, 또는 장면별로 복붙.

### 준비 (녹화 시작 전)
```bash
cd AutoPoC
docker --context colima images autopoc         # autopoc:latest 존재 확인
```

### 장면 ① 취약 타깃 → 실행 증명 + 결정론 (PiggyBank, 무키, 자동 2회)
번들 취약 타깃을 **네트워크 완전 차단**으로 두 번 실행 → 둘 다 PROVEN, 산출물 **바이트 동일**.
```bash
rm -rf out/pb_a out/pb_b && mkdir -p out/pb_a out/pb_b
for r in a b; do
  docker --context colima run --rm --network=none \
    -v "$PWD/demo-targets/PiggyBank:/work/target:ro" -v "$PWD/out/pb_$r:/work/out" \
    autopoc \
    --contract /work/target/src/PiggyBank.sol \
    --invariants /work/target/Invariants.sol \
    --manifest  /work/target/manifest.json \
    --out /work/out --timeout 120 --seed 42 --no-cache
  echo "run $r exit=$?"                          # 0 = PROVEN
done
cat out/pb_a/attempts.log                        # 1  reentrancy  PROVEN  bankSolvent
cat out/pb_a/Exploit.sol                         # 생성된 PoC(무수정, run(address))
shasum -a 256 out/pb_a/Exploit.sol out/pb_b/Exploit.sol   # 두 해시 동일 = 결정론
```

### 장면 ② 정상 타깃 → 오탐 0 기권 (GuardedBank, 무키)
같은 저금통이지만 checks-effects-interactions로 안전한 버전. 후보가 없어 **기권**한다.
```bash
rm -rf out/gb && mkdir -p out/gb
docker --context colima run --rm --network=none \
  -v "$PWD/demo-targets/GuardedBank:/work/target:ro" -v "$PWD/out/gb:/work/out" \
  autopoc \
  --contract /work/target/src/GuardedBank.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 120 --seed 42 --max-attempts 5
echo "exit=$?"                                   # 1 = 기권
cat out/gb/Exploit.sol                           # "// no candidate" (채택 후보 없음)
```

### 장면 ③ (선택) 클라우드 일반화 — 키 + 공개셋 외 타깃 있을 때만
오프라인 두뇌가 못 잡는 타깃을 **클라우드 LLM**이 추론으로 증명. 로그에 self-validation 루프가 보인다.
```bash
export ANTHROPIC_API_KEY="$(cat ~/.trust404_key)"          # 파일에서 읽어 화면 노출 방지
T=../dvd-track4-targets/Truster                            # 로컬 보유 포팅 타깃(레포 미포함)
rm -rf out/cloud && mkdir -p out/cloud
docker --context colima run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$PWD/$T:/work/target:ro" -v "$PWD/out/cloud:/work/out" \
  autopoc \
  --contract /work/target/src/TrusterLenderPool.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8
echo "exit=$?"                                             # 0 = PROVEN (클라우드)
cat out/cloud/attempts.log                                 # cloud-llm#1 실패 → 피드백 → #2 PROVEN
```
> 자막 권장: **"공개셋 외 포팅 타깃 — 클라우드 추론으로 일반화, 실패는 피드백받아 자가수정."**

### 마무리 컷 — 종료코드 규약
`0` 증명(PROVEN) · `1` 기권 · `2` 사용법/내부 오류. 취약 타깃은 실행된 PoC로 증명하고,
정상 타깃은 기권하며, 같은 입력은 바이트 동일하게 재현된다.

### 편집 메모
- 핵심 장면 ①②는 무키·무설정·각 1초라 컷 편집이 거의 필요 없다.
- 오프닝에 `git clone`(2초)을 넣으면 "공개 레포에서 받은 그대로 동작"을 보여줄 수 있다(빌드는 컷).
- 장면 ③은 선택. 키가 없으면 생략해도 ①②만으로 실행 증명·결정론·오탐 0이 모두 커버된다.

---

## 번들 데모 타깃 ([`demo-targets/`](demo-targets))

| 타깃 | 유형 | 기대 결과 |
|---|---|---|
| `PiggyBank` | 재진입 취약(외부콜 후 상태갱신) | `exit 0` · reentrancy PROVEN · 바이트 동일 |
| `GuardedBank` | 안전(checks-effects-interactions) | `exit 1` · `Exploit.sol = // no candidate` |

> 조직위 공개셋 파일은 재배포하지 않으려고 **직접 작성한 원본 데모 타깃**이다(MIT). 조직위 번들이나
> 미공개 타깃도 같은 CLI로 동일하게 동작한다.

## 명령 레퍼런스 (상황별)

전체 복붙 명령은 위 녹화 스크립트/`demo.sh`에 있다. 상황별 핵심만:

| 목적 | 핵심 실행 | 기대 결과 |
|---|---|---|
| 오프라인 증명 (무키) | `--network=none` + 취약 타깃 | `exit 0` · 결정론 두뇌가 PROVEN |
| 오탐 0 | `--network=none` + 정상 타깃 | `exit 1` · `Exploit.sol = // no candidate` |
| 생성 결정론 | 같은 입력·시드로 `--no-cache` N회 | `Exploit.sol` 해시 동일 |
| 클라우드 일반화 | `-e ANTHROPIC_API_KEY` + 공개셋 외 타깃 | `exit 0` · `cloud-llm` PROVEN |

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
