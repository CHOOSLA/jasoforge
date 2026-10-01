<div align="center">

<img src="./assets/icon.png" alt="JasoForge Icon" width="120" />

# JasoForge
### Enterprise-Grade Engineering Narrative & Resume Verification Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+_(Zero_Dependency)-blue.svg?style=flat-square)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-3.5.0-cyan.svg?style=flat-square)](CHANGELOG.md)
[![Standard](https://img.shields.io/badge/standard-agentskills.io-purple.svg?style=flat-square)](SKILL.md)
[![Deterministic Lint](https://img.shields.io/badge/lint-deterministic_100%25-green.svg?style=flat-square)](scripts/lint.py)

<p align="center">
  <b>마케팅 미사여구 배제. AI 할루시네이션 0%. 결정론적 엔지니어링 팩트 검증.</b><br />
  선형 가중합의 착시와 LLM 온정주의를 차단하고, 시니어 테크 리드의 사법 루브릭과 Knockout Red Flag 게이트키퍼로 실전 합격 서사를 단련합니다.
</p>

[빠른 설치](#-빠른-설치) • [호환 런타임](#-호환-런타임-works-with) • [빠른 사용법](#-빠른-사용법-quick-start) • [왜 JasoForge인가?](#-왜-jasoforge인가) • [실전 실증 대조](#-실전-실증-대조-case-study) • [핵심 아키텍처](#-핵심-아키텍처) • [10대 루브릭](#-10대-루브릭-헌법) • [CLI 가이드](#-cli-명령어-레퍼런스)

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

## 🚀 빠른 사용법 (Quick Start)

### 1. 지원 입력 형태 (아래 중 하나만 넘기면 끝)

| 구분 | 입력 예시 | 자동 처리 내용 |
| :--- | :--- | :--- |
| **자소설닷컴** | `https://jasoseol.com/recruit/...` | 공고 요강 및 문항별 글자수 자동 크롤링 |
| **노션(Notion)** | 채용 공고 또는 지원서 아카이브 URL | Notion API 연동 자동 파싱 |
| **로컬 파일** | `draft.txt`, `spec.json` 등 경로 | 로컬 자립 모드로 즉시 분석 |
| **직접 텍스트** | 공고 요강 또는 자소서 초안 복사/붙여넣기 | 파일 생성 없이 대화창에 직접 입력 |

---

### 2. 실전 프롬프트 예시 (한 줄 복사해서 사용)

#### 🔍 자소서 정밀 검토 및 진단
```text
"이 자소서 검토해줘 [링크 / 파일경로 / 본문]"
```
> 기계 린트(`lint.py`) ➔ 10대 루브릭 2인 독립 블라인드 채점 ➔ Knockout 결함 판정 ➔ 면접 킬러 질문 리포트 즉시 출력.

#### ✍️ 공고 분석 및 초안 작성
```text
"이 공고 보고 내 경험 아카이브 기반으로 1번 문항 써줘 [공고 링크 또는 본문]"
```
> 공고 딥리서치 ➔ 직무 엣지케이스 도출 ➔ 필요한 사실 확인 ➔ 문항과 경험에 맞는 초안 작성.

---

### 💡 Pro Tip: 교차 평가 (Cross-Model Audit)

> **"더 정확하고 냉혹한 평가를 원하신다면, 초안을 작성한 AI와 다른 AI 모델로 채점을 진행해보세요."**
>
> JasoForge는 채점 시 이전 작성 대화 맥락을 완전히 차단하는 **컨텍스트 완전 격리(Context-Isolated)** 환경에서 채점을 수행합니다.  
> 하지만 동일한 AI 모델(예: Claude로 쓰고 Claude로 채점)을 사용할 경우, 모델 고유의 문체나 서사 구조에 대해 무의식적인 **글쓰기 스타일의 자기 편애적 부작용(Self-Favoritism / Style Bias)**이 발생할 수 있습니다.
> 
> ➔ **가장 객관적이고 정확한 점수**를 얻으려면 **작성 모델(예: Claude Code)**과 **검토/채점 모델(예: Gemini CLI / Antigravity 또는 OpenAI Codex)**을 교차하여 실행하는 것을 추천합니다.

---

## 💡 왜 JasoForge인가?

일반 LLM(ChatGPT, Claude 등)에게 자소서를 검토시키면 **"훌륭합니다! 95점입니다"**라며 칭찬 일색의 점수를 내놓습니다. 그러나 이 초안들은 실제 현업 서류 전형에서 탈락하기 십상입니다.

### 1. 단순 평균 점수의 함정
기존 AI 프롬프트는 모든 항목을 두루뭉술하게 평균 냅니다.  
그 결과 **비현실적인 과장(신입의 레거시 코어 계승 호언)**, **오탈자 방치**, **무관한 프로젝트 백화점식 나열** 같은 치명적인 탈락 사유가 있어도, 글자수를 채우고 기술 용어만 나열하면 **94점(합격권)**이라는 위험한 착시 점수를 내놓습니다.

### 2. 현실 채용은 '단 하나의 결함'으로 탈락합니다
실제 기업 평가는 평균 점수가 아니라 **"치명적인 결함 1개(Knockout Factor)"**로 서류를 거릅니다.  
JasoForge는 **Knockout Red Flag 게이트키퍼**를 통해 치명적 결함이 적발되는 즉시 총점을 Max 70~75점(불합격권)으로 강제 제한하여, 면접장에 가기도 전에 떨어질 위험을 사전에 완벽히 차단합니다.

---

## 📊 실전 실증 대조 (Case Study)

동일 지원자(컴퓨터공학 전공)의 실제 **국내 금융/증권 IT 기업** 서류 합격본과 탈락본을 JasoForge 엔진으로 정밀 블라인드 평가한 결과입니다:

| 평가 지표 | ❌ 실제 탈락본 (`c1e36478`) | ✅ 실제 합격본 (`8b4cd477`) |
| :--- | :--- | :--- |
| **소재 구성** | MFC, MobileNet, SSL Pinning, 캠핑카 등 6개 프로젝트 나열 | **단일 상용 외주 서비스 프로젝트** 멱등성/장애방어 집중 |
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
│ • 글자수/바이트 계량 (EUC-KR/UTF-8 바이트, 80% 하한선)        │
│ • 지시문 키워드 전수 충족도 검사 (0건 시 FAIL)              │
│ • 블라인드 금지어 검출 & 매크로성 고유명사 밀도             │
│ • 🚨 치명적 오탈자 3건 이상 누적 시 CRITICAL FAIL 즉시 차단 │
│ • 🚨 중간점(·) 나열식 방지 및 ATS 호환성 검사                │
│ • AI 번역투 대조구문(~이 아니라) 및 종결어미 60% 편중 경고 │
│ • 전 문항 마무리 상투 다짐(기여하겠습니다) 전역 반복 탐지   │
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
│   - 의미론적 증거 계약(Semantic Evidence Contract) 기반 검증 │
│   - 조직 정체성 이원화 계약(채용 모회사 ↔ 서비스 도메인)     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 🚨 Pass 3. Knockout Red Flag 사법 게이트키퍼 (Hard Clamp)   │
│ • 치명적 레드 플래그 유효 채택 건수 감사:               │
│   Flag 1. 자아과잉 / 비현실적 레거시 코어 전면 계승 장담    │
│   Flag 2. 서사 모순 & 오탈자 3건 이상 방치                  │
│   나열은 내용 평가에서 검토, 프로젝트 수로 결격 판정하지 않음  │
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
| **A** | **배경의 절제와 T·A 중심** | HR | S는 짧게, 과제·판단·행동은 충분히 설명하는가. T·A의 고민을 배경으로 오인하지 않음 |
| **B** | **판단과 근거** | Tech | 실제 선택이나 원인 설명이 확인된 상황·근거에 연결되는가 |
| **C** | **수행 범위와 결과** | Tech | 본인의 역할·행동·확인된 결과와 한계를 구별하는가 |
| **D** | **부서 엣지케이스 연결** | Tech | 지원 부서 1순위 핵심 과업 직격 여부 및 고유 핵심 불변식에 대한 현실적 온보딩 자세 |
| **E** | **문항 요구와 설명의 연결** | HR | 실제 질문에 답하며 전개를 따라갈 수 있는가 |
| **F** | **작성방법 지침 전수 충족** | HR | 행동, 결과, 보완 노력, 계기 등 공고의 필수 항목을 100% 충족했는가 |
| **G** | **글자수 규격 준수** | HR | 상한선 대비 90% 이상의 충실도 유지 (80~85%는 고밀도 압축 시 5점 구제, 80% 미만 하한선) |
| **H** | **고유성 (치환 불가성)** | Tech | 고유명사를 가려도 본인만의 팩트가 생생한가 ([CS Fundamental Safe Harbor] 보장) |
| **I** | **요구한 가치관·태도의 근거** | HR | 해당 문항이 요구하는 범위에서 행동 근거가 있는가 |
| **J** | **근거 무결성 & 팩트 일치** | Tech | 가짜 수치 날조 배제, 서사 모순 차단 (사소한 오탈자 1~2건은 교정 권고, 3건 이상 누적 시 결함) |

---

## 서술과 평가

경험 서술은 배경 S를 짧게 하고 과제 T와 판단·행동 A를 중심에 둡니다. 과도한 배경은 줄이되 T·A의 실제 의문과 선택 이유를 보존합니다. 문단 순서·문장 길이·감정의 강도는 고정하지 않으며, 대안·실패·저수준 조사·정량 성과가 없다는 이유만으로 소재를 제외하거나 점수를 제한하지 않습니다. 서사 유형을 선언할 필요가 없고 기존 type_declaration 자료도 점수 조건으로 사용하지 않습니다. 사실 확인, 실제 문항 요구, 인용 감사는 유지합니다.

---

## 🛠️ CLI 명령어 레퍼런스

JasoForge는 외부 의존성(Third-party pip package)이 전혀 없는 순수 파이썬 표준 라이브러리로 구동됩니다:

```bash
# 1. E2E 원클릭 파이프라인 실행 (기계 린트 + 2인 평가 프롬프트 패킷 자동 생성)
python3 scripts/run_pipeline.py draft.txt spec.json

# 2. 결정적 기계 린트 단독 실행 (글자수 80% 하한선, 중간점, AI 번역투, 오탈자 게이트)
python3 scripts/lint.py draft.txt spec.json

# 3. 2단계 검사-판사 독립 채점 및 리포트 집계 (Draft Hash Lock 검증)
python3 scripts/grade.py draft.txt hr_eval.json tech_eval.json \
  --spec spec.json \
  --knockout-threshold 75.0 \
  --out report.md

# 4. 무손실 회귀 불변식 100개 전수 검증
python3 scripts/verify_lossless.py

# 5. 스마트 라우팅 및 런타임 자동 배포
python3 installer.py --target auto
```

---

## 🤝 기여 및 라이선스 (License)

이 프로젝트는 **[MIT License](LICENSE)** 하에 배포됩니다.  
모든 개발자가 마케팅성 미사여구가 아닌, 진짜 엔지니어링 팩트와 시스템적 무결성으로 합격 서사를 증명할 수 있도록 지원합니다.
