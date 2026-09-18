<div align="center">

<img src="./assets/icon.png" alt="JasoForge Icon" width="120" />

# JasoForge
### Enterprise-Grade Engineering Narrative & Resume Verification Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+_(Zero_Dependency)-blue.svg?style=flat-square)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-3.4.0-cyan.svg?style=flat-square)](CHANGELOG.md)
[![Standard](https://img.shields.io/badge/standard-agentskills.io-purple.svg?style=flat-square)](SKILL.md)
[![Deterministic Lint](https://img.shields.io/badge/lint-deterministic_100%25-green.svg?style=flat-square)](scripts/lint.py)

<p align="center">
  <b>마케팅 미사여구 배제. AI 할루시네이션 0%. 결정론적 엔지니어링 팩트 검증.</b><br />
  선형 가중합의 착시와 LLM 온정주의를 차단하고, 시니어 테크 리드의 사법 루브릭과 Knockout Red Flag 게이트키퍼로 실전 합격 서사를 단련합니다.
</p>

[빠른 설치](#-빠른-설치) • [호환 런타임](#-호환-런타임-works-with) • [왜 JasoForge인가?](#-왜-jasoforge인가) • [실전 실증 대조](#-실전-실증-대조-case-study) • [핵심 아키텍처](#-핵심-아키텍처) • [10대 루브릭](#-10대-루브릭-헌법) • [CLI 가이드](#-cli-명령어-레퍼런스)

</div>

---

## ⚡ 빠른 설치

JasoForge는 표준 [agentskills.io](https://agentskills.io) 규격을 준수하며, 시스템에 설치된 AI 코딩 에이전트 런타임을 자동 감지하여 배포합니다.

### skills.sh 패키지 매니저
```bash
npx skills add choosla/jasoforge
```

### macOS & Linux (원클릭)
```bash
curl -fsSL https://raw.githubusercontent.com/choosla/jasoforge/main/install.sh | bash
```

### Windows (PowerShell 5.1+ / 7+)
```powershell
irm https://raw.githubusercontent.com/choosla/jasoforge/main/install.ps1 | iex
```

### Python 무의존성 설치 (Standard Library Only)
```bash
git clone https://github.com/choosla/jasoforge.git
cd jasoforge
python3 installer.py
```

---

## 🖥️ 호환 런타임 (Works with)

JasoForge는 단일 소스 트리로 주요 AI 코딩 에이전트 환경에 네이티브 동기화됩니다:

| 런타임 환경 | 배포 경로 | 활성화 방식 |
| :--- | :--- | :--- |
| **Claude Code** | `~/.claude/skills/jaso-pipeline` | 자동 로드 또는 `/jaso-pipeline` |
| **Gemini CLI / Antigravity** | `~/.gemini/config/skills/jaso-pipeline` | 자동 로드 또는 `/jaso-pipeline` |
| **Universal Agents** | `~/.agents/skills/jaso-pipeline` | 글로벌 표준 스킬 자동 인식 |
| **OpenAI Codex** | `~/.codex/skills/jaso-pipeline` | `SKILL.md` 표준 계약 호환 |

---

## 💡 왜 JasoForge인가?

일반 LLM(ChatGPT, Claude 등)에게 자소서를 검토시키면 **"훌륭합니다! 95점입니다"**라며 칭찬 일색의 점수를 내놓습니다. 그러나 이 초안들은 실제 현업 테크 리드의 서류 전형에서 100% 탈락합니다.

### 1. 선형 가중합의 함정 (The Linear Averaging Trap)
기존 채점 프롬프트는 10개 축 점수를 단순 가중 평균(`HR 40% + Tech 60%`)합니다.  
그 결과, **신입이 40년 레거시 코어 계승을 장담하는 오만함(Flag 1)**, **도구주의를 주장하면서 오탈자 5건을 방치한 서사 모순(Flag 2)**, **6개 프로젝트를 나열한 조각모음(Flag 3)**이 있어도, 글자수 채우기나 학술 스펙 키워드 덕분에 **94.0점(합격권 착시)**이 찍히는 치명적인 결함이 발생합니다.

### 2. 현실 채용은 '관문 탈락(Knockout)'입니다
실제 기업 채용 평가는 합산 점수가 아니라 **"단 1개의 치명적 결함(Knockout Factor)"**으로 탈락시키는 구조입니다.  
JasoForge는 **Knockout Red Flag 사법 게이트키퍼**를 도입하여, 치명적 결함 적발 시 선형 가중합을 즉시 무효화하고 총점을 Max 70~75점(DEFECT)으로 강제 캡핑(Hard Clamp)합니다.

---

## 📊 실전 실증 대조 (Case Study)

동일 지원자(컴퓨터공학 전공)의 실제 **다우기술(금융/증권 IT 개발)** 서류 합격본과 탈락본을 JasoForge v3.2 엔진으로 정밀 블라인드 심리한 결과입니다:

| 평가 지표 | ❌ 실제 탈락본 (`c1e36478`) | ✅ 실제 합격본 (`8b4cd477`) |
| :--- | :--- | :--- |
| **소재 구성** | MFC, MobileNet, SSL Pinning, 캠핑카 등 6개 프로젝트 나열 | **Ditda 디자인 외주 서비스 단일 프로젝트** 멱등성/장애방어 집중 |
| **온보딩 태도** | "40년간 축적된 코드를 안정적으로 계승" (비현실적 호언) | "화면 하나를 골라 데이터 유입 흐름을 도식화" (현실적 기여) |
| **무결성/오탈자** | '곳', '끕어올려', '가늘할', '옷기던', '옷겨본' (5건 방치) | 오탈자 0건, 비문 0건, 완벽한 서류 무결성 |
| **기존 선형 점수** | **94.0점 (A+ 통과권 - 착시 발생)** | **99.4점 (PASS - 합격권)** |
| **🚨 Knockout 심리** | **3대 레드 플래그 전원 유효 채택 (3 SUSTAINED)** | **3대 레드 플래그 전건 기각 (ALL CLEAR)** |
| **v3.2 사법 판결** | **70.0점 (DEFECT / 불합격권 선고)** *(Hard Clamped)* | **99.4점 (PASS / 최상위 1% 실전 합격권)** |
| **점수 변별력** | **기존 5.4점 차이 ➔ 29.4점 격차로 실제 합/불 결과 완벽 재현** |

---

## 🏛️ 핵심 아키텍처

```
[입력 패킷: draft.txt + spec.json + context.json]
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Pass 1. 결정적 기계 린트 (scripts/lint.py)                    │
│ • 글자수/바이트 계량 (상한 대비 80% 하드 하한선)               │
│ • 지시문 키워드 충족도 (0건 시 FAIL)                        │
│ • 블라인드 금지어 검출 & 매크로 고유명사 밀도               │
│ • 🚨 치명적 오탈자 3건 이상 누적 시 CRITICAL FAIL 즉시 차단 │
└──────────────────────────────┬──────────────────────────────┘
                               │ PASS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Pass 2. 2단계 검사-판사 사법 심리 (Prosecutor-Judge Eval)   │
│ • Phase 1 (기소): 점수 권한 박탈 2대 레드팀 검사             │
│   - HR 검사 (40%): A, E, F, G, I 지시문 이탈 기소           │
│   - Tech 검사 (60%): B, C, D, H, J 기술허점/3단계 So What 추궁│
│ • Phase 2 (판결): 판사 엔진 (Word Bi-gram Fuzzy Jaccard)     │
│   - 환각 기소 즉시 기각 vs 실질 결함 채택                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 🚨 Pass 3. Knockout Red Flag 사법 게이트키퍼 (Hard Clamp)   │
│ • 3대 치명적 레드 플래그 유효 채택 건수 감사:               │
│   Flag 1. 자아과잉 / 비현실적 레거시 코어 전면 계승 장담    │
│   Flag 2. 서사 모순 & 오탈자 3건 이상 방치                  │
│   Flag 3. 무관한 프로젝트 조각모음 나열 (Type_C 독소 저촉)  │
│                                                             │
│   ➔ [결함 적발 시 (탈락본)]: 선형 합산 전면 무효화 &        │
│      총점 Max 70~75.0점 강제 캡핑 ➔ DEFECT (불합격권)       │
│   ➔ [0건 무결점 (합격본)]: HR 40% + Tech 60% 정상 선형 랭킹│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Pass 4. 회귀 방지 점수 원장 (score_ledger.json)             │
│ • (지원서, 버전, 문항, 축) 단위 영구 보존                   │
│ • v1 대비 v2 점수 하락(퇴행) 감지 및 진동 방지 국소 수정     │
└─────────────────────────────────────────────────────────────┘
```

---

## 📜 10대 루브릭 헌법

모든 지원서는 10개 공통 평가 축(축당 10점, 총 100점 만점)을 기준으로 평가됩니다:

| 축 | 평가 항목 | 가중치 | 핵심 심리 기준 |
| :---: | :--- | :---: | :--- |
| **A** | **상황 설명 비중 $\le 30\%$** | HR | 배경 설명은 1~2문장으로 압축. 지면의 70% 이상을 행동과 판단에 몰입했는가 |
| **B** | **판단 근거 & Why 의식** | Tech | 단순 라이브러리 사용을 넘어, 왜 그 방식을 택했고 무엇을 버렸는지(트레이드오프) 입증 |
| **C** | **완수 과정 & 리스크 책임** | Tech | 상용 프로덕션 실전성 또는 신입 엔지니어링 5대 완수 앵커(배포, OOM 극복, 부하 테스트 등) 실증 |
| **D** | **부서 엣지케이스 연결** | Tech | 지원 부서의 고유 핵심 불변식을 관통하며, 신입으로서 현실적 온보딩 자세를 갖추었는가 |
| **E** | **질문 본질 의도 & 플로우** | HR | 지시문의 두괄식 질문 순서와 인과관계에 정확히 호응하는가 |
| **F** | **작성방법 지침 전수 충족** | HR | 행동, 결과, 보완 노력, 계기 등 공고의 필수 항목을 100% 충족했는가 |
| **G** | **글자수 규격 준수** | HR | 상한선 대비 90% 이상의 충실도 유지 (80~85%는 고밀도 압축 시 5점 구제) |
| **H** | **고유성 (치환 불가성)** | Tech | 고유명사를 가려도 본인만의 팩트가 생생한가 ([CS Fundamental Safe Harbor] 보장) |
| **I** | **행동화된 가치관 지속성** | HR | 단순 반성문이 아닌 업무 규칙(시스템적 강제)으로 체화되어 입사 후에도 지속되는가 |
| **J** | **근거 무결성 & 팩트 일치** | Tech | 가짜 수치 날조 배제, 서사 모순 및 치명적 오탈자 배제 |

---

## 📐 5대 직교 서사 유형 (Orthogonal Narrative Matrix)

기술 프로젝트 문항(B축)은 사전에 선언된 단 하나의 서사 유형만을 기준으로 잠금 루브릭(Locked Rubric)을 적용합니다:

* **Type A (기술적 의사결정 / 트레이드오프형)**: 버린 대안 1건 필수 명시 및 수치적/공학적 비교.
* **Type B (밑바닥 심층 디버깅 / Grit형)**: OS, 네이티브 핸들, 바이트코드 레벨의 근본 원인 규명 및 PR/패치 완수.
* **Type C (풀스택 시스템 조망형)**: 단일 서비스 내 클라이언트-백엔드-인프라 간 데이터 결속. *(무관한 프로젝트 조각모음 엄격 금지)*
* **Type D (알고리즘 및 복잡도 최적화형)**: 시간/공간 복잡도 개선($O(N^2) \rightarrow O(N \log N)$) 및 벤치마크.
* **Type E (데이터 및 인프라 파이프라인형)**: 비동기 분산 처리, I/O 병목 제거, 스루풋(TPS/QPS) 지연 최소화.

---

## 🛠️ CLI 명령어 레퍼런스

JasoForge는 외부 의존성(Third-party pip package)이 전혀 없는 순수 파이썬 표준 라이브러리로 구동됩니다:

```bash
# 1. 결정적 기계 린트 실행 (글자수, 지시문, 오탈자 게이트)
python3 scripts/lint.py draft.txt spec.json

# 2. 2단계 검사-판사 사법 채점 및 리포트 생성
python3 scripts/grade.py draft.txt hr_eval.json tech_eval.json \
  --spec spec.json \
  --knockout-threshold 75.0 \
  --out report.md

# 3. 무손실 회귀 불변식 76개 전수 검증
python3 scripts/verify_lossless.py

# 4. 스마트 라우팅 및 런타임 자동 배포
python3 installer.py --target auto
```

---

## 🤝 기여 및 라이선스 (License)

이 프로젝트는 **[MIT License](LICENSE)** 하에 배포됩니다.  
모든 개발자가 마케팅성 미사여구가 아닌, 진짜 엔지니어링 팩트와 시스템적 무결성으로 합격 서사를 증명할 수 있도록 지원합니다.
