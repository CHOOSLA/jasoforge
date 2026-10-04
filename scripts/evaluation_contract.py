"""Shared validation for review inputs. Verification is not hiring prediction."""
import hashlib
import json
import re
from pathlib import Path

EVALUATION_VERSION = "5.0"
ROLE_AXES = {"HR": set("AEFI"), "TECH": set("BCDH")}
ALL_AXES = set("ABCDEFHI")
WEIGHT_PROFILES = {"BALANCED": (0.4, 0.6), "TECH_DRIVEN": (0.3, 0.7), "HR_PUBLIC_DRIVEN": (0.6, 0.4)}


class ContractError(ValueError):
    pass


def resolve_weights(profile=None, hr=None, tech=None):
    import math
    if profile:
        if profile not in WEIGHT_PROFILES or hr is not None or tech is not None:
            raise ContractError("가중치 프리셋과 개별 가중치를 동시에 지정할 수 없습니다.")
        hr, tech = WEIGHT_PROFILES[profile]
    weights = {"HR": 0.4 if hr is None else hr, "TECH": 0.6 if tech is None else tech}
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in weights.values()):
        raise ContractError("평가자 가중치는 유한한 양수여야 합니다.")
    return weights


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_json(text, label="JSON"):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError(f"중복 JSON 키: {key} ({label})")
            result[key] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=unique_object)
    except ValueError as exc:
        raise ContractError(f"JSON을 읽을 수 없습니다: {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON 최상위는 객체여야 합니다: {label}")
    return value


def read_json(path):
    try:
        return parse_json(Path(path).read_text(encoding="utf-8"), str(path))
    except OSError as exc:
        raise ContractError(f"JSON을 읽을 수 없습니다: {path}: {exc}") from exc


def load_draft(path):
    text = Path(path).read_text(encoding="utf-8")
    parts = re.split(r"^===(\S+)===\s*$", text, flags=re.M)
    if len(parts) == 1 or parts[0].strip():
        raise ContractError("초안은 ===문항ID=== 구분자로 시작해야 합니다.")
    draft = {}
    for index in range(1, len(parts), 2):
        qid, body = parts[index], parts[index + 1].strip("\n")
        if qid in draft:
            raise ContractError(f"중복 문항 ID: {qid}")
        if not body.strip():
            raise ContractError(f"빈 문항: {qid}")
        draft[qid] = body
    return draft


def validate_spec(spec, draft, require_axes=False):
    questions = spec.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise ContractError("spec.questions에 문항별 규격이 필요합니다.")
    if set(questions) != set(draft):
        raise ContractError(f"문항 ID 불일치: spec={sorted(questions)}, draft={sorted(draft)}")
    for field in ("banned", "proper_nouns"):
        values = spec.get(field, [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ContractError(f"spec.{field}는 문자열 배열이어야 합니다.")
    for pattern in spec.get("banned", []):
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ContractError(f"유효하지 않은 금지 표현 정규식: {pattern}") from exc
    for qid, question in questions.items():
        if not isinstance(question, dict):
            raise ContractError(f"문항 {qid} 규격은 객체여야 합니다.")
        items = question.get("required_items", {})
        if not isinstance(items, dict) or any(not isinstance(words, list) or any(not isinstance(word, str) for word in words) for words in items.values()):
            raise ContractError(f"문항 {qid}.required_items는 항목별 문자열 배열이어야 합니다.")
        for key in ("min", "max"):
            value = question.get(key)
            if value is not None and (type(value) is not int or value < 0):
                raise ContractError(f"문항 {qid}.{key}는 0 이상 정수여야 합니다.")
        if question.get("max") is not None and (question.get("min") or 0) > question["max"]:
            raise ContractError(f"문항 {qid}: min이 max보다 큽니다.")
        metric = question.get("length_metric_type", spec.get("length_metric_type", question.get("basis", "chars_with_space")))
        if metric not in ("chars_with_space", "chars_without_space", "with_spaces", "without_spaces", "bytes_euckr", "bytes_utf8", "legacy_nonascii_2byte"):
            raise ContractError(f"문항 {qid}: 지원하지 않는 계량 방식 {metric!r}")
        if question.get("spec_confirmation", "UNKNOWN") not in ("CONFIRMED", "PARTIAL", "UNKNOWN"):
            raise ContractError(f"문항 {qid}: spec_confirmation은 CONFIRMED/PARTIAL/UNKNOWN입니다.")
        if question.get("spec_confirmation") == "CONFIRMED" and (not isinstance(question.get("spec_source"), str) or not question["spec_source"].strip()):
            raise ContractError("확인된 규격에는 출처 설명이 필요합니다.")
        if require_axes:
            axes = question.get("applicable_axes")
            if not isinstance(axes, list) or not axes or any(not isinstance(a, str) or a not in ALL_AXES for a in axes) or len(set(axes)) != len(axes):
                raise ContractError(f"문항 {qid}.applicable_axes에 실제 문항에 적용할 작성 8개 축을 중복 없이 명시하십시오. 구형 입력은 references/migration.md에 따라 원본을 보존하고 호스트가 보완합니다.")
            reasons = question.get("axis_applicability_reasons")
            if not isinstance(reasons, dict) or any(not isinstance(reasons.get(a), str) or not reasons[a].strip() for a in ALL_AXES):
                raise ContractError(f"문항 {qid}.axis_applicability_reasons에 작성 8개 각 축의 적용/제외 이유가 필요합니다.")
            if question.get("prompt") is not None and not isinstance(question["prompt"], str):
                raise ContractError(f"문항 {qid}.prompt는 원문 문자열 또는 미제공(null)이어야 합니다.")


def verify_quote(quote, body):
    """Whitespace-only normalization. No token similarity or meaning inference."""
    return isinstance(quote, str) and bool(quote.strip()) and re.sub(r"\s+", " ", quote.strip()) in re.sub(r"\s+", " ", body)


def verify_manifest(token_path, draft_path, spec_path, context_path, root):
    token = read_json(token_path)
    if token.get("schema_version") != 3 or token.get("evaluation_version") != EVALUATION_VERSION or not isinstance(token.get("run_id"), str) or not token["run_id"]:
        raise ContractError("현재 검토에 필요한 v3 세션 토큰이 없습니다. 과거 기록은 --historical-import로 별도 열람하십시오.")
    inputs = token.get("inputs")
    if not isinstance(inputs, dict):
        raise ContractError("세션 입력 manifest가 없습니다.")
    expected = {
        "draft": Path(draft_path), "spec": Path(spec_path),
        "rubric_hr": Path(root) / "references/rubric_hr.json",
        "rubric_tech": Path(root) / "references/rubric_tech.json",
        "question_flows": Path(root) / "references/question-flows.md",
        "lint_engine": Path(root) / "scripts/lint.py",
        "review_engine": Path(root) / "scripts/grade.py",
        "contract_engine": Path(root) / "scripts/evaluation_contract.py",
        "packet_engine": Path(root) / "scripts/run_pipeline.py",
    }
    if context_path:
        expected["context"] = Path(context_path)
    elif "context" in inputs:
        raise ContractError("평가 당시 context.json이 현재 입력에서 누락되었습니다.")
    required = set(expected) | {"lint_report", "hr_packet", "tech_packet"}
    if set(inputs) != required:
        raise ContractError("세션 입력 목록이 현재 실행과 일치하지 않습니다.")
    for name in required:
        entry = inputs[name]
        if not isinstance(entry, dict) or not entry.get("path") or not entry.get("sha256"):
            raise ContractError(f"입력 해시 누락: {name}")
        path = expected.get(name, Path(entry["path"]))
        if not path.is_file() or file_hash(path) != entry["sha256"]:
            raise ContractError(f"평가 입력 변경 또는 유실: {name}")
    return token


def validate_evaluation(data, role, draft, spec, token, context=None):
    fact_input = validate_fact_input(context or {}, draft)
    if data.get("evaluator") != role:
        raise ContractError(f"평가자 역할 불일치: {role}")
    for key, expected in (("run_id", token["run_id"]), ("draft_hash", token["inputs"]["draft"]["sha256"]), ("packet_hash", token["inputs"][f"{role.lower()}_packet"]["sha256"])):
        if data.get(key) != expected:
            raise ContractError(f"{role} 평가의 {key}가 현재 실행과 일치하지 않습니다.")
    questions = data.get("questions")
    if not isinstance(questions, dict) or set(questions) != set(draft):
        raise ContractError(f"{role} 평가 문항 ID가 초안/규격과 일치하지 않습니다.")
    for qid, review in questions.items():
        if not isinstance(review, dict):
            raise ContractError(f"{role} 문항 {qid}는 객체여야 합니다.")
        scores, evidence = review.get("scores"), review.get("axis_evidence")
        if not isinstance(scores, dict) or set(scores) != ROLE_AXES[role] or not isinstance(evidence, dict) or set(evidence) != ROLE_AXES[role]:
            raise ContractError(f"{role} 문항 {qid}: 담당 축 전체의 scores와 axis_evidence가 필요합니다.")
        applicable = set(spec["questions"][qid]["applicable_axes"])
        for axis in ROLE_AXES[role]:
            score, item = scores[axis], evidence[axis]
            if not isinstance(item, dict):
                raise ContractError(f"{qid}/{axis}: axis_evidence는 객체여야 합니다.")
            if axis not in applicable:
                if score is not None or item.get("status") != "NOT_APPLICABLE" or not isinstance(item.get("reason"), str) or not item["reason"].strip():
                    raise ContractError(f"{qid}/{axis}: 제외 축은 null 점수와 NOT_APPLICABLE, 이유가 필요합니다.")
                continue
            if axis in {"E", "F"} and not (spec["questions"][qid].get("prompt") or "").strip() and item.get("status") != "DEFERRED":
                raise ContractError(f"{qid}/{axis}: 문항 원문이 없어 문항 충족 축은 유보해야 합니다.")
            if item.get("status") == "DEFERRED":
                if score is not None or item.get("missing_input") not in ("prompt", "job_description", "required_instruction") or not isinstance(item.get("reason"), str) or not item["reason"].strip():
                    raise ContractError(f"{qid}/{axis}: 평가 유보는 null, 필요한 문항/직무 입력과 이유가 필요합니다.")
                continue
            if type(score) is not int or score not in range(1, 6) or item.get("status") != "ASSESSED":
                raise ContractError(f"{qid}/{axis}: 적용 축은 ASSESSED와 정수 1~5가 필요합니다.")
            if not isinstance(item.get("rationale"), str) or not item["rationale"].strip():
                raise ContractError(f"{qid}/{axis}: 긍정 판단 또는 개선 판단의 근거가 필요합니다.")
            if not isinstance(item.get("severity"), str) or item["severity"] not in {"none", "revise"}:
                raise ContractError(f"{qid}/{axis}: 작성 severity는 none/revise 중 하나여야 합니다.")
            if score <= 3 and item["severity"] == "none":
                raise ContractError(f"{qid}/{axis}: 낮은 점수와 수정 필요 없음 판정이 충돌합니다.")
            quotes = item.get("quotes")
            if not isinstance(quotes, list) or not quotes or any(not verify_quote(q, draft[qid]) for q in quotes):
                raise ContractError(f"{qid}/{axis}: 해당 문항의 정확한 인용이 없거나 일치하지 않습니다. 점수 복원 없이 재평가가 필요합니다.")
        if role == "TECH":
            validate_fact_review(review.get("fact_review"), qid, fact_input)
            interview = review.get("interview")
            if token.get("technical_followups_required") or interview is not None:
                validate_interview(interview, qid, draft[qid])
    return data


def validate_interview(interview, qid, body):
    if not isinstance(interview, dict) or not isinstance(interview.get("questions"), list):
        raise ContractError(f"TECH 문항 {qid}: 독립 면접 질문 또는 생략 이유가 필요합니다.")
    questions = interview["questions"]
    reason = interview.get("omission_reason", "")
    if not isinstance(reason, str) or (not questions and not reason.strip()):
        raise ContractError(f"TECH 문항 {qid}: 질문이 없으면 omission_reason을 남기십시오.")
    for item in questions:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip()
                for k in ("question", "intent", "anchor_quote", "answer_scope")):
            raise ContractError(f"TECH 문항 {qid}: 질문·의도·원문 인용·답변 범위가 필요합니다.")
        if item.get("topic") not in ("technical", "organization"):
            raise ContractError(f"TECH 문항 {qid}: topic은 technical/organization이어야 합니다.")
        if not verify_quote(item["anchor_quote"], body):
            raise ContractError(f"TECH 문항 {qid}: 면접 질문의 인용이 원고와 일치하지 않습니다.")
        facts = item.get("facts_to_confirm")
        if not isinstance(facts, list) or any(not isinstance(v, str) or not v.strip() for v in facts):
            raise ContractError(f"TECH 문항 {qid}: facts_to_confirm은 확인할 사실의 문자열 배열이어야 합니다.")


def validate_fact_input(context, draft):
    """Optional sources; a first-time applicant needs no evidence archive."""
    data = context.get("fact_check", {"sources": [], "claims": {}})
    if any(context.get(k) for k in ("experience_sources", "evidence_sources")):
        raise ContractError("제공한 경험 자료는 fact_check.sources와 claims로 연결하십시오. 원문 없이 URL만으로 대조 완료 처리하지 않습니다.")
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list) or not isinstance(data.get("claims"), dict):
        raise ContractError("fact_check에는 sources 배열과 claims 객체가 필요합니다. 자료가 없으면 생략할 수 있습니다.")
    sources = {}
    for source in data["sources"]:
        if not isinstance(source, dict) or any(not isinstance(source.get(k), str) or not source[k].strip() for k in ("id", "text")):
            raise ContractError("대조 자료에는 고유 id와 실제 text가 필요합니다.")
        if source["id"] in sources or source.get("kind") not in ("user_statement", "record", "code", "public_source", "draft_derived"):
            raise ContractError("중복 자료 id 또는 지원하지 않는 자료 종류입니다.")
        sources[source["id"]] = source
    if set(data["claims"]) - set(draft):
        raise ContractError("근거 연결표의 문항 ID가 원고와 다릅니다.")
    claims = {}
    for qid in draft:
        items = data["claims"].get(qid, [])
        if not isinstance(items, list):
            raise ContractError("문항별 근거 연결표는 배열이어야 합니다.")
        claims[qid] = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip() or item["id"] in claims[qid]:
                raise ContractError("주장에는 문항 내 고유 id가 필요합니다.")
            if not verify_quote(item.get("quote"), draft[qid]):
                raise ContractError("연결표의 주장은 해당 문항의 실제 연속 인용이어야 합니다.")
            refs = item.get("source_ids")
            if not isinstance(refs, list) or any(not isinstance(v, str) or v not in sources for v in refs) or len(refs) != len(set(refs)):
                raise ContractError("연결표에 없는 자료 id가 있거나 중복되었습니다.")
            availability = item.get("availability")
            if availability not in ("provided", "not_provided", "input_missing") or (availability == "provided") != bool(refs):
                raise ContractError("provided는 실제 자료 id가 필요하며 미제공/전달 누락에는 자료 id를 넣지 않습니다.")
            claims[qid][item["id"]] = item
    if sources and not any(claims.values()):
        raise ContractError("자료를 제공했다면 원고의 주요 주장과 연결하십시오.")
    return {"sources": sources, "claims": claims}


def validate_fact_review(review, qid, fact_input):
    if not isinstance(review, dict) or not isinstance(review.get("findings"), list):
        raise ContractError(f"TECH 문항 {qid}: fact_review.findings가 필요합니다. 대조 자료가 없으면 빈 배열입니다.")
    expected = fact_input["claims"][qid]
    found = set()
    for finding in review["findings"]:
        if not isinstance(finding, dict) or not isinstance(finding.get("claim_id"), str) or finding.get("claim_id") not in expected or finding["claim_id"] in found:
            raise ContractError("근거 대조는 연결표의 주장 ID를 중복 없이 사용해야 합니다.")
        found.add(finding["claim_id"])
        claim = expected[finding["claim_id"]]
        if finding.get("status") not in ("CONSISTENT", "UNVERIFIED", "CONFLICT") or finding.get("impact") not in ("minor", "material") or not isinstance(finding.get("rationale"), str) or not finding["rationale"].strip():
            raise ContractError("근거 대조의 상태·영향·판단 이유가 필요합니다.")
        refs = finding.get("evidence")
        if not isinstance(refs, list):
            raise ContractError("근거 대조 evidence는 자료 인용 배열이어야 합니다.")
        substantive = False
        for ref in refs:
            if not isinstance(ref, dict) or ref.get("source_id") not in claim["source_ids"]:
                raise ContractError("연결되지 않은 자료를 근거로 사용할 수 없습니다.")
            source = fact_input["sources"][ref["source_id"]]
            if not verify_quote(ref.get("quote"), source["text"]):
                raise ContractError("근거 자료의 인용이 제공 원문과 일치하지 않습니다.")
            substantive |= source["kind"] != "draft_derived"
        if finding["status"] != "UNVERIFIED" and not substantive:
            raise ContractError("자소서 파생 기록 또는 미제공 자료만으로 일치·충돌을 확정할 수 없습니다.")
        if claim["availability"] != "provided" and finding["status"] != "UNVERIFIED":
            raise ContractError("자료 미제공/전달 누락은 일치나 모순으로 판정할 수 없습니다.")
    if found != set(expected):
        raise ContractError("근거 연결표의 모든 주장을 대조하거나 미확인으로 남겨야 합니다.")


def compliance_review(draft, spec):
    import lint
    result = {}
    for qid, body in draft.items():
        question = dict(spec["questions"][qid])
        if "length_metric_type" not in question and "length_metric_type" in spec:
            question["length_metric_type"] = spec["length_metric_type"]
        raw = lint.check(qid, body, question, spec.get("banned", []), spec.get("proper_nouns", []), blind_level=spec.get("blind_compliance_level", "NONE"))
        failures = [v for v in raw["issues"] if v.startswith("FAIL")]
        confirmation = question.get("spec_confirmation", "UNKNOWN")
        result[qid] = {"status": "VIOLATION" if failures else "MET" if confirmation == "CONFIRMED" else "UNVERIFIED",
                       "declared_limits_met": not failures, "spec_confirmation": confirmation,
                       "source": question.get("spec_source", "출처 미지정"), "measurements": raw["info"], "issues": raw["issues"]}
    return result
