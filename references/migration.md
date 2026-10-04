# 구형 입력·평가·원장 이전

일반 사용자는 공고·문항·원고를 제공하면 된다. 아래 변환은 호스트 에이전트가 수행한다. 이전 자료를 현재 형식으로 조용히 덮어쓰지 않는다.

## spec과 context

1. 원고·구형 spec·context와 원장을 보존하고 새 버전 작업 사본을 만든다. `lint.py`는 기존 questions/min/max/basis/required_items 구조도 읽는다.
2. 기존 문항 ID·공식 분량·계수 방식·명시 금지사항을 유지한다. 과거 도구가 임의 생성한 최소 분량 등은 공고로 대조하고 정정 이유를 기록한다.
3. 각 문항의 `prompt`를 실제 공고/지원서 본문에서 확보한다. `required_items`의 키워드 목록으로 문항 원문을 추측하지 않는다.
4. 원문 요구와 주장을 읽고 `applicable_axes`, A/B/C/D/E/F/H/I 전부의 `axis_applicability_reasons`를 보완한다. 참고는 [평가 계약](evaluation.md)과 rubric JSON이다. 기술 평가를 피하거나 점수를 높이기 위해 축을 빼지 않는다. 문항·직무 필수 입력이 없으면 해당 축을 유보한다. 개인 경험 자료가 없는 것은 정상 사용이다.
5. 구형 spec에 있는 company/role/organization_contract/key_responsibilities 등은 출처와 함께 새 context의 company/job_role/조직·업무 필드로 연결한다. 원래 값과 출처를 보존하고 추정 순위를 확인된 우선순위로 승격하지 않는다. 전형은 실제 공고에서 확인한다.
6. 새 사본으로 린트→패킷→실제 독립 평가→집계→별도 원장 기록을 실행한다. `--out-json`은 자동 집계 결과를 저장한다.

## 평가 JSON과 입력 해시

구형 평가 JSON은 `--historical-import`로 미검증 기록을 확인할 수 있다. `killer_followup_questions` 등 기존 질문도 원본 파일에 보존하되 현재 TECH가 새로 검토한 질문으로 옮기지 않는다.

새 TECH 응답은 문항별 interview를 포함한다. 이전 실행은 코드 해시까지 묶여 있으므로 엔진 변경 후에는 현재 버전에서 그대로 유효하다고 집계할 수 없다. 원래 버전의 코드·입력·토큰을 보존하면 그 환경에서 열람하거나, 현재 버전으로 새 평가를 수행한다. 새 엔진용 해시·run_id를 옛 평가에 덧씌우지 않는다. `--allow-stale`은 우회 수단이 아니다.

## CLI와 원장

`--hr-weight`, `--tech-weight`, `--out`, `--run-id`, `--out-packets-dir`은 유지된다. 프리셋과 집계 JSON 출력이 추가됐다. `--knockout-eval`, `--knockout-threshold`의 키워드 결격·점수 상한은 폐기된 동작이므로 되살리지 않는다. 심각한 문제는 작성 revise 근거와 별도 근거 대조와 리포트의 확인/보완 사항으로 명시한다.

지원서키·버전·문항을 대응시키되 과거 점수를 현재 점수로 섞지 않는다. 알려지지 않은 구형 ledger는 복사 보존하고 현재 형식 원장을 별도 경로에 만든다. 새 기록은 실제 호출 증거와 입력을 포함한다. 기존 v4.1 원장 항목도 그대로 남기며 새 run만 추가한다. 레거시 기록을 지우거나 복구를 이유로 모든 지원서를 다시 작성하지 않는다.

## v4 → v5 평가 분리

새 spec 사본에서 G/J를 작성 applicable_axes와 이유 목록에서 제거하고 실제 규격을 spec_confirmation/spec_source에 보존한다. 경험 자료를 사용할 경우 원문을 fact_check.sources에, 주요 주장 연결을 claims에 옮긴다. 기존 experience_sources/evidence_sources만 둔 채 사실 대조를 했다고 보고하지 않는다. 자료가 없는 첫 사용은 fact_check를 생략한다.

새 토큰은 schema_version=3, evaluation_version=5.0이다. v4 평가 JSON의 G/J 점수를 빼거나 새 토큰 해시를 덧씌워 재평가로 재사용하지 않는다. 실제 독립 호출부터 다시 진행하고 기존 평가·원장은 보존한다.
