# 선택적 근거 대조와 첫 사용자

작성·평가 전에 가진 자료의 범위를 확인한다. 경험 원장이나 Notion은 필수가 아니다. 원고만 있으면 사용자 진술을 전제로 설명을 평가하고, 원문 내 모순·역할 모호함·과도한 인과 주장을 읽는다. 모든 주장에 증빙을 요구하지 않고 문항 답변에 필요한 사실만 질문한다. 질문 답변은 사용자 진술로 저장하며 문서·코드 검증과 구별한다.

자료를 제공한 경우 호스트가 원문을 읽고 주요 주장과 연결한다. 사용자가 JSON을 준비하는 흐름이 아니다. 현재 기록과 과거 제출본의 시점·범위 차이도 남긴다. 개인 경험 자료가 없는 경우와, 관련 자료가 있는데 호스트가 평가자에게 전달하지 못한 경우를 구별한다. 후자는 입력 보완 사항이며 원고 결함이 아니다.

## context.fact_check — 호스트가 생성

없으면 필드를 생략하거나 sources=[], claims={}로 둔다. URL만 있고 본문이 없으면 제공 자료로 등록하지 않는다. 공고·회사 조사 필드는 그대로 별도로 유지한다.

```json
{
  "fact_check": {
    "sources": [
      {"id":"interview-1", "kind":"user_statement", "text":"학생회 신청 안내를 두 쪽으로 줄였고 실제 배포까지 맡았다.", "locator":"사용자 답변·확인일"}
    ],
    "claims": {
      "1":[{"id":"claim-1", "quote":"신청 안내를 두 쪽으로 줄여 배포했습니다.", "availability":"provided", "source_ids":["interview-1"]}]
    }
  }
}
```

sources.kind는 user_statement(사용자 설명), record(제공 문서), code(제공 코드), public_source(공개 원문), draft_derived(자소서에서 복사·파생한 기록)다. 자기소개서를 다시 원장에 저장한 것으로 사실을 순환 증명하지 않는다. draft_derived만 있으면 일치·불일치를 확정할 수 없다. 사용자 설명과 일치한다는 판단은 외부 사실 검증 완료가 아니다.

claims는 문항별 주요 주장 배열이다. id는 문항 내 고유값, quote는 해당 문항의 정확한 연속 인용이다. availability=provided는 실제 sources의 id가 필요하다. not_provided(대조 자료 없음)와 input_missing(확보·전달 누락)은 source_ids=[]로 두며, 필요한 경우 reason에 누락 맥락을 남긴다. 대조할 자료가 없다면 주장 배열을 만드는 것도 필수는 아니다. 자료가 있으면 중대한 주장을 임의로 누락하지 않는다.

## TECH 출력 — 점수 없음

각 문항은 fact_review.findings를 가진다. 연결표가 없으면 빈 배열이다. 연결표가 있으면 모든 주장에 다음 항목을 남긴다.

```json
{"claim_id":"claim-1", "status":"CONSISTENT", "impact":"minor", "rationale":"사용자가 설명한 작성·배포 범위와 일치한다. 독립 문서 검증은 아니다.", "evidence":[{"source_id":"interview-1", "quote":"학생회 신청 안내를 두 쪽으로 줄였고 실제 배포까지 맡았다."}]}
```

- CONSISTENT: 제공 자료 범위에서 일치. CONFLICT: 실제 자료와 충돌. 둘 모두 자소서 파생 기록 외의 연결된 자료 인용이 필요하다. UNVERIFIED: 판단할 자료가 부족하거나 서로 다른 시점·범위를 확정하지 못함.
- impact=minor는 핵심 역할·판단·성과를 바꾸지 않는 국소 정정, material은 중심 주장에 영향을 주는 충돌·확인이다. 숫자라는 이유만으로 작다고 판단하지 않고 그 수치가 주장에 하는 역할을 읽는다.
- 없는 자료의 인용, 다른 주장에만 연결된 출처, 연결표의 검토 누락은 집계에서 거부한다. 인용 검사는 외부 자료의 진실성을 보증하지 않는다.

## 결과 표시

fact_review.coverage는 NOT_PROVIDED(대조 자료 없음), REVIEWED(제공 범위 대조), INPUT_INCOMPLETE(호스트 전달 누락)로 구분한다. 자료 없음은 첫 사용의 정상 상태이며 작성 점수를 낮추거나 일괄 보류하지 않는다. 개별 결과·자료 종류·사용자 진술 여부를 함께 표시한다.

규격은 compliance.status=MET/VIOLATION/UNVERIFIED로 별도 표시한다. spec.questions의 spec_confirmation은 CONFIRMED/PARTIAL/UNKNOWN이고 생략 시 UNKNOWN이다. CONFIRMED에는 spec_source가 필요하다. 이는 실제 확인한 규격의 출처이며 입력창 계수기를 매번 다시 열어야 한다는 요구가 아니다. 저장된 규격 통과와 출처 확인 상태는 구별한다.

핵심 사실 충돌은 MATERIAL_FACT_CONFLICT, 규격 위반은 COMPLIANCE_VIOLATION, 필수 평가 입력·자료 전달 누락은 INPUT_INCOMPLETE로 드러난다. 핵심 사실 충돌 시 작성 점수는 PROVISIONAL_FACT_CONFLICT로 해석을 제한한다. 점수에서 자동 차감하거나 합격 여부를 추정하지 않는다. 실제 역할·성과가 바뀌면 원고를 수정하고 새 입력으로 평가한다.
