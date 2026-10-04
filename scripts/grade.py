#!/usr/bin/env python3
"""Validate independent reviews and report an uncalibrated internal rubric index."""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from evaluation_contract import (
    ContractError, ROLE_AXES, EVALUATION_VERSION, validate_fact_input, compliance_review, load_draft, read_json, validate_spec,
    validate_evaluation, verify_manifest, verify_quote, WEIGHT_PROFILES, resolve_weights,
)

ROOT = Path(__file__).resolve().parent.parent


def verify_quote_fuzzy(quote, full_text, threshold=None):
    """Legacy function name; matching is exact except for whitespace."""
    return verify_quote(quote, full_text)


def verify_quotes(quotes, full_text):
    return [{"quote": q, "valid": verify_quote(q, full_text)} for q in quotes]


def audit_type_rubric_gating(*args, **kwargs):
    return "서사 유형은 점수 조건이 아닙니다."


def audit_axis_c_gating(*args, **kwargs):
    return None


def audit_knockout_gatekeeper(*args, **kwargs):
    """Retired compatibility hook. Keywords never establish hiring outcomes."""
    return [], [{"key": "LEGACY_KNOCKOUT_RETIRED", "reason": "키워드 기반 채용 결격 판정은 폐기되었습니다."}]


def resolve_token(hr_path, tech_path, explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise ContractError("지정한 session_token.json이 없습니다.")
        return path
    candidates = {p.resolve() for p in (
        Path(hr_path).parent / "session_token.json",
        Path(hr_path).parent.parent / "session_token.json",
        Path(tech_path).parent / "session_token.json",
        Path(tech_path).parent.parent / "session_token.json",
    ) if p.is_file()}
    if len(candidates) != 1:
        raise ContractError("현재 검토의 --session-token을 지정하십시오. 토큰 없음/모호함은 평가 완료로 처리하지 않습니다.")
    return candidates.pop()


def summarize_review(draft, spec, reviews, weights, context=None):
    """Writing scores, compliance and optional source comparison stay separate."""
    fact_input = validate_fact_input(context or {}, draft)
    compliance = compliance_review(draft, spec)
    questions, all_issues, attention = {}, [], []
    for qid in draft:
        applicable = set(spec["questions"][qid]["applicable_axes"])
        role_indices, issues, deferred = {}, [], []
        for role in ("HR", "TECH"):
            review = reviews[role]["questions"][qid]
            axes = ROLE_AXES[role] & applicable
            pending = [axis for axis in sorted(axes) if review["axis_evidence"][axis]["status"] == "DEFERRED"]
            deferred.extend({"axis": axis, "role": role, **review["axis_evidence"][axis]} for axis in pending)
            role_indices[role] = sum(review["scores"][axis] for axis in axes) / (5 * len(axes)) * 100 if axes and not pending else None
            for axis in sorted(axes - set(pending)):
                item = review["axis_evidence"][axis]
                if item["severity"] != "none":
                    issues.append({"question_id": qid, "role": role, "axis": axis, **item})
        active = [role for role, value in role_indices.items() if value is not None]
        index = sum(role_indices[r] * weights[r] for r in active) / sum(weights[r] for r in active) if active and not deferred else None
        state = "INPUT_INCOMPLETE" if deferred else "REVISION_REQUIRED" if issues else "REVIEW_COMPLETE"
        findings = []
        for item in reviews["TECH"]["questions"][qid]["fact_review"]["findings"]:
            claim = fact_input["claims"][qid][item["claim_id"]]
            kinds = sorted({fact_input["sources"][source_id]["kind"] for source_id in claim["source_ids"]})
            findings.append({**item, "claim_quote": claim["quote"], "availability": claim["availability"], "source_kinds": kinds})
        coverage = "INPUT_INCOMPLETE" if any(c["availability"] == "input_missing" for c in fact_input["claims"][qid].values()) else "REVIEWED" if any(c["availability"] == "provided" for c in fact_input["claims"][qid].values()) else "NOT_PROVIDED"
        material = [item for item in findings if item["status"] == "CONFLICT" and item["impact"] == "material"]
        flags = []
        if material: flags.append("MATERIAL_FACT_CONFLICT")
        if compliance[qid]["status"] == "VIOLATION": flags.append("COMPLIANCE_VIOLATION")
        if deferred or coverage == "INPUT_INCOMPLETE": flags.append("INPUT_INCOMPLETE")
        attention.extend({"question_id": qid, "flag": flag} for flag in flags)
        questions[qid] = {"role_indices": role_indices, "weighted_index": index, "state": state,
                          "applicable_axes": sorted(applicable), "deferred_axes": deferred, "issues": issues,
                          "compliance": compliance[qid], "fact_review": {"coverage": coverage, "findings": findings},
                          "attention_flags": flags,
                          "score_interpretation": "UNAVAILABLE" if index is None else "PROVISIONAL_FACT_CONFLICT" if material else "WRITING_ONLY",
                          "interview": reviews["TECH"]["questions"][qid].get("interview")}
        all_issues.extend(issues)
    means = {}
    for role in ("HR", "TECH"):
        values = [q["role_indices"][role] for q in questions.values() if q["role_indices"][role] is not None]
        pending = any(any(item['role'] == role for item in q['deferred_axes']) for q in questions.values())
        means[role] = sum(values) / len(values) if values and not pending else None
    incomplete = any(q["weighted_index"] is None for q in questions.values())
    state = "INPUT_INCOMPLETE" if incomplete else "REVISION_REQUIRED" if all_issues else "REVIEW_COMPLETE"
    org = (context or {}).get("organization_contract") or spec.get("organization_contract") or {}
    if not isinstance(org, dict): org = {}
    return {"schema_version": 2, "evaluation_version": EVALUATION_VERSION,
            "state": state, "weights": weights, "questions": questions, "role_means": means,
            "mean_weighted_index": None if incomplete else sum(q["weighted_index"] for q in questions.values()) / len(questions),
            "score_interpretation": "UNAVAILABLE" if incomplete else "PROVISIONAL_FACT_CONFLICT" if any(a["flag"] == "MATERIAL_FACT_CONFLICT" for a in attention) else "WRITING_ONLY",
            "attention_flags": attention, "issues": all_issues, "organization_contract": org,
            "index_note": "작성 품질의 미보정 내부 지수. 규격·근거 대조는 점수에 합산하지 않습니다. 자료 미제공은 정상 사용이며 사실 검증 완료를 뜻하지 않습니다. 핵심 사실 충돌은 점수와 별도로 먼저 해결해야 합니다. v4 점수와 직접 비교하지 않습니다."}


def review_age_notice(token, now=None):
    try:
        created = datetime.fromisoformat(token["created_at"].replace("Z", "+00:00"))
        hours = ((now or datetime.now(timezone.utc)) - created).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        return "평가 패킷 생성 시각을 확인할 수 없습니다. 원래 실행 기록을 확인하십시오."
    return f"평가 패킷 생성 후 {int(hours)}시간 경과. 입력 해시는 유효하며 시간만으로 무효화하지 않습니다. 재사용 시 원래 실행 시각을 밝히십시오." if hours >= 24 else None


def format_index(value):
    return "N/A" if value is None else f"{value:.1f}"


def report_review(draft, spec, reviews, weights, context=None, summary=None):
    summary = summary or summarize_review(draft, spec, reviews, weights, context)
    lines = ["# 자소서 내부 검토", "", "이 검토는 채용 합격 여부·확률을 예측하지 않습니다. 참고 지수는 외부 채용 결과로 보정되지 않았습니다.",
             "인용 일치는 해당 문장이 본문에 있다는 뜻입니다. 실제 경험·성과의 진실성은 출처 원문과 별도로 대조해야 합니다.", "",
             f"작성 검토 상태: **{summary['state']}**", f"평가 버전: {summary['evaluation_version']} · 점수 해석: {summary['score_interpretation']}", "", "## 중요 확인 사항"]
    for flag in summary["attention_flags"]:
        lines.append(f"- 문항 {flag['question_id']}: {flag['flag']}")
    for qid, q in summary["questions"].items():
        for item in q["fact_review"]["findings"]:
            if item["status"] == "CONFLICT" and item["impact"] == "material":
                lines.append(f"- 문항 {qid} 핵심 주장 불일치: “{item['claim_quote']}” — {item['rationale']}")
        for item in q['deferred_axes']:
            lines.append(f"- 문항 {qid}/{item['axis']} 평가 유보: {item['reason']}")
    if not summary["attention_flags"]:
        lines.append("- 핵심 사실 충돌·규격 위반·필수 평가 입력 누락으로 표시된 항목 없음. 제출 승인이나 사실 검증 완료 판정은 아닙니다.")
    lines += ["", "## 글의 보완 사항"]
    for item in summary["issues"]:
        lines.append(f"- 문항 {item['question_id']} / {item['role']} {item['axis']} / {item['severity']}: {item['rationale']}")
    if not summary["issues"]:
        lines.append("- 현재 검토에서 표시된 확인·보완 사항 없음.")
    lines += ["", "## 작성 점수 요약", "", "| 문항 | HR / 100 | TECH / 100 | 가중 지수 / 100 | 적용 축 | 상태 |", "| --- | ---: | ---: | ---: | --- | --- |"]
    for qid, q in summary["questions"].items():
        lines.append(f"| {qid} | {format_index(q['role_indices']['HR'])} | {format_index(q['role_indices']['TECH'])} | {format_index(q['weighted_index'])} | {', '.join(q['applicable_axes'])} | {q['state']} |")
    lines += [f"| 평균 | {format_index(summary['role_means']['HR'])} | {format_index(summary['role_means']['TECH'])} | {format_index(summary['mean_weighted_index'])} | | |", "",
              f"문항 평균 작성 지수: {format_index(summary['mean_weighted_index'])}/100 (미보정)", summary['index_note'],
              f"평가 당시 가중치 HR:TECH = {weights['HR']:g}:{weights['TECH']:g}. 문항에서 적용 축이 없는 역할은 제외하고 남은 가중치를 정규화합니다.",
              "REVIEW_COMPLETE는 현재 자료의 검토 절차 완료를 뜻하며 합격권이나 제출 승인을 뜻하지 않습니다.",
              "규격·사실 확인은 별도 결과이며 작성 점수만으로 제출 준비 완료를 선언하지 않습니다."]
    lines += ["", "## 규격 검사 · 점수 미합산"]
    for qid, q in summary["questions"].items():
        c = q["compliance"]
        lines.append(f"- 문항 {qid}: {c['status']} · 저장 규격 충족={c['declared_limits_met']} · 출처: {c['source']}")
        lines.extend(f"  - {issue}" for issue in c["issues"])
    lines += ["", "## 선택적 근거 대조 · 점수 미합산"]
    for qid, q in summary["questions"].items():
        fact = q["fact_review"]
        lines.append(f"- 문항 {qid}: {fact['coverage']}")
        if fact['coverage'] == 'NOT_PROVIDED':
            lines.append("  - 대조 자료 없음. 사용자 진술을 전제로 작성 검토를 수행했으며, 증빙 부족 감점이나 허위 판정이 아닙니다.")
        for item in fact["findings"]:
            lines.append(f"  - {item['status']} / {item['impact']} / 자료 종류={', '.join(item['source_kinds']) or '없음'}: “{item['claim_quote']}” — {item['rationale']}")
            for ref in item["evidence"]:
                lines.append(f"    - {ref['source_id']}: “{ref['quote']}”")
    for qid in draft:
        applicable = set(spec['questions'][qid]['applicable_axes'])
        lines += ["", f"### 문항 {qid}", "", f"질문: {spec['questions'][qid].get('prompt') or '문항 원문 미제공'}", ""]
        for role in ("HR", "TECH"):
            review = reviews[role]["questions"][qid]
            for axis in sorted(ROLE_AXES[role]):
                item = review["axis_evidence"][axis]
                if axis not in applicable:
                    lines.append(f"- {axis}: N/A — {item['reason']}")
                elif item["status"] == "DEFERRED":
                    lines.append(f"- {axis}: 평가 유보 — {item['reason']}")
                else:
                    lines.append(f"- {axis}: {review['scores'][axis]}/5, {item['severity']} — {item['rationale']}")
                    lines.append("  근거: " + " / ".join(f"“{q}”" for q in item["quotes"]))
    lines += ["", "## 독립 TECH 면접 후속 질문"]
    for qid, q in summary['questions'].items():
        interview = q['interview']
        if interview is None:
            lines.append(f"- 문항 {qid}: 면접 검토가 포함되지 않은 구형 평가입니다. 현재 질문으로 대체하지 않습니다.")
            continue
        if not interview['questions']:
            lines.append(f"- 문항 {qid} 질문 생략: {interview['omission_reason']}")
        for item in interview['questions']:
            lines += ["", f"### 문항 {qid} · {item['topic']}: {item['question']}",
                      f"- 원고 근거: “{item['anchor_quote']}”", f"- 확인 의도: {item['intent']}",
                      f"- 답변 가능 범위: {item['answer_scope']}",
                      "- 추가 확인: " + (" / ".join(item['facts_to_confirm']) or "평가자가 추가 사실 확인을 요청하지 않음")]
    org = summary['organization_contract']
    parent, service = org.get('parent_legal_entity'), org.get('client_service_domain')
    if parent and service and parent != service:
        lines += ["", "## 조직 관계 면접 가이드", f"- 제공된 채용 법인: {parent}", f"- 제공된 고객사/담당 서비스: {service}"]
        evidence = org.get('relationship_evidence')
        lines.append("- 관계 근거: " + (json.dumps(evidence, ensure_ascii=False) if evidence else "미확인. 명칭이 다르다는 이유로 위탁·고용 관계를 확정하지 않습니다."))
        lines.append("- 답변 준비: 채용 법인의 역할과 담당 서비스의 업무를 제공된 근거로 구별하고, 본인이 수행한 경험의 적용 범위를 설명합니다. 조직 관련 독립 질문은 위 organization 항목을 참고합니다.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft")
    parser.add_argument("hr_eval")
    parser.add_argument("tech_eval")
    parser.add_argument("--spec")
    parser.add_argument("--context")
    parser.add_argument("--session-token")
    parser.add_argument("--historical-import", action="store_true")
    parser.add_argument("--hr-weight", type=float)
    parser.add_argument("--tech-weight", type=float)
    parser.add_argument("--weight-profile", choices=sorted(WEIGHT_PROFILES))
    parser.add_argument("--out")
    parser.add_argument("--out-json")
    args = parser.parse_args()
    try:
        reviews = {"HR": read_json(args.hr_eval), "TECH": read_json(args.tech_eval)}
        if args.historical_import:
            output = "# 과거 평가 기록\n\n상태: **HISTORICAL_UNVERIFIED**\n\n현재 초안의 평가로 재사용하지 않습니다. 입력 출처와 실행 동일성이 검증되지 않아 점수를 집계하지 않습니다.\n\n"
            output += "기록 파일: " + ", ".join(str(Path(p).resolve()) for p in (args.hr_eval, args.tech_eval))
            summary = {"schema_version": 1, "state": "HISTORICAL_UNVERIFIED", "score": None}
        else:
            if not args.spec:
                raise ContractError("현재 검토에는 --spec이 필요합니다.")
            weights = resolve_weights(args.weight_profile, args.hr_weight, args.tech_weight)
            draft, spec = load_draft(args.draft), read_json(args.spec)
            validate_spec(spec, draft, require_axes=True)
            token_path = resolve_token(args.hr_eval, args.tech_eval, args.session_token)
            token = verify_manifest(token_path, args.draft, args.spec, args.context, ROOT)
            expected_weights = token.get("review_weights")
            if expected_weights != weights:
                raise ContractError("평가자 가중치가 패킷 생성 당시와 다릅니다.")
            context = read_json(args.context) if args.context else {}
            for role in reviews:
                validate_evaluation(reviews[role], role, draft, spec, token, context)
            summary = summarize_review(draft, spec, reviews, weights, context)
            summary.update(run_id=token['run_id'], created_at=token.get('created_at'), inputs=token['inputs'])
            notice = review_age_notice(token)
            summary['advisories'] = [notice] if notice else []
            output = report_review(draft, spec, reviews, weights, context, summary)
            if notice:
                output += "\n\n참고: " + notice
    except (ContractError, OSError, ValueError) as exc:
        output = f"상태: NOT_EVALUABLE\n{exc}\n점수는 산출하지 않았습니다. 원인을 수정하고 해당 평가를 다시 실행하십시오."
        print(output)
        if args.out:
            Path(args.out).write_text(output, encoding="utf-8")
        if args.out_json:
            Path(args.out_json).write_text(json.dumps({"schema_version": 1, "state": "NOT_EVALUABLE", "score": None, "error": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2
    print(output)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
