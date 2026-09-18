# 🏢 노션 데이터베이스 연동 규격 및 스키마 (Notion Reference)

## 1. `🏢 회사별 지원 현황 DB` (`975d0820-971e-4335-ab6c-3aa08068b789`)
새 회사 지원 시 행을 생성하고 아래 속성을 필수로 기입함:
- `회사` (Title): 회사명
- `직무` (Text): 매칭된 지원 직무명
- `부서` (Text): 지원 부서 (공고에 명시된 경우)
- `상태` (Status): `준비중` (제출 완료 시 `제출`, 이후 `코테`/`면접` 등으로 전이)
- `지원일` (Date): **마감일자 필수 기입** (⚠️ 누락 시 보드/최신순 뷰에서 누락되거나 최하단으로 밀려남)
- `메모` (Text): 공고 URL, 마감 시각, 경쟁률, 직무 선정 사유 등
- `작성된지원서` (Relation): `📄 지원서 아카이브 DB`의 해당 지원서 페이지 연동

### 본문 필수 구성:
- 공고 개요 & 전형 일정 테이블
- 지원 전 확인사항 체크리스트 (블라인드 여부, 글자수 제한, 복수지원 불가, 어학 유효기간 등)
- 전 직무 비교 분석표 (업무, 자격요건, 우대사항, 기술스택)
- 직무 타당성 분석 (지원자 수 비교 및 1순위 선정 사유)

---

## 2. `📄 지원서 아카이브 DB` (`df7d2284-d7d4-4ed7-87c3-a002efca38c7`)
버전별 지원서를 관리하는 단일 원장 페이지:
- `지원서` (Title): `{회사명} {직무명} 지원서 (v{버전})`
- `지원서키` (Text): `YYYY-회사슬러그-직무슬러그` (동일 계열은 키를 공유)
- `버전` (Number): 1, 2, 3...
- `활성버전` (Checkbox): `TRUE` / `FALSE` (계열 내 1개만 `TRUE`)
- `🏢 지원 회사 (연동)` (Relation): `회사별 지원 현황` 행 연결
- `유형` (Select): `자기소개서`
- `작성일` (Date): 작성 일자
- `비고` (Text): 버전별 핵심 변경 요약

### 본문 구성:
- 문항 원장 (원문, 글자수, 분해된 항목)
- 장면 매칭 내역 표 (제약 조건, 버린 대안, 실제 선택, 관찰된 결과)
- 지원서 본문 텍스트
- lint 및 채점 결과표

---

## 3. `📝 ✍️ 지원서 변경 로그 DB` (`21a367de-0906-49f2-b93c-66aedc09a923`)
1회의 수정 세션(작업)이 완료될 때마다 반드시 1개 행을 생성:
- `지원서`: **이번 세션에서 실제로 수정한 지원서 아카이브 “활성 버전 페이지 URL” 1개만 연결** (필수)
- `변경(Title)`: `[커밋 타입] 요약` (예: `refactor: 뱅크웨어글로벌 자소서 v2 확정`)
- `작성자`: `gemini-cli` / `antigravity`
- `세션ID`: 해당 수정 세션 타임스탬프 (예: `20260917-1140`)
- `유형`: `feat`, `refactor`, `fix`, `cut`, `wip` 중 택 1
- `Scope`: `서론`, `지원동기`, `문항 1`, `문항 2`, `문항 3`, `전체` 중 택 1
- `What`: 무엇을 변경했는지 (1~2줄)
- `Why`: 왜 변경했는지 (1~2줄)
- `Before` / `After`: 대규모 수정일 경우 반드시 핵심 변경 문장이나 단락, 전문을 발췌하여 전/후 대조를 명확히 남길 것 (⚠️ 절대 누락 금지)

---

## 4. `🧪 context.json` 표준 스키마 및 4대 채용 아키타입 (`recruitment_archetype`)
채용 공고 및 부서 도메인 메타데이터를 저장하는 핵심 설정 규격:
- `company` (String): 지원 대상 기업명
- `department` (String): 지원 대상 부서 및 조직명
- `job_role` (String): 채용 직무명
- `deadline` (String): 지원 마감일자 (YYYY-MM-DD)
- `recruitment_archetype` (Enum): **4대 채용 아키타입 분기 기준**
  - `TECH_PURE`: 빅테크, SaaS, 순수 IT 서비스. CS Fundamental 및 학습 민첩성(Fast Learner) 우선. 스택 미경험 자백을 독해력/학습력으로 치환 시 방어 논리로 수용.
  - `MANUFACTURING_OPS`: 제조업 공장 IT, 온프레미스 설비 SM/SI. **즉시 전력감(Off-the-shelf Utility) 절대 우선**. 필수 코어 스택(C#, .NET, Java, DB/SQL 등) 미경험 자백 시 D축 치명적 감점(Max 2점 하드 캡핑). 시스템 엔지니어 공고에 웹 프론트엔드 조작 위장 시 D축 Max 3점 캡핑.
  - `FINTECH_CORE`: 금융, 증권 계정계/채널 IT. 원장 무결성, 트랜잭션 멱등성, 락 제어, 무중단/무장애, 금융 보안 우선.
  - `PUBLIC_SECTOR`: 공기업, 공공기관, 금융공기업. 블라인드 규격 무결성, 직업윤리, 지시문 전수 충족 우선.
- `required_hard_skills` (List[String]): 해당 직무의 타협 불가능한 필수 코어 스택 (예: `["C#", ".NET", "DB", "SQL"]`)
- `evaluation_priority` (Enum): `OFF_THE_SHELF_UTILITY` | `CS_FUNDAMENTAL` | `TRANSACTION_INTEGRITY` | `PROCEDURAL_COMPLIANCE`
- `domain_anti_patterns` (List[String]): 해당 직무에서 괴리감을 주는 부적합 서사/키워드 (예: 시스템 엔지니어 공고의 `["컴포넌트", "ref", "포커스", "블러", "DOM", "CSS"]`)
- `domain_core_invariants` (String): 지원 부서의 생명선인 핵심 도메인 불변식
- `layer1_company` / `layer2_department` / `layer3_job_edge_cases`: 3계층 기업 딥리서치 엣지케이스
