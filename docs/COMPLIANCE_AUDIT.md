# TRUST404 Track04 — 요구사항 적합성 감사 (대회 제공 파일 캐시 없이 재정독 기준)

감사 방법: 대회 번들(`trust404-track04-participant/`)의 모든 파일을 처음 읽듯 다시 정독하고,
각 요구사항을 **고정 Docker 이미지 V3(`343ffed166f4`)** 실측으로 대조했다. 판정: ✅ 충족 ·
⚠️ 조건부/주의 · ❌ 미충족.

정독한 파일: `PARTICIPANT.md`, `MANIFEST.md`, `DETERMINISM.md`, `METHOD.md`(양식),
`Exploit.example.sol`, `harness/README.md`, `harness/src/Harness.sol`,
`scripts/validate-submission.mjs`, `targets/*/manifest.json`. (`RUBRIC.md`은 문서들이 참조하나
번들에 **미포함** — 아래 G3.)

---

## A. PARTICIPANT.md — 핵심 규칙 / 제출 / CLI / 필수 준수

| # | 요구사항 | 상태 | 근거 (실측/코드) |
|---|---|---|---|
| A1 | 제출물 3종: 에이전트(repo+Dockerfile) · METHOD.md · Exploit.sol(무수정) | ✅ | 공식 검사기 `validate-submission.mjs track04-agent-mvp` → **통과**(오류 0/경고 0). `agent/Dockerfile`, `METHOD.md`, 루트 `Exploit.sol`(BadAccounting 언더플로, 에이전트 산출물) 존재 |
| A2 | 표준 CLI 7개 인자(`--contract/--invariants/--manifest/--out/--timeout/--seed/--max-attempts`) | ✅ | `agent_combined.py` argparse가 7개 모두 파싱; 검사기가 문서에서 7개 확인 |
| A3 | 종료코드 0 발견 · 1 예산내 미발견 · 2 사용법/내부오류 | ✅ | 실측: 발견→0, 기권→1, 없는 파일(내부오류)→2, argparse(사용법)→2 |
| A4 | 출력 `Exploit.sol`(최선 후보) + `attempts.log`(번호·전략·결과·깨진 술어) | ✅ | attempts.log 예: `1⇥heuristic⇥access-control:set-owner⇥PROVEN⇥ownerUnchanged`(번호·두뇌·전략·결과·술어) |
| A5 | Foundry(forge) 표준, Hardhat 불가 | ✅ | 검증·퍼징 모두 `forge test`; 하네스=조직위 원본(바이트 동일) |
| A6 | 결정론 게이트②: 고정 Docker(solc0.8.24/forge핀), 같은 seed+manifest→같은 결과, block/time는 manifest 고정 | ✅ | V3 이미지 solc0.8.24. 같은 Exploit.sol N=10 재실행 판정 동일; 오프라인 두뇌 산출물 **바이트 동일**(예 Delegation `7d47910f…`, Elevator `5e4cffca…` r1=r2). PoC는 tx.origin/타임스탬프 난수 미사용 |
| A7 | 네트워크 차단 · `mode:"fork"` 금지 · local | ✅ | 전 타깃 local; `--network=none`로 오프라인 정탐 확인; 네트워크는 **LLM API 예외**만 사용 |
| A8 | LLM 허용(`ANTHROPIC_API_KEY`/`LLM_API_KEY`), **키 없어도 오프라인 degrade** | ✅ | 키 없으면 CloudLLMBrain no-op; **오프라인만으로 공개 취약 4/4 + 중립 5/6 정탐**; `selftest_loop`가 무키 degrade 검증 |
| A9 | 유효제출: 취약 4 중 ≥1 정탐 + 멀쩡 2 종료코드 1 | ✅ | 공개 취약 4/4 발견, 멀쩡 SafeVault/BoundedOwner 기권(exit1) |
| A10 | 외부 라이브러리 import 금지(자기완결, remappings 없이 컴파일) | ✅ | 생성 Exploit.sol은 interface+contract만, import 없음(검사기 no-import 확인) |
| A11 | LLM 키 하드코딩 금지(환경변수만) | ✅ | 키는 env(`ANTHROPIC_API_KEY`/`LLM_API_KEY`)에서만 로드, 소스에 없음 |
| A12 | 비공개 3개 일반화 | ⚠️ | 중립 Ethernaut 6종 대리측정: 오프라인 5/6 + 클라우드로 6/6. 단 오라클 템플릿은 NaiveOracle **형태 특화**(이름 기반)라 리네임된 비공개 오라클은 클라우드로 넘어감(G2). 퍼저·재진입은 이름 비의존 |

## B. MANIFEST.md — 매니페스트 스키마 / 하네스 규약

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| B1 | schema `trust404.track04.manifest/0.1`, target(name/src/solc0.8.24/evm cancun), deploy, determinism, invariants, budget 파싱 | ✅ | 에이전트가 manifest에서 target/invariants/determinism 읽어 배포·시간 고정; 우리 포팅 타깃도 스키마 준수 |
| B2 | Exploit는 `run(address) payable`, 하네스가 10 ETH(`DEFAULT_EXPLOIT_FUNDING_WEI`) 지급 | ✅ | 생성 Exploit.sol 모두 `function run(address) external payable`; 재진입 PoC가 그 종잣돈 사용 |
| B3 | `value_wei` 문자열(BigInt) 처리 | ✅ | 하네스 `_parseDecimal`가 처리; 에이전트는 python json으로 읽음 |

## C. DETERMINISM.md — 게이트 ②

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| C1 | 같은 `Exploit.sol`을 하네스로 **N=10회(확정)** 실행 → PROVEN/`firstViolated` 전부 동일 | ✅ | 게이트는 **PoC 재실행**(forge, 에이전트/API 무관)이라 EVM 결정론으로 충족. 우리 PoC는 비결정 요소 미사용 |
| C2 | Docker(버전핀·네트워크차단)에서 재현 | ✅ | V3 이미지 `--network=none` 재현 확인 |
| C3 | METHOD.md §5에 **생성 단계** 결정론 서술 | ✅ | METHOD §5: 오프라인 두뇌 결정론 + 클라우드는 솔루션 캐시로 바이트 동일 리플레이 |

## D. METHOD.md(양식) — 제출물 B

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| D1 | 6개 섹션(접근/아키텍처/탐색/LLM/결정론/한계) 전부 | ✅ | 우리 METHOD.md 1~6 + §7(종료코드·대회환경) |
| D2 | LLM 사용 여부 명시 + 무키 degrade 설명 | ✅ | §4: 폴백 체인 sonnet-5→opus-4-8, 무키 시 오프라인 |
| D3 | 결정론(특히 LLM 비결정성) 처리 | ✅ | §5: 검증 게이트+캐시가 흡수 |
| D4 | 한계 솔직 서술 | ✅ | §6 + DVD/COMPARISON 보고서의 한계절 |
| D5 | 하드코딩 정답 아님(거짓 서술 금지) | ✅ | 타깃별 정답 하드코딩 없음; 모든 후보는 소스/퍼징/추론에서 유도되고 하네스로만 채택 |

## E. RUBRIC.md(참조되나 번들 미포함)

| # | 기준 | 상태 | 근거 |
|---|---|---|---|
| E1 | ④ 스스로 찾은 경로(사람 PoC 위장=실격) | ✅ | 에이전트 생성 + 실행 검증 게이트; 정답 하드코딩 없음(비공개 재실행으로 검증 가능) |
| E2 | ⑤ 일반화(비공개) | ⚠️ | 중립셋 대리측정만 가능(A12/G1) |
| E3 | ⑥ 최소 PoC 간결성 | ✅ | 생성 PoC는 단일 목적·자기완결(대략 15~40줄) |
| E4 | RUBRIC.md 원문 확인 | ⚠️ | 번들에 **없음** → 정확한 배점/세부기준 미확인(G3) |

## F. harness/README.md · Harness.sol

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| F1 | 판정은 `IInvariants.checkAll`만; 5단계 파이프라인 | ✅ | 우리 검증기가 조직위 하네스를 그대로 호출(하네스 diff=IDENTICAL) |
| F2 | 무인자 생성자만 deployCode, 인자 있으면 `Setup.s.sol` | ✅ | 우리 포팅 타깃은 Setup.s.sol 경로 사용 |
| F3 | 레이아웃 관례(`src/<Name>.sol:<Name>`, `Invariants`, `Setup`) | ✅ | 준수 |

---

## G. 런타임 / 이미지 / 입력 조건 (실측 대조)

| # | 조건 | 상태 | 근거 |
|---|---|---|---|
| G-1 | 입력 방식: `--contract/--invariants/--manifest` 절대경로 인자, `--out`에 출력 | ✅ | 하드코딩 경로 없음 → 채점기 마운트 레이아웃과 무관 |
| G-2 | ENTRYPOINT가 CLI 인자 전달 | ✅ | `entrypoint.sh`가 `$@`→`agent_combined.py` (조직위 baseline `python3 agent.py`와 기능 동일) |
| G-3 | FOUNDRY_VERSION 핀 | ✅ | 우리 `v1.0.0` = 조직위 baseline Dockerfile `v1.0.0` (harness 주석 "1.7.1"은 로컬 sanity 노트) |
| G-4 | solc 0.8.24 | ✅ | harness/foundry.toml `solc="0.8.24"`, forge가 svm으로 받아 이미지 캐시 |
| G-5 | harness/foundry.toml | ✅ | 조직위와 **바이트 동일**(evm cancun·optimizer 200·via_ir false·bytecode_hash none) → 바이트코드 동일 |
| G-6 | Harness.sol | ✅ | 조직위와 **바이트 동일**(diff IDENTICAL) |
| G-7 | 빌드 컨텍스트 | ✅ | 번들 루트에서 `-f agent/Dockerfile` |
| G-8 | 네트워크 모델 | ✅ | 빌드때만 다운로드; 런타임 `--network=none` 동작 확인, LLM API만 예외 |

## 일반화(비공개 신종) — 정정된 프레이밍

- **키 주입 시(LLM 허용): 강함.** 클라우드 LLM이 신종 일반화를 담당 — 우리가 시도한 낯선 타깃
  전부 성공(중립 6/6 incl. 암호식 게이트 + DVD/CTE 8/8 + 최난도 3/3 = 23/23).
- **키 없음(오프라인 채점): 흔한 단일컨트랙트 클래스만.** 공개 4/4 + 재진입/접근제어/tx.origin/
  언더플로/delegatecall/콜백. 암호식·신종-난도는 미탐.
- **거부: 폴백 체인이 방어**(sonnet-5→opus-4-8).
- 즉 실질 리스크는 "신종을 못 푼다"가 아니라 **"키 미주입 오프라인 채점에서 암호식/신종-난도"**로 국한.

## 갭 / 주의 항목 (정직하게)

- **G1 (핵심): 오프라인 채점 시 클라우드-전용 클래스는 미탐.** 키가 주입되지 않으면 암호식
  게이트(GatekeeperTwo류)·완전 신종 유형은 못 푼다. 완화: 오프라인 티어가 이제 **공개 4/4 +
  흔한 클래스(재진입·접근제어·tx.origin·언더플로·delegatecall·콜백)**를 커버 → 공개셋은 무키로도
  전부 처리. 남는 위험은 "무키 + 비공개 신종".
- **G2: 오라클 템플릿은 NaiveOracle 형태 특화.** `_oracle_manip`가 `borrow`/`spotPrice`/
  `swap*` 이름을 봐서, 리네임된 비공개 오라클은 오프라인 미스 → 클라우드로 넘어감. (퍼저·재진입·
  접근제어·콜백·delegatecall 템플릿은 이름 비의존이라 이 문제 적음.)
- **G3: `RUBRIC.md` 번들 미포함.** 정확한 배점/세부 실격 조건은 `PARTICIPANT.md` 참조 문구로만
  추정. 원문 확보 권장.
- **G4: 클라우드 결정론은 캐시 의존.** 단 게이트②는 PoC 재실행이라 저위험. 채점기가 **에이전트를**
  N회 재실행해 동일 Exploit.sol을 기대한다면(문서상으론 아님), 공개셋 캐시 베이킹으로 대비 가능.
- **G5: opus-4-8 폴백은 모델 가용성·정책 의존.** 그래서 단일 고정이 아니라 체인으로 뒀고, 1순위
  sonnet-5가 거의 다 처리한다.

## 종합 판정

- **형식 게이트(A1~A5, A10~A11): 전부 ✅** — 공식 검사기 통과.
- **결정론 게이트②(A6, C1~C3): ✅** — N=10 재현·오프라인 바이트 동일·PoC 비결정 요소 없음.
- **정오탐(A9): ✅** — 공개 취약 4/4 + 멀쩡 2 기권.
- **무키 degrade(A8): ✅** — 오프라인만으로 공개 4/4 + 중립 5/6.
- **일반화(A12/E2): ⚠️** — 대리측정 양호하나 무키+신종은 잔여 위험(G1/G2).
- **미확인: RUBRIC.md 원문(G3).**

우리 에이전트는 대회의 **형식·결정론·정오탐·무키 degrade 요구를 모두 충족**하며, 유일한 실질
리스크는 "키 미주입 채점에서 비공개 신종/암호식 유형"이다(오프라인 티어 확장으로 상당 부분 완화).

## 실측 증거 — 무키 오프라인 공개셋 스윕 (V3 이미지, `--network=none`)

| 타깃 | 성격 | exit | 두뇌 | 기대 | 판정 |
|---|---|---|---|---|---|
| ReentrantVault | 취약 | 0 | reentrancy | 0 | ✅ |
| OpenVault | 취약 | 0 | fuzzer | 0 | ✅ |
| BadAccounting | 취약 | 0 | heuristic | 0 | ✅ |
| NaiveOracle | 취약 | 0 | heuristic | 0 | ✅ |
| SafeVault | 멀쩡 | 1 | — | 1 | ✅ |
| BoundedOwner | 멀쩡 | 1 | — | 1 | ✅ |

**키 없이 오프라인만으로 공개 취약 4/4 정탐 + 멀쩡 2/2 기권(exit1). 신규 템플릿이 멀쩡 타깃에
거짓양성 없음(정오탐 회귀 통과).**

## 증거 재현
```bash
node trust404-track04-participant/scripts/validate-submission.mjs track04-agent-mvp   # 형식 게이트
bash track04-agent-mvp/agent/offline_public_v3.sh                                      # 무키 오프라인 공개 6
bash track04-agent-mvp/agent/reverify_v3.sh                                            # 오프라인 정탐+결정론+클라우드
bash track04-agent-mvp/agent/run_compenv.sh public                                     # 공개 6 대회환경
# 오프라인 공개셋(무키): docker ... --network=none ...  (공개 취약 4/4 정탐, 멀쩡 2 exit1)
```
