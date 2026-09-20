# DEMO — AutoPoC 동작 확인

AutoPoC의 핵심 성질(실행 증명 · 결정론 · 오탐 없음 · 클라우드 일반화)을 한 번에 보여주는
**녹화용 런북**과, 상황별 **명령 레퍼런스**를 담는다. 모든 성공은 하네스가 실제로 불변식을
깨야만 인정된다.

> **Docker 컨텍스트:** 로컬(colima) 시연 명령은 `docker --context colima`를 쓴다(아래 런북에 반영).
> 채점자 재현 시에는 순정 `docker`.
>
> **경로 전제:** 이 레포(`track04-agent-mvp/`)와 조직위 번들
> `trust404-track04-participant/`가 같은 부모 디렉터리에 있다고 가정한다.

---

## 0. 이미지 빌드 (1회, 녹화 전)

```bash
# 컨텍스트 = 레포 루트(agent/ + harness/ 의 부모)
docker build -f agent/Dockerfile -t autopoc .
docker images autopoc            # autopoc:latest 확인
```

빌드 결과: Foundry `v1.0.0` + solc 0.8.24 + Python 3.12 + 오프라인 두뇌 내장 이미지.

---

## 시연 영상 녹화 스크립트 (≤5분, 세 문제를 한 영상에)

세 장면은 서로 다른 평가 항목을 커버하므로 **한 영상에 모두** 담는다. 오프라인 실행은
장면당 약 1초, 클라우드도 5초 내외라 실행 시간은 총 10초 남짓 — 5분은 설명·화면 전환용으로 충분하다.

> 빌드는 위 0단계에서 미리 끝내 두고, 녹화에서는 실행 장면만 보여준다.

### 준비 (녹화 시작 전)

```bash
cd track04-agent-mvp
docker --context colima images autopoc        # autopoc:latest 존재 확인 (미리 빌드)

# 키는 파일에서 읽어 화면에 노출되지 않게 (없으면 export ANTHROPIC_API_KEY="sk-ant-...")
export ANTHROPIC_API_KEY="$(cat ~/.trust404_key)"

P=../trust404-track04-participant/targets      # 조직위 공개셋
```

### 장면 ① 오프라인 증명 + 결정론 — 평가 ①실행 위반 · ②결정론 · ④자체 도출
재진입 취약점을 **네트워크 완전 차단**으로 두 번 실행 → 둘 다 PROVEN, 산출물 **바이트 동일**.

```bash
rm -rf out/d1a out/d1b && mkdir -p out/d1a out/d1b
for r in a b; do
  docker --context colima run --rm --network=none \
    -v "$PWD/$P/ReentrantVault:/work/target:ro" -v "$PWD/out/d1$r:/work/out" \
    autopoc \
    --contract /work/target/src/ReentrantVault.sol \
    --invariants /work/target/Invariants.sol \
    --manifest  /work/target/manifest.json \
    --out /work/out --timeout 150 --seed 42 --no-cache
  echo "run $r exit=$?"                         # 0 = PROVEN
done
cat out/d1a/attempts.log                        # 1  reentrancy  PROVEN  vaultSolvent
cat out/d1a/Exploit.sol                         # 생성된 PoC(무수정, run(address))
shasum -a 256 out/d1a/Exploit.sol out/d1b/Exploit.sol   # 두 해시 동일 = 결정론
```

### 장면 ② 클라우드 일반화 — 평가 ⑤미공개 일반화 · ④자체 도출
오프라인 두뇌가 못 잡는 타깃을 **클라우드 LLM**이 소스 추론으로 증명(파일·정답 접근 없음).

```bash
T=../dvd-track4-targets/Truster                 # 공개 CTF(DVD) 포팅 = 공개셋 외 타깃
rm -rf out/d2 && mkdir -p out/d2
docker --context colima run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v "$PWD/$T:/work/target:ro" -v "$PWD/out/d2:/work/out" \
  autopoc \
  --contract /work/target/src/TrusterLenderPool.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8
echo "exit=$?"                                  # 0 = PROVEN (클라우드)
cat out/d2/attempts.log                         # cloud-llm 전략으로 PROVEN
```
> 자막 권장: **"공개 CTF(DVD)를 트랙 형식으로 포팅한, 공개셋 외 타깃 — 클라우드 추론으로 일반화."**
> 타깃 디렉터리 내용은 화면에 띄우지 말 것(R&D 레퍼런스 파일 포함). 산출물은 `out/d2`에서 확인.

### 장면 ③ 오탐 0 — 평가 ③정상 컨트랙트 오탐 없음
정상 타깃은 어떤 후보도 불변식을 못 깨므로 **거짓 성공을 만들지 않고 기권**한다.

```bash
rm -rf out/d3 && mkdir -p out/d3
docker --context colima run --rm --network=none \
  -v "$PWD/$P/SafeVault:/work/target:ro" -v "$PWD/out/d3:/work/out" \
  autopoc \
  --contract /work/target/src/SafeVault.sol \
  --invariants /work/target/Invariants.sol \
  --manifest  /work/target/manifest.json \
  --out /work/out --timeout 300 --seed 42 --max-attempts 8
echo "exit=$?"                                  # 1 = 기권
cat out/d3/Exploit.sol                          # "// no candidate" (채택 후보 없음)
```
> 정상 타깃은 채택된 후보가 없어 `attempts.log`가 비고 `Exploit.sol`은 `// no candidate`다.
> `exit 1` + 후보 없음 자체가 **오탐 0**의 증거다.

### 마무리 컷 — 종료코드 규약
`0` 증명(PROVEN) · `1` 기권 · `2` 사용법/내부 오류. 취약 타깃은 실행된 PoC로 증명하고,
정상 타깃은 기권하며, 같은 입력은 바이트 동일하게 재현된다.

### 편집 메모
- 모든 실행이 1~5초라 컷 편집이 거의 필요 없다.
- 키는 준비 단계에서 파일로 주입하므로 화면에 노출되지 않는다.
- 채점자 재현용은 순정 `docker`(공개셋만으로 ①③과 결정론까지 재현 가능). ②의 포팅 타깃은
  로컬 보유분이므로, 재현 시에는 채점 측이 마운트하는 임의 타깃으로 대체하면 된다.

---

## 명령 레퍼런스 (상황별)

전체 복붙 명령은 위 녹화 스크립트에 있다. 상황별 핵심만 요약하면:

| 목적 | 핵심 실행 | 기대 결과 |
|---|---|---|
| 오프라인 증명 (키 없음) | `--network=none` + 취약 타깃 | `exit 0` · 결정론 두뇌가 PROVEN |
| 클라우드 일반화 | `-e ANTHROPIC_API_KEY` + 공개셋 외/미공개 타깃 | `exit 0` · `cloud-llm` PROVEN |
| 오탐 0 | `--network=none` + 정상 타깃(SafeVault) | `exit 1` · `Exploit.sol = // no candidate` |
| 생성 결정론 | 같은 입력·시드로 `--no-cache` N회 | `Exploit.sol` 해시 동일 |

도커 이미지에서 결정론을 한 번에 검증(오프라인 N=3 신규 생성 + 클라우드 캐시 리플레이):

```bash
bash agent/det_check.sh        # 각 타깃 "BYTE_IDENTICAL", 마지막 "DET_DONE"
```

---

## 종료코드 · 산출물 규약

| exit | 의미 | 산출물 |
|---|---|---|
| **0** | PROVEN (하네스 불변식 실제 파손) | `out/Exploit.sol` (무수정) + `out/attempts.log` |
| **1** | 예산 내 미발견 → 기권 | `out/attempts.log` (시도 이력; 후보가 없으면 빈 로그 + `Exploit.sol = // no candidate`) |
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
