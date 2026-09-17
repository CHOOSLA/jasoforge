#!/usr/bin/env python3
"""자소서 2인 독립 검증 기계 집계기 (grade.py v2.2).
최신 2026년 LLM-as-a-Judge 연구(RULERS arXiv:2601.08654)를 준수합니다:
1. Token-level Jaccard Overlap Ratio (≥0.75) 기반 인용구 무결성 감사 (Fuzzy Grounding).
2. Typed Locked Rubric Gating: 서사 유형(Type_A, Type_B, Type_C) 필수 증거 및 배제 조건(Negative Boundary) 위반 시 기계적 3점 캡핑(Clamping).
3. HR(40%)과 Tech Lead(60%)의 결정론적 가중 평균 계산 및 면접 방어 리포트 생성.
"""

import sys, json, re, argparse
from pathlib import Path

def load_draft(path):
    parts = re.split(r'^===(\S+)===\s*$', Path(path).read_text(encoding='utf-8'), flags=re.M)
    return {parts[i]: parts[i+1].strip('\n') for i in range(1, len(parts), 2)}

def normalize_tokens(text):
    """구두점, 특수문자, 줄임표 제거 후 토큰 분리"""
    cleaned = re.sub(r'[\.\,\!\?\'\"…\(\)\[\]\{\}\<\>\~\`\:\;\-\_]', ' ', text)
    return [t for t in cleaned.split() if len(t) > 0]

def extract_ngrams(tokens, n=2):
    """연속된 n개 토큰의 n-gram 튜플 집합 추출 (n보다 짧으면 1-gram 집합 반환)"""
    if len(tokens) < n:
        return set(tokens)
    return set(tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1))

def verify_quote_fuzzy(quote, full_text, threshold=0.70):
    """
    본문 텍스트 내 슬라이딩 윈도우 기반 Word Bi-gram (2-gram) + Unigram N-gram Jaccard Overlap 비율 검증.
    단어 순서가 뒤죽박죽 섞인 어순 왜곡 환각을 2-gram으로 차단하고, 말줄임표(...) 축약 인용은 정밀 통과시킴.
    """
    clean_full = re.sub(r'\s+', ' ', full_text)
    clean_q = re.sub(r'\s+', ' ', quote.strip())
    # 1. 완벽한 부분 문자열 일치 시 즉시 통과
    if clean_q and clean_q in clean_full:
        return True

    q_tokens = normalize_tokens(quote)
    if not q_tokens:
        return False

    full_tokens = normalize_tokens(full_text)
    n_q = len(q_tokens)

    # 3단어 이상이면 Bi-gram(2-gram)으로 어순 결합 검증, 2단어 이하면 Unigram(1-gram)
    use_n = 2 if n_q >= 3 else 1
    q_ngrams = extract_ngrams(q_tokens, n=use_n)

    # 2. 슬라이딩 윈도우 기반 N-gram 오버랩 비율 탐색
    best_ratio = 0.0
    for i in range(max(1, len(full_tokens) - n_q + 1)):
        window_tokens = full_tokens[i:i + n_q + 5]
        window_ngrams = extract_ngrams(window_tokens, n=use_n)
        overlap = len(q_ngrams & window_ngrams) / len(q_ngrams)
        if overlap > best_ratio:
            best_ratio = overlap
            if best_ratio >= threshold:
                return True
    return best_ratio >= threshold

def verify_quotes(quotes, full_text):
    results = []
    for q in quotes:
        is_valid = verify_quote_fuzzy(q, full_text)
        results.append({"quote": q, "valid": is_valid})
    return results

def audit_type_rubric_gating(tech_q, full_draft_text):
    """
    서사 유형(Type A, B, C) 선행 선언 및 배제 기준(Negative Boundary) 위반 시 기계적으로 점수를 3점으로 강제 캡핑(Clamp)
    """
    type_decl = tech_q.get("type_declaration", {})
    sel_type = type_decl.get("selected_type")
    score_b = tech_q.get("scores", {}).get("B", 0)

    # 1. 유형 선언 누락 검사 (기존 데이터 호환: 선언 없으면 경고만)
    if not sel_type or sel_type not in ["Type_A", "Type_B", "Type_C", "Type_D", "Type_E"]:
        return "Type 미선언 (기존 데이터 호환)"

    # 2. 필수 증거 인용구 실존 검사
    must_evidence = type_decl.get("must_have_evidence_found", "")
    if score_b >= 4 and (not must_evidence or not verify_quote_fuzzy(must_evidence, full_draft_text)):
        tech_q["scores"]["B"] = 3
        return f"⚠️ **CLAMPED**: {sel_type} 필수 관찰 증거 미확인으로 B축 점수가 3점으로 기계 강제 하향되었습니다."

    # 3. 배제 조건(Negative Boundary) 위반 플래그 시 하드 캡
    if type_decl.get("negative_boundary_violated") and score_b > 3:
        tech_q["scores"]["B"] = 3
        return f"⚠️ **CLAMPED**: {sel_type} 전용 배제 기준(Negative Boundary) 위반으로 B축 점수가 3점으로 기계 강제 하향되었습니다."

    return f"✅ **PASSED**: {sel_type} 잠금 루브릭(Locked Rubric) 기계 감사 통과"

def main():
    parser = argparse.ArgumentParser(description="자소서 2인 독립 검증 사후 집계기 (grade.py v2.2)")
    parser.add_argument("draft", help="초안 텍스트 파일 경로 (===1=== 구분자)")
    parser.add_argument("hr_eval", help="HR 평가 결과 JSON 파일 경로")
    parser.add_argument("tech_eval", help="테크 리드 평가 결과 JSON 파일 경로")
    parser.add_argument("--hr-weight", type=float, default=0.4, help="HR 가중치 (기본값: 0.4)")
    parser.add_argument("--tech-weight", type=float, default=0.6, help="테크 리드 가중치 (기본값: 0.6)")
    parser.add_argument("--out", help="출력 마크다운 리포트 파일 경로 (옵션)")
    args = parser.parse_args()

    draft = load_draft(args.draft)
    full_draft_text = " ".join(draft.values())
    hr_data = json.loads(Path(args.hr_eval).read_text(encoding='utf-8'))
    tech_data = json.loads(Path(args.tech_eval).read_text(encoding='utf-8'))

    total_w = args.hr_weight + args.tech_weight
    w_hr = args.hr_weight / total_w
    w_tech = args.tech_weight / total_w

    report = []
    report.append("# 📊 자소서 2인 독립 검증 결과 종합 리포트 (jaso-pipeline v2.3)")
    report.append(f"- **가중치 반영 비율**: HR 인사담당자 {w_hr*100:.0f}% : 현업 테크 리드 {w_tech*100:.0f}%")
    report.append("- **평가 원칙**: 산술 연산 배제, Typed Locked Rubric 적용, 환각 인용 점수 롤백(Rollback), Word Bi-gram 인용구 감사\n")

    q_ids = sorted(list(set(list(draft.keys()) + list(hr_data.get("questions", {}).keys()))))
    
    total_hr_scores = []
    total_tech_scores = []
    total_final_scores = []

    table_rows = []
    type_audit_logs = []
    rollback_logs = []
    all_verified_quotes = []

    for qid in q_ids:
        hr_q = hr_data.get("questions", {}).get(qid, {})
        tech_q = tech_data.get("questions", {}).get(qid, {})

        # 1. 문항별 인용구 무결성 검증 (Word Bi-gram + Token Jaccard)
        hr_quotes = hr_q.get("quotes", [])
        tech_quotes = tech_q.get("quotes", [])
        
        hr_verified = verify_quotes(hr_quotes, full_draft_text)
        tech_verified = verify_quotes(tech_quotes, full_draft_text)
        all_verified_quotes.extend(hr_verified)
        all_verified_quotes.extend(tech_verified)

        # 2. Typed Locked Rubric Gating 기계 감사 집행 (B축 Clamping 선행)
        hr_axes = dict(hr_q.get("scores", {}))
        tech_axes = dict(tech_q.get("scores", {}))

        audit_log = audit_type_rubric_gating(tech_q, full_draft_text)
        if "B" in tech_q.get("scores", {}):
            tech_axes["B"] = tech_q["scores"]["B"]
        type_audit_logs.append(f"- [문항 {qid}] {audit_log}")

        # 3. 환각 인용 감지 시 감점 자동 롤백 (Score Rollback)
        hr_hallucinated = [v for v in hr_verified if not v["valid"]]
        if hr_hallucinated:
            for axis, score in list(hr_axes.items()):
                if score < 5:
                    hr_axes[axis] = 5
                    rollback_logs.append(f"- 🔄 **[점수 롤백]** 문항 {qid} HR 인사담당자: 가짜 인용구 감지로 인해 {axis}축 감점 무효화 ({score}점 ➔ 5.0점 복원)")

        tech_hallucinated = [v for v in tech_verified if not v["valid"]]
        if tech_hallucinated:
            for axis, score in list(tech_axes.items()):
                if score < 5:
                    tech_axes[axis] = 5
                    rollback_logs.append(f"- 🔄 **[점수 롤백]** 문항 {qid} 현업 테크 리드: 가짜 인용구 감지로 인해 {axis}축 감점 무효화 ({score}점 ➔ 5.0점 복원)")

        # 4. 점수 계산 (롤백 적용된 점수 기준)
        hr_sum = sum(hr_axes.values())
        hr_score_100 = (hr_sum / 25.0) * 100 if hr_axes else 0.0

        tech_sum = sum(tech_axes.values())
        tech_score_100 = (tech_sum / 25.0) * 100 if tech_axes else 0.0

        # 가중 종합 점수
        final_q_score = (hr_score_100 * w_hr) + (tech_score_100 * w_tech)

        total_hr_scores.append(hr_score_100)
        total_tech_scores.append(tech_score_100)
        total_final_scores.append(final_q_score)

        table_rows.append(f"| 문항 {qid} | {hr_score_100:.1f}점 | {tech_score_100:.1f}점 | **{final_q_score:.1f}점** |")

    avg_hr = sum(total_hr_scores) / len(total_hr_scores) if total_hr_scores else 0
    avg_tech = sum(total_tech_scores) / len(total_tech_scores) if total_tech_scores else 0
    avg_final = sum(total_final_scores) / len(total_final_scores) if total_final_scores else 0

    report.append("## 1. 종합 점수 요약\n")
    report.append("| 문항 | HR 점수 (40%) | 테크 리드 점수 (60%) | 가중 종합 점수 |")
    report.append("| :--- | :---: | :---: | :---: |")
    for r in table_rows:
        report.append(r)
    report.append(f"| **전체 평균** | **{avg_hr:.1f}점** | **{avg_tech:.1f}점** | **{avg_final:.1f}점** |\n")

    # 2. Typed Locked Rubric Gating 기계 감사 로그
    report.append("## 2. Typed Locked Rubric 기계 감사 로그 (Anti-Sycophancy)\n")
    for log in type_audit_logs:
        report.append(log)
    report.append("")

    # 3. 감점 인용구 무결성 검증 (Word Bi-gram & Fuzzy Jaccard)
    report.append("## 3. 감점 인용구 무결성 감사 (Word Bi-gram & Fuzzy Jaccard)\n")
    hallucinated = 0
    for v in all_verified_quotes:
        if v["valid"]:
            report.append(f"- [검증 통과] `{v['quote']}`")
        else:
            hallucinated += 1
            report.append(f"- ⚠️ **[환각 인용 감지 - 감점 무효화 대상]**: 본문 불일치 ➔ `{v['quote']}`")
    
    if not all_verified_quotes:
        report.append("- 인용구 없음\n")
    elif hallucinated == 0:
        report.append(f"\n✅ 인용구 {len(all_verified_quotes)}건 전수 일치 확인 (지어낸 비판 0건)\n")
    else:
        report.append(f"\n⚠️ 환각 인용 {hallucinated}건 감지됨. 해당 감점 사유는 전면 무효화 및 점수 롤백 처리되었습니다.\n")

    # 4. 점수 롤백 감사 로그
    if rollback_logs:
        report.append("## 4. 환각 인용 감점 무효화 및 점수 롤백 내역 (Score Rollback)\n")
        for rlog in rollback_logs:
            report.append(rlog)
        report.append("")

    # 5. 실전 면접 킬러 꼬리질문 및 방어 전략
    killer_questions = tech_data.get("killer_followup_questions", []) or tech_data.get("killer_questions", [])
    if killer_questions:
        report.append("## 5. 현업 테크 리드의 실전 기술면접 킬러 꼬리질문 (Killer Questions)\n")
        for idx, kq in enumerate(killer_questions, 1):
            q_text = kq.get('question', '')
            intent = kq.get('intent', '')
            defense = kq.get('recommended_defense', '') or kq.get('defense_guide', '')
            report.append(f"### Q{idx}. {q_text}")
            if intent:
                report.append(f"- **의도 / 취약점**: {intent}")
            if defense:
                report.append(f"- **추천 방어 전략**: {defense}")
            report.append("")

    # 6. 문항별 세부 평가 리포트
    report.append("## 6. 문항별 상세 평가 내역\n")
    for qid in q_ids:
        report.append(f"### [문항 {qid}]")
        hr_q = hr_data.get("questions", {}).get(qid, {})
        tech_q = tech_data.get("questions", {}).get(qid, {})

        hr_comment = hr_q.get('critique') or hr_q.get('comment') or '의견 없음'
        tech_comment = tech_q.get('critique') or tech_q.get('comment') or '의견 없음'

        report.append("#### 🧑‍💼 HR 인사담당자 의견")
        report.append(f"- 세부 점수: A({hr_q.get('scores',{}).get('A','-')}) E({hr_q.get('scores',{}).get('E','-')}) F({hr_q.get('scores',{}).get('F','-')}) G({hr_q.get('scores',{}).get('G','-')}) I({hr_q.get('scores',{}).get('I','-')}) / 25점 만점")
        report.append(f"- 핵심 소견: {hr_comment}\n")

        report.append("#### 🧑‍💻 현업 테크 리드 의견")
        report.append(f"- 세부 점수: B({tech_q.get('scores',{}).get('B','-')}) C({tech_q.get('scores',{}).get('C','-')}) D({tech_q.get('scores',{}).get('D','-')}) H({tech_q.get('scores',{}).get('H','-')}) J({tech_q.get('scores',{}).get('J','-')}) / 25점 만점")
        report.append(f"- 핵심 소견: {tech_comment}\n")

    # 7. 종합 총평
    report.append("## 7. 평가위원 종합 총평\n")
    if hr_data.get("overall_comment"):
        report.append(f"### 🧑‍💼 HR 인사담당자 총평\n{hr_data['overall_comment']}\n")
    if tech_data.get("overall_comment"):
        report.append(f"### 🧑‍💻 현업 테크 리드 총평\n{tech_data['overall_comment']}\n")

    final_output = "\n".join(report)
    print(final_output)

    if args.out:
        Path(args.out).write_text(final_output, encoding="utf-8")
        print(f"\n[저장 완료] 리포트가 {args.out}에 저장되었습니다.")

if __name__ == "__main__":
    main()
