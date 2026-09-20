# AutoPoC

**타깃 스마트컨트랙트를 입력받아, 공격이 실제로 성립함을 실행되는 PoC(`Exploit.sol`)로 스스로 증명하는 에이전트.**

AutoPoC는 취약점을 "의심"으로 보고하지 않는다. 후보 익스플로잇을 만들고 **Foundry 하네스로 실제 실행**해서,
불변식(invariant)이 진짜로 깨질 때만 성공으로 인정한다. 깨지 못하면 조용히 기권한다 — 거짓 성공(오탐)을 만들지 않는다.

> TRUST404 Track 04 벤치마크를 위해 만들어졌지만, "타깃 + 불변식 + manifest"를 주면 어떤 컨트랙트에도 동작한다.

---

## 무엇을 하나

- **입력:** 타깃 컨트랙트 소스 · 불변식 컨트랙트(`Invariants.sol`) · `manifest.json`
- **출력:** 불변식을 깨는 `Exploit.sol`(무수정 실행 가능) + 시도 로그(`attempts.log`) + 종료 코드
- **판정:** 오직 `forge` 실행만. 에이전트도 LLM도 "성공"을 선언하지 못한다.

## 핵심 특징

- **실행 증명 게이트** — 모든 후보는 하네스 실행으로만 채택된다. 정답 하드코딩 없음.
- **오프라인 우선 + 결정론** — 퍼저·재진입 브레인·휴리스틱을 클라우드보다 먼저 돌린다. 키/네트워크 없이도 동작하고, 같은 입력엔 바이트 동일한 결과.
- **클라우드 폴백(선택)** — 오프라인 두뇌가 못 잡는 신종은 Anthropic 모델 체인(`sonnet-5 → opus-4-8`)으로 추론. **API 키가 있을 때만** 활성화.
- **오탐 0** — 멀쩡한 타깃은 예산을 다 써도 `exit 1`로 기권.

동작 원리 자세히는 [METHOD.md](METHOD.md), 명령 흐름 데모는 [DEMO.md](DEMO.md) 참고.

---

## 요구 사항

- **Docker** (권장) — 툴체인이 이미지에 고정되어 있어 가장 간단하다.
- 또는 **로컬 실행**: [Foundry](https://book.getfoundry.sh/) `v1.0.0` + Python `3.12` (외부 pip 의존성 없음, 표준 라이브러리만 사용). solc `0.8.24`는 `forge`가 자동으로 받는다.

## 설치 / 빌드 (Docker)

빌드 컨텍스트는 **레포 루트**여야 한다 (`agent/`와 `harness/`의 부모).

```bash
docker build -f agent/Dockerfile -t autopoc .
docker images autopoc          # autopoc:latest 확인
```

---

## API 키 설정

AutoPoC는 **키 없이도** 오프라인 결정론 두뇌만으로 동작한다. 강한 클라우드 추론 브레인을 켜려면 Anthropic API 키가 필요하다.

**1) 키 발급** — [Anthropic Console](https://console.anthropic.com/) → *API Keys* → *Create Key* (`sk-ant-...` 형식).

**2) 키 전달** — 키는 **런타임 환경변수**로만 넘긴다. 이미지에 굽거나 코드/레포에 커밋하지 말 것.

에이전트가 읽는 환경변수 (앞의 것이 우선):

| 변수 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | 기본 키 변수 |
| `LLM_API_KEY` | 대체 키 변수 (위가 없을 때) |

셸에 export 후 Docker로 전달:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."      # 현재 셸 세션에만

docker run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$TARGET:/work/target:ro" -v "$PWD/out:/work/out" \
  autopoc --contract /work/target/src/<Name>.sol \
          --invariants /work/target/Invariants.sol \
          --manifest  /work/target/manifest.json \
          --out /work/out
```

키를 파일에 두고 읽어오는 방식(셸 히스토리에 키가 남지 않음):

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY="$(cat ~/.anthropic_key)" \
  -v "$TARGET:/work/target:ro" -v "$PWD/out:/work/out" \
  autopoc --contract /work/target/src/<Name>.sol \
          --invariants /work/target/Invariants.sol \
          --manifest /work/target/manifest.json --out /work/out
```

**키를 생략하면** 에이전트는 자동으로 오프라인 모드로 degrade 한다 (`--network=none`으로 완전 차단해도 됨).

> 보안: 키를 `Dockerfile`·소스·커밋에 넣지 말 것. `.gitignore`에 키 파일 경로를 추가하고, 런타임에만 주입하세요.

---

## 입력 형식 (타깃 구조)

타깃 디렉터리는 다음을 포함한다:

```
<Target>/
├─ src/<Name>.sol      타깃 컨트랙트
├─ Invariants.sol      checkAll(address) 로 불변식을 평가하는 컨트랙트
├─ manifest.json       메타데이터(아래)
└─ Setup.s.sol         (선택) 배포 셋업 스크립트
```

`manifest.json` 예시:

```json
{
  "target": { "name": "ReentrantVault", "src": "src/ReentrantVault.sol",
              "solc": "0.8.24", "evm_version": "cancun" },
  "deploy": { "mode": "local", "constructor_args": [],
              "value_wei": "10000000000000000000", "setup": "Setup.s.sol" },
  "determinism": { "block_number": 21000000, "block_timestamp": 1735689600, "seed": 42 },
  "invariants": { "contract": "Invariants.sol", "predicates": ["vaultSolvent"] },
  "budget": { "timeout_sec": 300, "max_attempts": 5 }
}
```

---

## 사용법

아래 예시는 레포와 타깃 번들이 같은 부모 디렉터리에 있다고 가정한다.

```bash
TARGET=../trust404-track04-participant/targets/ReentrantVault
mkdir -p out
```

### 1) 클라우드 모드 (키 사용)

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$PWD/$TARGET:/work/target:ro" \
  -v "$PWD/out:/work/out" \
  autopoc \
  --contract /work/target/src/ReentrantVault.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8
```

### 2) 완전 오프라인 모드 (키 없음, 네트워크 차단)

```bash
docker run --rm --network=none \
  -v "$PWD/$TARGET:/work/target:ro" \
  -v "$PWD/out:/work/out" \
  autopoc \
  --contract /work/target/src/ReentrantVault.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8
```

### 3) 로컬 실행 (Foundry + Python)

먼저 한 번, 하네스를 빌드해 `forge-std`와 solc를 준비한다:

```bash
export PATH="$HOME/.foundry/bin:$PATH"
git clone --depth 1 https://github.com/foundry-rs/forge-std harness/lib/forge-std
( cd harness && forge build )
```

그 다음 레포 루트에서 실행 (하네스는 `harness/`에서 자동 탐색, 다른 위치면 `TRUST404_HARNESS_DIR` 지정):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."          # 클라우드 브레인 쓸 때만
python3 agent/agent_combined.py \
  --contract "$TARGET/src/ReentrantVault.sol" \
  --invariants "$TARGET/Invariants.sol" \
  --manifest  "$TARGET/manifest.json" \
  --out ./out --timeout 300 --seed 42 --max-attempts 8
```

### CLI 옵션

| 옵션 | 필수 | 기본값 | 설명 |
|---|:---:|---|---|
| `--contract` | ✓ | — | 타깃 컨트랙트 `.sol` 경로 |
| `--invariants` | ✓ | — | 불변식 컨트랙트(`Invariants.sol`) 경로 |
| `--manifest` | ✓ | — | `manifest.json` 경로 |
| `--out` | ✓ | — | 산출물 출력 디렉터리 |
| `--timeout` | | `600` | 전체 시간 예산(초) |
| `--seed` | | `42` | 결정론 시드(퍼저·캐시 키) |
| `--max-attempts` | | `8` | 최대 시도 횟수 |
| `--no-cache` | | off | 솔루션 캐시 무시(매번 새로 생성 — 결정론 검증용) |

### 환경 변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `ANTHROPIC_API_KEY` / `LLM_API_KEY` | (없음) | 클라우드 LLM 브레인 활성화. 없으면 오프라인 degrade |
| `TRUST404_CLOUD_MODELS` | `claude-sonnet-5,claude-opus-4-8` | 모델 폴백 체인(거부/오류 시 다음 모델) |
| `TRUST404_CLOUD_MODEL` | (없음) | 단일 모델 강제(체인 무시) |
| `TRUST404_MAX_TOKENS` | `16000` | LLM 출력 토큰 상한 |
| `TRUST404_CACHE` | `agent/.solution_cache.json` | 성공 PoC 캐시(재실행 시 바이트 동일 리플레이) |
| `TRUST404_HARNESS_DIR` | 이미지: `/opt/track04/harness` · 로컬: `./harness` | 하네스 위치 |
| `TRUST404_LLM_URL` | `http://localhost:11434` | (선택) 오프라인 로컬 LLM(Ollama) 주소 |
| `TRUST404_LLM_MODEL` | `qwen2.5-coder:7b` | (선택) 로컬 LLM 모델명 |

> 완전 오프라인 로컬 LLM 브레인을 쓰려면 이미지 빌드 때 `--build-arg BAKE_LOCAL_MODEL=1`로 Ollama+모델을 구우면 된다(이미지 커짐, 기본 off).

---

## 출력 & 종료 코드

| exit | 의미 | 산출물 |
|:---:|---|---|
| **0** | PROVEN — 하네스 불변식이 실제로 깨짐 | `out/Exploit.sol` (무수정) + `out/attempts.log` |
| **1** | 예산 내 미발견 → 기권 | `out/attempts.log` (시도 이력) |
| **2** | 사용법 / 내부 오류 | stderr 진단 |

- `out/Exploit.sol` — 채택된 PoC. `function run(address target) external payable` 형태, 무수정.
- `out/attempts.log` — 시도별 `번호 · 브레인 · 전략 · 결과 · 깨진 술어(predicate)`.

## 결정론 / 재현

- 성공한 PoC는 `(타깃 해시, 시드)`로 캐시되어 재실행 시 **바이트 동일**하게 리플레이된다.
- 캐시 없이 생성 경로 자체의 결정론을 검증하려면 `--no-cache`로 반복 실행 → 해시 동일 확인.
- 재현 스크립트: `agent/det_check.sh`(도커 결정론 게이트), `agent/offline_public_v3.sh`(무키 오프라인 스윕).

---

## 데모 & 문서

- **[DEMO.md](DEMO.md)** — 빌드→오프라인 증명→클라우드→기권→결정론까지 복붙 가능한 명령 흐름.
- **[METHOD.md](METHOD.md)** — 접근·아키텍처·탐색·LLM·결정론·한계.
- **피치덱: [docs/AutoPoC-pitch.pdf](docs/AutoPoC-pitch.pdf)** — 문제 정의·위협 모델·검증 결과 (소스: `docs/AutoPoC-pitch.html`).
- **[docs/SOLVE_CONDITIONS_REPORT.md](docs/SOLVE_CONDITIONS_REPORT.md)** · **[docs/COMPLIANCE_AUDIT.md](docs/COMPLIANCE_AUDIT.md)** — 실행 조건·요구사항 감사.

## 레포 구조

```
.
├─ README.md              이 문서
├─ METHOD.md              동작 원리
├─ DEMO.md                명령 흐름 데모
├─ Exploit.sol            산출물 예시(무수정, BadAccounting 언더플로)
├─ agent/                 에이전트 코드 + Dockerfile + 재현 스크립트
│  ├─ agent_combined.py   메인(triage→route→brains→verify)
│  ├─ agent.py agent_general.py triage.py knowledge.py
│  ├─ Dockerfile entrypoint.sh
│  └─ *.sh, selftest_*.py …   재현/자체 테스트
├─ harness/               Foundry 하네스(무변경) — Harness.sol, foundry.toml, test/
└─ docs/                  문서 · 피치덱 · 감사 보고서
```

> `harness/lib/forge-std`, `out/`, 솔루션 캐시는 `.gitignore` 대상(빌드/런타임에 재생성).

## 한계

- 신종·미공개 유형 일반화는 클라우드 키가 있을 때 가장 강하다. 키 없이는 퍼저·재진입·휴리스틱이 커버하는 범위(접근제어·산술·재진입·delegatecall·tx.origin·오라클 등)로 제한된다.
- 로컬 LLM 브레인은 선택 사항이며 이미지에 구웠을 때만 활성화된다.
- 판정은 제공된 하네스/불변식에 종속된다 — 불변식이 표현하지 못하는 공격은 "증명" 대상이 아니다.
