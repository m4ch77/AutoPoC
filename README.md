# AutoPoC

**타깃 스마트컨트랙트를 입력받아, 공격이 실제로 성립함을 실행되는 PoC(`Exploit.sol`)로 스스로 증명하는 에이전트입니다.**

AutoPoC는 취약점을 "의심"으로 보고하지 않습니다. 후보 익스플로잇을 만든 뒤 **Foundry 하네스로 실제 실행**하여,
불변식(invariant)이 실제로 깨질 때에만 성공으로 인정합니다. 깨뜨리지 못하면 조용히 기권하며, 거짓 성공(오탐)을 만들지 않습니다.

## 핵심 특징

- **실행 증명** — 모든 후보는 하네스 실행을 통해서만 채택됩니다. 판정 권한은 하네스에만 있으며(에이전트·LLM은 성공을 선언할 수 없습니다), 정답 하드코딩도 없습니다.
- **결정론 & 일관성** — 성공한 PoC를 `(타깃 해시, 시드)`로 캐시하여, 재실행 시 **바이트 동일**하게 리플레이합니다. LLM 비결정성과 무관합니다.
- **하이브리드 두뇌** — triage로 취약 유형을 분류하여, 유형별 최강 두뇌(퍼저·재진입·휴리스틱)를 먼저 실행하고 **클라우드 LLM으로 폴백**합니다.
- **오탐 0** — 정상 타깃에서는 예산을 모두 소진하더라도 기권합니다(`exit 1`).

---

## 세팅 & 실행

**요구 사항:** Docker · Anthropic API 키.

### 1. API 키 설정

[Anthropic Console](https://console.anthropic.com/) → *API Keys* → *Create Key* 로 `sk-ant-...` 키를 발급받아
환경변수로 등록합니다 (키는 런타임에만 주입하며, 이미지나 코드에는 넣지 마십시오).

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 2. 이미지 빌드

빌드 컨텍스트는 **레포 루트**여야 합니다 (`agent/`와 `harness/`의 부모).

```bash
docker build -f agent/Dockerfile -t autopoc .
```

### 3. 실행

타깃 디렉터리는 읽기 전용으로, 출력 디렉터리는 쓰기 가능으로 마운트하고 API 키를 전달합니다.

```bash
TARGET=../trust404-track04-participant/targets/ReentrantVault
mkdir -p out

docker run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$PWD/$TARGET:/work/target:ro" \
  -v "$PWD/out:/work/out" \
  autopoc \
  --contract /work/target/src/ReentrantVault.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8

echo "exit=$?"     # 0=증명(PROVEN) · 1=기권 · 2=오류
```

결과는 `out/`에 남습니다. **`Exploit.sol`**(채택된 PoC, 무수정)과 **`attempts.log`**(시도별 전략·결과·깨진 술어)가 생성됩니다.

---

## 입력 형식

타깃 디렉터리는 다음을 포함합니다.

```
<Target>/
├─ src/<Name>.sol      타깃 컨트랙트
├─ Invariants.sol      checkAll(address) 로 불변식을 평가
├─ manifest.json       메타데이터(이름·solc·배포·결정론·불변식·예산)
└─ Setup.s.sol         (선택) 배포 셋업
```

`manifest.json` 예시는 다음과 같습니다.

```json
{
  "target": { "name": "ReentrantVault", "src": "src/ReentrantVault.sol", "solc": "0.8.24", "evm_version": "cancun" },
  "deploy": { "mode": "local", "value_wei": "10000000000000000000", "setup": "Setup.s.sol" },
  "determinism": { "block_number": 21000000, "block_timestamp": 1735689600, "seed": 42 },
  "invariants": { "contract": "Invariants.sol", "predicates": ["vaultSolvent"] },
  "budget": { "timeout_sec": 300, "max_attempts": 5 }
}
```

## CLI 옵션

| 옵션 | 필수 | 기본값 | 설명 |
|---|:---:|---|---|
| `--contract` | ✓ | — | 타깃 컨트랙트 `.sol` 경로 |
| `--invariants` | ✓ | — | 불변식 컨트랙트 경로 |
| `--manifest` | ✓ | — | `manifest.json` 경로 |
| `--out` | ✓ | — | 산출물 출력 디렉터리 |
| `--timeout` | | `600` | 전체 시간 예산(초) |
| `--seed` | | `42` | 결정론 시드 |
| `--max-attempts` | | `8` | 최대 시도 횟수 |
| `--no-cache` | | off | 솔루션 캐시 무시(매번 새로 생성) |

## 환경 변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `ANTHROPIC_API_KEY` | (없음) | 클라우드 LLM 브레인 활성화 (대체: `LLM_API_KEY`) |
| `TRUST404_CLOUD_MODELS` | `claude-sonnet-5,claude-opus-4-8` | 모델 폴백 체인(거부/오류 시 다음 모델) |
| `TRUST404_MAX_TOKENS` | `16000` | LLM 출력 토큰 상한 |
| `TRUST404_CACHE` | `agent/.solution_cache.json` | 성공 PoC 캐시(바이트 동일 리플레이) |

> 키를 생략하면 네트워크 없이 오프라인 결정론 두뇌(퍼저·재진입·휴리스틱)만으로 degrade 합니다.

---

## 문서

- **[METHOD.md](METHOD.md)** — 접근·아키텍처·탐색·LLM·결정론·한계.
- **[DEMO.md](DEMO.md)** — 복붙 가능한 명령 흐름 데모.
- **피치덱: [docs/AutoPoC-pitch.pdf](docs/AutoPoC-pitch.pdf)** — 문제 정의·위협 모델·검증 결과.

## 레포 구조

```
.
├─ README.md · METHOD.md · DEMO.md
├─ Exploit.sol            산출물 예시(무수정)
├─ agent/                 에이전트 코드 + Dockerfile + entrypoint + 재현 스크립트
├─ harness/               Foundry 하네스(무변경)
└─ docs/                  문서 · 피치덱 · 감사 보고서
```
