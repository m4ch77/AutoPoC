# TRUST404 Track 04 — Autonomous Exploit-Proof Agent

타깃 스마트컨트랙트를 입력받아 **공격이 실제로 성립함을 실행되는 PoC(`Exploit.sol`)로 스스로 증명**하는
에이전트. "의심"을 보고서로 남기지 않는다 — 조직위 하네스의 `IInvariants.checkAll`이 실제로 깨져야만
성공으로 인정한다.

## 제출물 (스펙 3종)

| # | 파일 | 내용 |
|---|---|---|
| A | [`agent/`](agent/) + [`agent/Dockerfile`](agent/Dockerfile) | 에이전트 코드 + 컨테이너 |
| B | [`METHOD.md`](METHOD.md) | 접근·아키텍처·탐색·LLM·결정론·한계 |
| C | [`Exploit.sol`](Exploit.sol) | 에이전트 산출물 예시(무수정, BadAccounting 언더플로) |

## 빠른 시작

### Docker (채점과 동일 조건)
```bash
# 빌드 (컨텍스트 = 이 레포 루트: agent/ + harness/ 의 부모)
docker build -f agent/Dockerfile -t track04-agent-mvp .

# 타깃 디렉터리는 채점 측이 마운트로 제공한다(예: 조직위 번들의 targets/<Name>).
TARGET=../trust404-track04-participant/targets/ReentrantVault

# 클라우드 LLM 켜고 실행 (허용된 LLM API 예외만 네트워크 사용)
docker run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$TARGET:/work/target:ro" \
  -v "$PWD/out:/work/out" \
  track04-agent-mvp \
  --contract /work/target/src/ReentrantVault.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8

# 완전 오프라인 (키 없음) — 결정론 도구만으로 degrade
docker run --rm --network=none -v "$TARGET:/work/target:ro" \
  -v "$PWD/out:/work/out" track04-agent-mvp \
  --contract /work/target/src/ReentrantVault.sol --invariants /work/target/Invariants.sol \
  --manifest /work/target/manifest.json --out /work/out --timeout 300 --seed 42 --max-attempts 8
```

### 로컬 (Foundry + Python 3.12)
```bash
export PATH="$HOME/.foundry/bin:$PATH"
export TRUST404_HARNESS_DIR="$PWD/harness"     # 하네스 위치
python3 agent/agent_combined.py --contract <타깃.sol> --invariants <Invariants.sol> \
  --manifest <manifest.json> --out ./out --timeout 300 --seed 42 --max-attempts 8
```

### 종료코드 · 출력
- **0** 발견(PROVEN) · **1** 예산 내 미발견(기권) · **2** 사용법/내부 오류
- `--out/Exploit.sol` (최선 후보, 무수정) · `--out/attempts.log` (시도별 번호·전략·결과·깨진 술어)

## 환경변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `ANTHROPIC_API_KEY` / `LLM_API_KEY` | (없음) | 있으면 클라우드 LLM 활성. **없으면 오프라인으로 degrade** |
| `TRUST404_CLOUD_MODELS` | `claude-sonnet-5,claude-opus-4-8` | 모델 폴백 체인(거부/오류 시 다음 모델) |
| `TRUST404_CLOUD_MODEL` | (없음) | 단일 모델 강제(체인 무시) |
| `TRUST404_MAX_TOKENS` | `16000` | LLM 출력 토큰 상한(멀티컨트랙트 익스플로잇 여유) |
| `TRUST404_HARNESS_DIR` | 이미지: `/opt/track04/harness` | 하네스 위치 |
| `TRUST404_CACHE` | `agent/.solution_cache.json` | 성공 PoC 캐시(재현 시 바이트 동일 리플레이) |

## 동작 방식 (요약, 자세히는 [METHOD.md](METHOD.md))

```
입력 → triage(정적 분류) → 라우팅(오프라인 우선) → 검증 게이트(forge)
   ├─ 오프라인 결정론 두뇌: 퍼저 · 재진입 브레인 · 휴리스틱 템플릿
   └─ 클라우드 LLM 폴백 체인(sonnet-5 → opus-4-8), 키 있을 때만
          ↓ 각 후보
      forge 하네스로 실제 실행 → checkAll 깨지면 PROVEN, 아니면 다음 후보
```
- **오프라인 우선**: 싼 결정론 두뇌를 클라우드보다 먼저 → 결정론 강화 + API 비용 절감.
- **판정 권한은 하네스뿐**: 에이전트도 LLM도 성공을 선언하지 않는다.
- **정답 하드코딩 없음**: 모든 후보는 소스/퍼징/추론에서 유도되고 하네스 실행으로만 채택.

## 레포 구조

```
track04-agent-mvp/
├─ README.md              이 문서
├─ METHOD.md              제출물 B
├─ Exploit.sol            제출물 C (에이전트 산출물, 무수정)
├─ agent/                 제출물 A — 에이전트 코드 + Dockerfile + 테스트/재현 스크립트
│  ├─ agent_combined.py   메인(triage→route→brains→verify) · agent.py/agent_general.py
│  ├─ triage.py knowledge.py
│  ├─ Dockerfile entrypoint.sh
│  └─ selftest_*.py/.sh, run_compenv.sh, det_check.sh, offline_public_v3.sh, full_pass_v3.sh …
├─ harness/               조직위 하네스(무변경) — Harness.sol, foundry.toml, test/
└─ docs/                  분석·검증 보고서
   ├─ SOLVE_CONDITIONS_REPORT.md   문제풀이 조건(시간/시도/종료코드/결정론) 준수표
   └─ COMPLIANCE_AUDIT.md          대회 요구사항 항목별 감사
```
> `harness/lib/forge-std`, `out/`, 솔루션 캐시는 `.gitignore` 대상(빌드 시 재생성/런타임 산출물).

## 검증 · 재현

```bash
node ../trust404-track04-participant/scripts/validate-submission.mjs .   # 형식 게이트(PASS)
bash agent/full_pass_v3.sh        # 공개6 + 포팅8 (클라우드) + 결정론
bash agent/offline_public_v3.sh   # 무키 오프라인 공개셋 (취약 4/4 + 멀쩡 2 exit1)
python3 agent/selftest_loop.py && python3 agent/selftest_knowledge.py   # 오프라인 단위테스트
```

**최종 이미지 실측(요약):** 공개 6/6(취약 4 발견 + 멀쩡 2 기권) · 포팅 8/8 발견 · 전부 예산 내 ·
종료코드 14/14 정확 · 결정론 바이트 동일. 상세는 [docs/SOLVE_CONDITIONS_REPORT.md](docs/SOLVE_CONDITIONS_REPORT.md).
