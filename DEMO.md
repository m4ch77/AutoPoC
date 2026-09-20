# DEMO — AutoPoC 동작 확인 명령 흐름

시연/재현용 명령 흐름. 각 시나리오는 **하네스가 실제로 불변식을 깨야만 성공**하는
AutoPoC의 핵심 성질(실행 증명 · 결정론 · 오탐 없음 · 클라우드 일반화)을 하나씩 보여준다.

> **Docker 컨텍스트:** 채점 환경은 표준 `docker`. 로컬(colima)에서 시연할 땐 아래 모든
> `docker`를 `docker --context colima`로 바꿔 실행한다.
>
> **경로 전제:** 이 레포(`track04-agent-mvp/`)와 조직위 번들
> `trust404-track04-participant/`가 같은 부모 디렉터리에 있다고 가정한다.

---

## 0. 이미지 빌드 (1회)

```bash
# 컨텍스트 = 레포 루트(agent/ + harness/ 의 부모)
docker build -f agent/Dockerfile -t autopoc .

docker images autopoc            # autopoc:latest 확인
```

빌드 결과: Foundry `v1.0.0` + solc 0.8.24 + Python 3.12 + 오프라인 두뇌 내장 이미지.

---

## 시나리오 A — 오프라인 결정론 증명 (키 없음, 네트워크 차단)

재진입 취약점을 **인터넷 완전 차단(`--network=none`)** 상태에서 결정론 두뇌만으로 증명한다.
클라우드 없이도 성립함을 보이는 흐름.

```bash
TARGET=../trust404-track04-participant/targets/ReentrantVault
mkdir -p out

docker run --rm --network=none \
  -v "$PWD/$TARGET:/work/target:ro" \
  -v "$PWD/out:/work/out" \
  autopoc \
  --contract /work/target/src/ReentrantVault.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8

echo "exit=$?"     # -> 0 (PROVEN)
```

**예상:** 수 초 내 `PROVEN` · `exit=0` · 사용 두뇌 = 재진입 브레인 (LLM 미사용).

### 산출물 확인
```bash
cat out/attempts.log        # 시도별 번호·전략·결과·깨진 술어(predicate)
echo "----- Exploit.sol -----"
cat out/Exploit.sol         # 채택된 PoC (무수정, run(address) payable)
shasum -a 256 out/Exploit.sol
```

`attempts.log`에 성공 시도의 전략명과 하네스가 깬 불변식이 남고, `Exploit.sol`은
**에이전트가 수정 없이 낸 그대로**의 실행 가능한 PoC다.

---

## 시나리오 B — 클라우드 일반화 (미공개/신종 타깃, 키 필요)

오프라인 두뇌가 유형을 못 잡는 타깃은 **클라우드 LLM 폴백 체인(sonnet-5 → opus-4-8)** 이
소스를 추론해 PoC를 합성한다. 정답 하드코딩·파일 접근 없이 추론만으로 일반화.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."     # 허용된 LLM API 예외
TARGET=<채점 측이 마운트하는 임의 타깃 디렉터리>   # 예: 신규/미공개 타깃

docker run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$TARGET:/work/target:ro" \
  -v "$PWD/out:/work/out" \
  autopoc \
  --contract /work/target/src/<Target>.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8

echo "exit=$?"     # -> 0 (PROVEN), 후보는 하네스 실행으로만 채택
```

> 실측: 포팅한 미공개 유형 타깃 8종(Truster/SideEntrance/Unstoppable/Raffle/TokenBazaar/
> SlotBoard/GuildToken/Ledger) 전부 예산 내 발견. 오프라인 우선 라우팅이라 클라우드는
> 결정론 두뇌가 못 잡을 때만 개입한다.

---

## 시나리오 C — 멀쩡한 타깃은 기권 (오탐 없음)

취약하지 않은 타깃에 대해서는 **거짓 성공을 만들지 않는다**. 예산을 소진해도 하네스가
깨지지 않으면 `exit 1`로 기권한다.

```bash
TARGET=../trust404-track04-participant/targets/SafeVault

docker run --rm --network=none \
  -v "$PWD/$TARGET:/work/target:ro" \
  -v "$PWD/out:/work/out" \
  autopoc \
  --contract /work/target/src/SafeVault.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8

echo "exit=$?"     # -> 1 (예산 내 미발견, 기권)
```

**예상:** `exit=1` · `Exploit.sol` 미채택. 판정 권한은 하네스뿐이므로 에이전트가
"의심"을 성공으로 승격시키지 않는다.

---

## 시나리오 D — 결정론 검증 (바이트 동일 재현)

같은 입력·시드로 반복 실행 시 결과가 **바이트 단위로 동일**함을 보인다.
- Part A: 오프라인 두뇌 `--no-cache` N=3 신규 실행 → 3회 모두 동일 해시.
- Part B: 클라우드로 푼 타깃 → 1회차 해결+캐시, 2회차 캐시 리플레이 → 동일.

```bash
# 스크립트는 로컬 colima 컨텍스트 기준 (키는 $ANTHROPIC_API_KEY, 없으면 $HOME/.trust404_key에서 읽음)
bash agent/det_check.sh
# -> 각 타깃 "BYTE_IDENTICAL", 마지막 "DET_DONE"
```

수동 확인(오프라인만):
```bash
for r in 1 2 3; do
  docker run --rm --network=none \
    -v "$PWD/../trust404-track04-participant/targets/ReentrantVault:/work/target:ro" \
    -v "$PWD/out/det_r$r:/work/out" autopoc \
    --contract /work/target/src/ReentrantVault.sol --invariants /work/target/Invariants.sol \
    --manifest /work/target/manifest.json --out /work/out --timeout 150 --seed 42 --no-cache >/dev/null 2>&1
  shasum -a 256 out/det_r$r/Exploit.sol
done
# -> 세 해시가 동일해야 함
```

---

## 종료코드 · 산출물 규약

| exit | 의미 | 산출물 |
|---|---|---|
| **0** | PROVEN (하네스 불변식 실제 파손) | `out/Exploit.sol` (무수정) + `out/attempts.log` |
| **1** | 예산 내 미발견 → 기권 | `out/attempts.log` (시도 이력) |
| **2** | 사용법/내부 오류 | stderr 진단 |

## 실측 요약 (최종 이미지)

| 세트 | 결과 | 비고 |
|---|---|---|
| 공개 6 | 6/6 | 취약 4 발견 + 멀쩡 2 기권, **전부 오프라인** |
| 포팅(미공개 유형) 8 | 8/8 | 클라우드 폴백, 전부 예산 내 |
| 종료코드 | 14/14 정확 | 발견=0 / 기권=1 |
| 결정론 | 바이트 동일 | 오프라인 N=3 · 클라우드 캐시 리플레이 |

상세 근거: [docs/SOLVE_CONDITIONS_REPORT.md](docs/SOLVE_CONDITIONS_REPORT.md) ·
[docs/COMPLIANCE_AUDIT.md](docs/COMPLIANCE_AUDIT.md)
