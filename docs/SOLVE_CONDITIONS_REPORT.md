# 대회 문제풀이 조건 준수 보고서 (Track04)

최종 제출 이미지 **V4(`183feaedde6f`, `autopoc:latest`)** 에서 공개 6 + 포팅 8 = **14타깃**을
대회 파이프라인(고정 Docker · 표준 CLI · 매니페스트 예산 · seed 42 · 클라우드 sonnet-5 primary)으로
실행하고, 대회가 요구한 조건별로 대조했다.

## 0. 요약

| 항목 | 결과 |
|---|---|
| 정탐/오탐 | **취약 12/12 발견(exit0) · 멀쩡 2/2 기권(exit1)** — 오탐 0 |
| 시간 예산(`timeout_sec`) | **14/14 예산 내.** 최장 취약=GuildToken 88s(예산 300s의 29%), 최장 전체=멀쩡 184s(61%) |
| 시도 예산(`max_attempts`) | **14/14 예산 내.** 최다 시도=SlotBoard 2회(예산 5~8) |
| 종료코드 계약(0/1/2) | **14/14 정확** |
| 결정론(게이트②) | 오프라인 두뇌 바이트 동일(N=3), 클라우드 캐시 리플레이 바이트 동일 |

## 1. 대회가 요구한 문제풀이 조건 (출처)

| # | 조건 | 근거 |
|---|---|---|
| C1 | **종료코드**: `0` 발견 · `1` 예산 내 미발견 · `2` 사용법/내부오류 | PARTICIPANT.md |
| C2 | **`budget.timeout_sec`**: 전체 제한 시간(분석·생성·검증·서브프로세스 전부 포함) | MANIFEST.md / CLI `--timeout` |
| C3 | **`budget.max_attempts`**: 후보 생성 최대 시도 | MANIFEST.md / CLI `--max-attempts` |
| C4 | **결정론 게이트②**: 같은 `seed`+매니페스트 → 매번 같은 결과. 같은 `Exploit.sol`을 하네스로 **N=10회** 재실행해 `PROVEN`/`firstViolated` 동일 | DETERMINISM.md |
| C5 | **정오탐**: 취약 4 중 ≥1 발견 + **멀쩡 2는 반드시 exit1** | PARTICIPANT.md |
| C6 | **결정론 고정값**: `block_number=21000000`, `block_timestamp=1735689600`, `seed=42` (vm.roll/warp) | 매니페스트 `determinism` |
| C7 | Foundry(forge) · local 배포 · 네트워크 차단(LLM API만 예외) · 외부 import 금지 | PARTICIPANT.md |

> 참고: 게이트②는 **에이전트를 N회 재실행하는 게 아니라, 나온 `Exploit.sol` 하나를 하네스로 N=10회
> 재실행**한다. 따라서 아래 "실제 시간"은 에이전트가 PoC를 **1회 생성**하는 데 걸린 시간이고,
> 재현성은 그 PoC의 결정론적 실행으로 판정된다.

## 2. 공개셋 6 — 조건 준수 (V4 실측)

| 타깃 | 성격 | 예산 timeout/att | 실제 시간 | 시간 여유 | 실제 시도 | 종료코드 | 기대 | 두뇌 | 결정론 |
|---|---|---|---|---|---|---|---|---|---|
| ReentrantVault | 취약·재진입 | 300s / 5 | 1s | ✅ 0.3% | 1 | **0** | 0 발견 | reentrancy | 오프라인·바이트동일(N=3) |
| OpenVault | 취약·접근제어 | 300s / 5 | 1s | ✅ | 1 | **0** | 0 발견 | fuzzer | 오프라인·바이트동일(N=3) |
| BadAccounting | 취약·언더플로 | 300s / 5 | 2s | ✅ | 1 | **0** | 0 발견 | heuristic | 오프라인·결정론 |
| NaiveOracle | 취약·오라클 | 600s / 8 | 1s | ✅ 0.2% | 1 | **0** | 0 발견 | heuristic | 오프라인·결정론 |
| SafeVault | **멀쩡** | 300s / 5 | 183s | ✅ 61% | 0 | **1** | 1 기권 | — | — |
| BoundedOwner | **멀쩡** | 300s / 5 | 184s | ✅ 61% | 0 | **1** | 1 기권 | — | — |

- 취약 4/4가 **키 없이 오프라인 두뇌만으로** 예산 내 발견(재진입/퍼저/휴리스틱). 멀쩡 2/2 기권(exit1).
- 멀쩡 타깃 183~184s: 퍼저 캠페인 + 클라우드 1회 호출(취약점이 없어 max_tokens까지 사고 후 빈응답)
  → 정상 기권. **예산 300s 대비 61%로 여유 안**. 만약 채점이 `--timeout`을 더 짧게 줘도, 마감 시
  미발견(exit1)이 되므로 결과는 동일(기권).

## 3. 포팅셋 8 — 조건 준수 (V4 실측, DVD 3 + CTE 5)

| 타깃 | 유형 | 예산 timeout/att | 실제 시간 | 시간 여유 | 실제 시도 | 종료코드 | 기대 | 두뇌 | 결정론 |
|---|---|---|---|---|---|---|---|---|---|
| Truster | DVD·arbitrary-call | 300s / 8 | 5s | ✅ | 1 | **0** | 0 | cloud-llm | 캐시 리플레이·바이트동일 |
| SideEntrance | DVD·flashloan-콜백 | 300s / 8 | 6s | ✅ | 1 | **0** | 0 | cloud-llm | 캐시 리플레이 |
| Unstoppable | DVD·토큰기부 | 300s / 8 | 5s | ✅ | 1 | **0** | 0 | cloud-llm | 캐시 리플레이 |
| Raffle | CTE·약한난수 | 300s / 8 | 11s | ✅ | 1 | **0** | 0 | cloud-llm | 캐시 리플레이 |
| TokenBazaar | CTE·오버플로 | 300s / 8 | 13s | ✅ | 1 | **0** | 0 | cloud-llm | 캐시 리플레이 |
| SlotBoard | CTE·임의스토리지쓰기 | 300s / 8 | 9s | ✅ | 2 | **0** | 0 | cloud-llm | 캐시 리플레이 |
| GuildToken | CTE·멀티계정 언더플로 | 300s / 8 | 88s | ✅ 29% | 1 | **0** | 0 | cloud-llm | 캐시 리플레이 |
| Ledger | CTE·접근제어 | 300s / 8 | 2s | ✅ | 1 | **0** | 0 | fuzzer | 오프라인·바이트동일(N=3) |

- 8/8 발견(exit0), 전부 300s·8시도 예산 내. Ledger는 오프라인 퍼저, 나머지는 클라우드.
- GuildToken(최난도, 멀티컨트랙트 Helper 익스플로잇)은 88s로 예산의 29% — `max_tokens=16000`이 사고+
  코드 생성에 충분해야 성립(캡을 4000으로 낮췄을 때 truncation으로 미탐 회귀 → 16000 복원으로 해결).

## 4. 결정론 (게이트②) — 실측

- **오프라인 두뇌(진짜 결정론):** `--no-cache` N=3 재실행 **바이트 동일**
  - ReentrantVault[reentrancy] `8d87269d…` · OpenVault[fuzzer] `0c3f0335…` · Ledger[fuzzer] `28937430…`
  - BadAccounting/NaiveOracle/Delegation/Elevator의 휴리스틱 템플릿도 고정 문자열이라 결정론.
- **클라우드 두뇌(캐시 리플레이 결정론):** 성공 PoC를 `(타깃 해시, seed)`로 캐싱 → 재실행 시 바이트 동일
  - Truster run1(생성) `c21029a4…` = run2(캐시 히트, "PROVEN from cache") `c21029a4…`
- PoC 자체가 tx.origin/타임스탬프 난수에 의존하지 않아, 하네스 N=10 재실행 시 EVM 결정론으로 동일 판정.

## 5. 여유·주의 (정직하게)

- **시간 여유:** 취약 타깃은 전부 예산의 30% 이하(최장 GuildToken 88s/300s). 멀쩡 타깃만 ~61%로
  가장 빠듯하나 300s 안. 클라우드 응답 시간은 실행마다 변동(LLM)하지만 **발견/종료코드는 불변**이고,
  마감 초과 시에도 미발견(exit1)로 안전.
- **시도 여유:** 최다 2회(SlotBoard). 예산 5~8에 크게 못 미침.
- **`max_tokens=16000` 트레이드오프:** 멀쩡 타깃의 클라우드 1회 호출이 사고 토큰을 끝까지 태워
  ~183s가 걸린다(예산 내). 폴백은 **거부(refusal)일 때만** 발동하므로 멀쩡 타깃에서 opus로 넘어가
  이중 과금하지 않는다.
- **무키 채점 시:** 공개 취약 4/4는 오프라인으로 그대로 발견(위 표의 두뇌가 offline). 포팅셋의
  클라우드 의존 타깃은 키가 있어야 발견.

## 6. 재현

```bash
docker --context colima build -f agent/Dockerfile -t autopoc .   # 고정 이미지
bash agent/full_pass_v3.sh            # 공개6 + 포팅8 (클라우드) + 결정론
# 개별: agent/run_compenv.sh {public|ported} · agent/det_check.sh
# 무키 오프라인 공개셋: agent/offline_public_v3.sh
```
결과 원본: `out/compenv_public/SUMMARY.tsv`, `out/compenv_ported/SUMMARY.tsv`, `out/determinism/`.
