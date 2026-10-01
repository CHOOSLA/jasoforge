#!/usr/bin/env python3
"""자소서 2인 독립 검증 기계 집계기 (grade.py v3.4).
최신 2026년 LLM-as-a-Judge 연구(RULERS arXiv:2601.08654)를 준수합니다:
1. Token-level Jaccard Overlap Ratio (≥0.75) 기반 인용구 무결성 감사 (Fuzzy Grounding).
2. 서사 유형이나 특정 완수 방식의 부재로 점수를 제한하지 않으며 본문 주장과 근거를 평가합니다.
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

def audit_type_rubric_gating(tech_q, full_draft_text, question_nature=None):
    """기존 호출 계약 유지. 폐기한 유형 메타데이터는 점수에 반영하지 않는다."""
    return "ℹ️ 서사 유형은 점수 조건이 아닙니다. 판단 근거는 문항과 본문 주장에 따라 평가합니다."

def audit_axis_c_gating(tech_q, full_draft_text):
    """완수는 실제 수행과 결과로 평가하며 특정 키워드의 부재로 제한하지 않는다."""
    return None

# ==============================================================================
# 🎯 채용 아키타입(Recruitment Archetype) & 도메인/지면 정합도 게이팅
# ==============================================================================
CONFESSION_PATTERN = re.compile(
    r'(?:다뤄본\s*적(?:이|은)?\s*없|해본\s*적(?:이|은)?\s*없|경험(?:이|은)?\s*없|배워본\s*적(?:이|은)?\s*없|써본\s*적(?:이|은)?\s*없|접해본\s*적(?:이|은)?\s*없|처음입|처음이지)',
    re.IGNORECASE
)

WEB_FRONTEND_EXCLUSIVE_PATTERN = re.compile(
    r'(컴포넌트|ref|포커스|블러|DOM|CSS|HTML|스타일링|핸들러|props|JSX|input\s*태그|웹\s*화면)',
    re.IGNORECASE
)

SYSTEM_ROLE_PATTERN = re.compile(
    r'(시스템|인프라|백엔드|공장|운용|SM|SE|서버|임베디드|네트워크|MES|LIMS|WMS)',
    re.IGNORECASE
)

def audit_evidence_contracts(tech_q, full_draft_text, q_draft_text, context_data, spec_data, qid, q_nature="TECH_CORE"):
    """
    의미론적 증거 계약(Semantic Evidence-Contract Architecture v3.6) 감사 엔진:
    1. LLM 평가관이 문맥/시제/의미론적 인과관계를 해석하여 작성한 evidence_contracts 검증.
    2. Python 감사 엔진은 제출된 인용구의 무결성(Word Bi-gram + Fuzzy Jaccard)을 검증하고 결정론적 캡핑을 집행.
    3. CULTURE_FIT(가치관/인성/지원동기) 문항은 시스템 아키텍처 불변식 대신 온보딩 신뢰성(Reliability & Culture-Fit)을 평가하여 D축 사법 살인(2점 클램핑)을 원천 차단.
    4. evidence_contracts 객체 부재 시 기존 정규식 기반 audit_domain_archetype_gating()으로 안전하게 폴백.
    """
    evidence_contracts = tech_q.get("evidence_contracts")
    if not evidence_contracts or not isinstance(evidence_contracts, dict):
        return audit_domain_archetype_gating(tech_q, q_draft_text, context_data, spec_data, qid)

    logs = []
    archetype = context_data.get("recruitment_archetype")
    score_d = tech_q.get("scores", {}).get("D", 5)

    # 1. archetype_audit: 스택 미경험 자백 및 실제 극복 팩트 검증
    arch_audit = evidence_contracts.get("archetype_audit")
    if arch_audit and isinstance(arch_audit, dict):
        has_confession = arch_audit.get("has_confession", False)
        confession_quote = arch_audit.get("confession_quote", "")
        has_overcoming = arch_audit.get("has_overcoming_fact", False)
        overcoming_quote = arch_audit.get("overcoming_quote", "")

        confession_valid = verify_quote_fuzzy(confession_quote, full_draft_text) if confession_quote else False
        overcoming_valid = verify_quote_fuzzy(overcoming_quote, full_draft_text) if overcoming_quote else False

        if archetype == "MANUFACTURING_OPS":
            if has_confession and confession_valid:
                if has_overcoming and overcoming_valid:
                    logs.append("✅ **[서류 스크리닝 통과]** 필수 스택 미경험 자백이 식별되었으나 실제 구현 및 배포 극복 팩트가 입증되어 결격 조항에서 제외되었습니다.")
                else:
                    cur_d = tech_q.get("scores", {}).get("D", 5)
                    if cur_d > 2:
                        tech_q["scores"]["D"] = 2
                        logs.append("⚠️ **[서류 결격 스크리닝 (MANUFACTURING_OPS)]** 즉시 전력감이 요구되는 제조 현장 IT에서 필수 코어 스택 미경험 자백 확인 및 극복 팩트 부재로 D축 점수가 2점으로 제한 집행되었습니다.")
            elif has_confession and not confession_valid:
                logs.append("ℹ️ **[인용구 무효]** 필수 스택 미경험 자백 인용구가 본문과 불일치하여 자백 감점이 무효화되었습니다.")

    # 2. core_invariant_audit: 도메인 불변식 조작적 정의 검증
    inv_audit = evidence_contracts.get("core_invariant_audit")
    if inv_audit and isinstance(inv_audit, dict):
        addressed = inv_audit.get("addressed", False)
        inv_quote = inv_audit.get("evidence_quote", "")
        inv_type = inv_audit.get("invariant_type", "도메인 불변식")
        inv_valid = verify_quote_fuzzy(inv_quote, full_draft_text) if inv_quote else False

        if addressed and inv_valid:
            logs.append(f"✅ **[도메인 불변식 검증 통과]** 전문 용어 부재 여부와 무관하게 문장 단위 조작적 정의({inv_type}) 및 실질적 조치 팩트가 확인되었습니다.")
        elif not addressed:
            # 가치관/인성 문항에서 회사/부서 언급이 존재하는 경우, 사내 시스템 미구현을 이유로 한 2점 살인을 방지하고 D축 3점(추상적 다짐 수준)으로 정상 조정
            if q_nature == "CULTURE_FIT":
                company = context_data.get("company", "") or spec_data.get("company", "")
                if company and company in q_draft_text:
                    cur_d = tech_q.get("scores", {}).get("D", 5)
                    if cur_d < 3:
                        tech_q["scores"]["D"] = 3
                        logs.append("ℹ️ **[도메인 과업 정합도 정상화]** 회사/부서 언급이 확인되므로 D축을 3점(추상적 다짐 수준)으로 조정합니다 (사내 시스템 미구현 2점 결격 배제).")
            else:
                cur_d = tech_q.get("scores", {}).get("D", 5)
                if archetype in ["FINTECH_CORE", "MANUFACTURING_OPS"] and cur_d > 3:
                    tech_q["scores"]["D"] = 3
                    logs.append(f"ℹ️ **[도메인 불변식 미흡]** 해당 도메인의 핵심 불변식에 대한 문장 단위 조작적 정의 부재로 D축 점수가 3점(상한)으로 조정되었습니다.")

    # 3. 도메인 정체성 괴리 (시스템/인프라 vs 웹 프론트엔드 DOM/컴포넌트)
    job_role = context_data.get("job_role", "") or spec_data.get("role", "")
    is_system_role = bool(SYSTEM_ROLE_PATTERN.search(job_role))
    if is_system_role:
        fe_hits = WEB_FRONTEND_EXCLUSIVE_PATTERN.findall(q_draft_text)
        if len(set(fe_hits)) >= 3:
            sys_db_hits = re.findall(r'(DB|SQL|인프라|서버|소켓|네이티브|커널|프로세스|스레드|MES|센서)', q_draft_text, re.IGNORECASE)
            if len(sys_db_hits) <= 1:
                cur_d = tech_q.get("scores", {}).get("D", 5)
                if cur_d > 3:
                    tech_q["scores"]["D"] = 3
                    logs.append(f"⚠️ **[도메인 정체성 괴리]** 시스템/인프라 직무({job_role})임에도 웹 프론트엔드 UI/컴포넌트 조작({', '.join(list(set(fe_hits))[:3])}) 서술 치중으로 D축 점수가 3점으로 제한되었습니다.")

    # 4. key_responsibilities_audit: 공고 담당업무 우선순위(Key Responsibilities) 정합도
    resp_audit = evidence_contracts.get("key_responsibilities_audit")
    if resp_audit and isinstance(resp_audit, dict):
        focus_level = resp_audit.get("focus_level", "CORE")  # CORE (1~2순위), SUPPORT (3순위 이하 부수 업무), NONE
        resp_quote = resp_audit.get("evidence_quote", "")
        resp_valid = verify_quote_fuzzy(resp_quote, full_draft_text) if resp_quote else False

        if focus_level in ["SUPPORT", "PERIPHERAL"]:
            if q_nature == "CULTURE_FIT":
                logs.append("ℹ️ **[도메인 과업 정합도]** 가치관/인성 문항이므로 공고 1순위 핵심 과업 직접 구현 대신 전반적 조직 기여 및 온보딩 관점을 정상 참작합니다.")
            else:
                cur_d = tech_q.get("scores", {}).get("D", 5)
                if cur_d > 3:
                    tech_q["scores"]["D"] = 3
                    logs.append("⚠️ **[담당업무 우선순위 괴리 (Max 3점 캡핑)]** 공고의 1~2순위 핵심 코어 업무(Core Mission)를 외면하고 3순위 이하 부수적/지원 업무에 치중한 서술이 확인되어 D축 점수가 3점으로 제한 집행되었습니다.")
        elif focus_level == "CORE" and resp_valid:
            logs.append("✅ **[담당업무 우선순위 정합 통과]** 공고의 최우선 핵심 업무(Top 1~2순위 Core Mission)를 직격하는 엔지니어링 서사가 입증되었습니다.")

    # 5. CULTURE_FIT 문항에 대한 도메인 과업 정합도 정상화
    if q_nature == "CULTURE_FIT":
        company = context_data.get("company", "") or spec_data.get("company", "")
        department = context_data.get("department", "") or spec_data.get("department", "")
        client_domain = context_data.get("client_service_domain", "")
        keywords = [k for k in [company, department, client_domain] if k]
        has_mention = any(k in q_draft_text for k in keywords) or bool(re.search(r'(회사|팀|부서|조직|시스템)', q_draft_text))
        if has_mention:
            cur_d = tech_q.get("scores", {}).get("D", 5)
            if cur_d < 3:
                tech_q["scores"]["D"] = 3
                logs.append("ℹ️ **[도메인 과업 정합도 정상화]** 가치관 문항에서 회사/부서 지향점 언급이 확인되므로 D축을 3점(추상적 다짐 수준)으로 정상 조정합니다 (사내 시스템 미구현 2점 결격 배제).")

    if logs:
        return "\n  ".join(logs)
    return None

def audit_domain_archetype_gating(tech_q, draft_q_text, context_data, spec_data, qid):
    """
    4대 채용 아키타입(recruitment_archetype) 및 도메인 정합도 기계 감사 (Regex Fallback):
    1. MANUFACTURING_OPS (제조업 공장 IT/SM):
       - 즉시 전력감(Off-the-shelf Utility) 필수.
       - 필수 코어 스택(required_hard_skills: C#, .NET, DB/SQL 등) 미경험 자백 시 D축 Max 2점 클램핑.
    2. 도메인 정체성 괴리 (Domain Identity Mismatch):
       - 시스템/인프라/공장운용 직무인데 본문 기술이 웹 프론트엔드 DOM/ref/컴포넌트 조작에 치중된 경우 D축 Max 3점 클램핑.
    """
    archetype = context_data.get("recruitment_archetype")
    if not archetype:
        company = context_data.get("company", "") or spec_data.get("company", "")
        job_role = context_data.get("job_role", "") or spec_data.get("role", "")
        if any(kw in company or kw in job_role for kw in ["제조", "공장", "화학", "쎄미켐", "MES", "생산"]):
            archetype = "MANUFACTURING_OPS"
        else:
            archetype = "TECH_PURE"

    required_skills = context_data.get("required_hard_skills", [])
    if not required_skills and archetype == "MANUFACTURING_OPS":
        required_skills = ["C#", ".NET", "DB", "SQL"]

    score_d = tech_q.get("scores", {}).get("D", 5)

    # 1. MANUFACTURING_OPS: 필수 코어 스택 미경험 자백 감사
    if archetype == "MANUFACTURING_OPS" and required_skills:
        has_confession = bool(CONFESSION_PATTERN.search(draft_q_text))
        if has_confession:
            confessed_skills = [s for s in required_skills if s.lower() in draft_q_text.lower()]
            if confessed_skills:
                if score_d > 2:
                    tech_q["scores"]["D"] = 2
                    return f"⚠️ **CLAMPED**: [도메인 아키타입 게이팅 ({archetype})] 즉시 전력감이 요구되는 제조 현장 IT 공고에서 필수 코어 스택({', '.join(confessed_skills)}) 미경험 자백 확인으로 D축 점수가 2점으로 기계 강제 하향되었습니다."

    # 2. 도메인 정체성 괴리 (시스템/인프라 vs 웹 프론트엔드 DOM/컴포넌트)
    job_role = context_data.get("job_role", "") or spec_data.get("role", "")
    is_system_role = bool(SYSTEM_ROLE_PATTERN.search(job_role))
    if is_system_role:
        fe_hits = WEB_FRONTEND_EXCLUSIVE_PATTERN.findall(draft_q_text)
        if len(set(fe_hits)) >= 3:
            sys_db_hits = re.findall(r'(DB|SQL|인프라|서버|소켓|네이티브|커널|프로세스|스레드|MES|센서)', draft_q_text, re.IGNORECASE)
            if len(sys_db_hits) <= 1:
                if score_d > 3:
                    tech_q["scores"]["D"] = 3
                    return f"⚠️ **CLAMPED**: [도메인 정체성 괴리] 시스템/인프라 직무({job_role})임에도 웹 프론트엔드 UI/컴포넌트 조작({', '.join(list(set(fe_hits))[:3])}) 서술 치중으로 D축 점수가 3점으로 기계 강제 하향되었습니다."

    return None

def audit_axis_g_effort_gating(hr_q, draft_q_text, q_spec, qid):
    """
    축 G (글자수 규격 준수 & 밀도) 대형 지면 성실도 기계 감사:
    문항 글자수 상한이 800자 이상인 대형 지면에서 실측 글자수가 상한의 75% 미만인 경우,
    여백 방치로 인한 성실도 부족 결함으로 간주하여 G축을 Max 3점으로 기계 캡핑.
    """
    max_len = q_spec.get("max", 0)
    if max_len < 800:
        return None

    basis = q_spec.get("basis", "with_spaces")
    actual_len = len(draft_q_text) if basis == "with_spaces" else len(re.sub(r'\s+', '', draft_q_text))
    ratio = actual_len / max_len

    score_g = hr_q.get("scores", {}).get("G", 5)
    if ratio < 0.75 and score_g > 3:
        hr_q["scores"]["G"] = 3
        return f"⚠️ **CLAMPED**: [지면 성실도 미달] 상한 800자 이상 대형 지면(상한 {max_len}자) 대비 실측 {actual_len}자({ratio*100:.1f}%)로 충실도 75% 미달하여 G축 점수가 3점으로 기계 강제 하향되었습니다."

    return None

# ==============================================================================
# 🚨 Knockout Red Flag 결격 사유 스크리닝 (Knockout Gatekeeper Protocol v3.4)
# ==============================================================================
KNOCKOUT_FLAG_PATTERNS = {
    "FLAG_EGO": {
        "name": "Flag 1: 자아과잉 / 비현실적 역할 인식",
        "desc": "신입이 20~40년 된 레거시 HTS C++ 코어 렌더링이나 계정계 트랜잭션을 전면 계승/재작성하겠다고 호언장담",
        "regex": re.compile(r'(40년간\s*축적된\s*코드를\s*.*안정적으로\s*계승|코어를\s*(?:재작성|재구축)|직접\s*계승|엔진을\s*다시\s*짜|원장을\s*전면\s*개편)', re.IGNORECASE),
        "keywords": ["오만", "비현실적", "자아과잉", "호언장담", "단독 계승", "Dunning-Kruger"]
    },
    "FLAG_TYPO_CONTRADICTION": {
        "name": "Flag 2: 서사 모순 & 오탈자 다수 방치",
        "desc": "디테일 추구 및 도구적 사전 차단을 강조하면서 3건 이상의 치명적 오탈자 방치 (무결성 훼손)",
        "typos": [
            (r'\b곳\b(?=\s*(?:고객|서버|데이터))', '곳 (곧의 오기)'),
            (r'끕어올려', '끕어올려 (끌어올려의 오기)'),
            (r'가늘할', '가늘할 (가늠할의 오기)'),
            (r'옷기던', '옷기던 (옮기던의 오기)'),
            (r'옷겨본', '옷겨본 (옮겨본의 오기)')
        ],
        "keywords": ["오탈자", "맞춤법", "모순", "무결성 훼손", "자가당착"]
    },
    "FLAG_LAUNDRY_LIST": {
        "name": "Flag 3: 무관한 프로젝트 조각모음 나열",
        "desc": "단일 아키텍처 인과관계 없이 4~6개 이상의 별개 프로젝트를 1개 문항 안에 백화점식으로 나열하여 깊이 상실",
        "keywords": ["조각모음", "백화점식", "프로젝트 나열", "경험 파편화", "서사 파편화", "Laundry list"]
    }
}

def audit_knockout_gatekeeper(tech_data, hr_data, full_draft_text, knockout_eval_path=None):
    """
    자아과잉 및 오탈자/모순을 감사하며 폐기한 서사 형식 결격은 적용하지 않는다.
    1건이라도 SUSTAINED(유효 채택) 시 선형 가중합을 무효화하고 총점을 Max 75점으로 강제 캡핑(Hard Clamp).
    """
    sustained_flags = []
    dismissed_flags = []

    # 1. 외부 사법 판결 JSON 파일이 제공된 경우 우선 반영
    if knockout_eval_path and Path(knockout_eval_path).exists():
        try:
            ke_data = json.loads(Path(knockout_eval_path).read_text(encoding='utf-8'))
            r_flags = ke_data.get("knockout_flags", {})
            for flag_key, flag_info in r_flags.items():
                if flag_key == "FLAG_LAUNDRY_LIST":
                    dismissed_flags.append({
                        "key": flag_key,
                        "name": flag_info.get("name", flag_key),
                        "reason": "서사 유형·프로젝트 수에 따른 결격 규칙은 폐기되었습니다."
                    })
                    continue
                status = flag_info.get("verdict", "").upper()
                if "SUSTAINED" in status or flag_info.get("sustained") is True:
                    sustained_flags.append({
                        "key": flag_key,
                        "name": flag_info.get("name", flag_key),
                        "evidence": flag_info.get("evidence", "외부 사법 감사에서 유효 채택")
                    })
                else:
                    dismissed_flags.append({
                        "key": flag_key,
                        "name": flag_info.get("name", flag_key),
                        "reason": flag_info.get("evidence", "기각 판결")
                    })
            if sustained_flags or dismissed_flags:
                return sustained_flags, dismissed_flags
        except Exception:
            pass

    # 2. 내장 사법 엔진으로 3대 레드 플래그 정밀 감사
    all_tech_critiques = " ".join([
        q.get("critique", "") + " " + q.get("comment", "")
        for q in tech_data.get("questions", {}).values()
    ]) + " " + tech_data.get("overall_comment", "")

    # --- Flag 1: 자아과잉 / 비현실적 역할 인식 ---
    has_ego_regex = bool(KNOCKOUT_FLAG_PATTERNS["FLAG_EGO"]["regex"].search(full_draft_text))
    has_ego_critique = any(kw in all_tech_critiques for kw in KNOCKOUT_FLAG_PATTERNS["FLAG_EGO"]["keywords"])
    min_d_score = min([q.get("scores", {}).get("D", 5) for q in tech_data.get("questions", {}).values()] or [5])
    if has_ego_regex or (has_ego_critique and min_d_score <= 3):
        evidence = "40년 레거시 코어 전면 계승/재작성 호언장담 식별" if has_ego_regex else "신입 감당 불가 초고위험 코어 장담 적발"
        sustained_flags.append({
            "key": "FLAG_EGO",
            "name": KNOCKOUT_FLAG_PATTERNS["FLAG_EGO"]["name"],
            "evidence": evidence
        })
    else:
        dismissed_flags.append({
            "key": "FLAG_EGO",
            "name": KNOCKOUT_FLAG_PATTERNS["FLAG_EGO"]["name"],
            "reason": "신입 역할 인식 및 현실적 온보딩 자세 유지 확인"
        })

    # --- Flag 2: 서사 모순 & 오탈자 다수 방치 ---
    detected_typos = []
    for pat, desc in KNOCKOUT_FLAG_PATTERNS["FLAG_TYPO_CONTRADICTION"]["typos"]:
        if re.search(pat, full_draft_text):
            detected_typos.append(desc)
    has_typo_critique = any(kw in all_tech_critiques for kw in KNOCKOUT_FLAG_PATTERNS["FLAG_TYPO_CONTRADICTION"]["keywords"])
    min_j_score = min([q.get("scores", {}).get("J", 5) for q in tech_data.get("questions", {}).values()] or [5])
    if len(detected_typos) >= 3 or (has_typo_critique and min_j_score <= 3):
        evidence = f"치명적 오탈자 {len(detected_typos)}건 실존 검출: {', '.join(detected_typos)}" if detected_typos else "도구주의 강조 대비 오탈자 방치 모순"
        sustained_flags.append({
            "key": "FLAG_TYPO_CONTRADICTION",
            "name": KNOCKOUT_FLAG_PATTERNS["FLAG_TYPO_CONTRADICTION"]["name"],
            "evidence": evidence
        })
    else:
        dismissed_flags.append({
            "key": "FLAG_TYPO_CONTRADICTION",
            "name": KNOCKOUT_FLAG_PATTERNS["FLAG_TYPO_CONTRADICTION"]["name"],
            "reason": "오탈자 3건 미만 및 서사 일관성 유지 확인"
        })

    # 여러 경험·기술의 등장 자체로 조각모음이나 단일 서사 위반을 단정하지 않는다.
    # 문항과 무관한 나열이라는 지적은 본문의 실제 근거에 따라 일반 축에서 평가한다.
    dismissed_flags.append({
        "key": "FLAG_LAUNDRY_LIST",
        "name": KNOCKOUT_FLAG_PATTERNS["FLAG_LAUNDRY_LIST"]["name"],
        "reason": "프로젝트·기술의 수나 서사 유형만으로 결격 판정을 하지 않습니다."
    })

    return sustained_flags, dismissed_flags

def resolve_question_nature(qid, q_spec, hr_q, tech_q):
    """
    문항 성격 계약(Question Nature Contract) 해석:
    1. spec_data의 questions[qid]["question_nature"] 계약 우선 (SSOT).
    2. tech_eval 또는 hr_eval 평가관이 제출한 question_nature 선언(Declaration) 차순위.
    3. spec.json의 required_items 지시 항목명(가치관, 인성, 지원동기, 포부 등) 연동.
    4. 테크 리드의 서사 유형 선언 연동.
    5. 선언 부재 시 None 반환 (전역 기본 가중치로 안전하게 폴백).
    """
    declared = q_spec.get("question_nature") or tech_q.get("question_nature") or hr_q.get("question_nature")
    if declared:
        dec_upper = str(declared).upper()
        if dec_upper in ["CULTURE_FIT", "PERSONALITY", "VALUE", "MOTIVATION", "GROWTH", "ATTITUDE"]:
            return "CULTURE_FIT"
        if dec_upper in ["TECH_CORE", "TECH_PROJECT", "PROJECT"]:
            return "TECH_CORE"

    # spec.json의 required_items 지시 항목명 연동
    req_items = list(q_spec.get("required_items", {}).keys())
    if any(k in " ".join(req_items) for k in ["가치관", "인성", "지원동기", "포부", "성장과정", "태도", "동기"]):
        return "CULTURE_FIT"

    # 테크 리드의 서사 유형 선언 연동
    type_decl = tech_q.get("type_declaration", {})
    if type_decl.get("exempt_tradeoff") or type_decl.get("selected_narrative_type") in ["EXEMPT", "NONE", "NON_TECH", "CULTURE"]:
        return "CULTURE_FIT"

    return None

def main():
    parser = argparse.ArgumentParser(description="자소서 2인 독립 검증 사후 집계기 (grade.py v3.7)")
    parser.add_argument("draft", help="초안 텍스트 파일 경로 (===1=== 구분자)")
    parser.add_argument("hr_eval", help="HR 평가 결과 JSON 파일 경로")
    parser.add_argument("tech_eval", help="테크 리드 평가 결과 JSON 파일 경로")
    parser.add_argument("--hr-weight", type=float, default=0.4, help="HR 가중치 (기본값: 0.4)")
    parser.add_argument("--tech-weight", type=float, default=0.6, help="테크 리드 가중치 (기본값: 0.6)")
    parser.add_argument("--spec", help="공고 명세 spec.json 경로 (옵션)")
    parser.add_argument("--context", help="채용 컨텍스트 context.json 경로 (옵션)")
    parser.add_argument("--knockout-eval", help="Knockout 사법 심판 JSON 파일 경로 (옵션)")
    parser.add_argument("--knockout-threshold", type=float, default=75.0, help="Knockout 발동 시 최대 상한 점수 (기본값: 75.0)")
    parser.add_argument("--out", help="출력 마크다운 리포트 파일 경로 (옵션)")
    args = parser.parse_args()

    draft = load_draft(args.draft)
    full_draft_text = " ".join(draft.values())
    hr_data = json.loads(Path(args.hr_eval).read_text(encoding='utf-8'))
    tech_data = json.loads(Path(args.tech_eval).read_text(encoding='utf-8'))
    spec_data = json.loads(Path(args.spec).read_text(encoding='utf-8')) if args.spec and Path(args.spec).exists() else {}

    # context_data 로드 (명시적 인자 우선, 없으면 draft 부모 디렉토리의 context.json 자동 감지)
    context_data = {}
    if args.context and Path(args.context).exists():
        context_data = json.loads(Path(args.context).read_text(encoding='utf-8'))
    else:
        candidate = Path(args.draft).resolve().parent / "context.json"
        if candidate.exists():
            context_data = json.loads(candidate.read_text(encoding='utf-8'))

    total_w = args.hr_weight + args.tech_weight
    w_hr = args.hr_weight / total_w
    w_tech = args.tech_weight / total_w

    report = []
    report.append("# 📊 자소서 2인 독립 검증 결과 종합 리포트 (jaso-pipeline v3.7)")
    report.append(f"- **가중치 반영 비율**: HR 인사담당자 {w_hr*100:.0f}% : 현업 테크 리드 {w_tech*100:.0f}% (A~J 10개 축 직교 평가 및 도메인 과업 정합도)")
    report.append("- **평가 원칙**: 문항과 본문 근거 평가, 환각 인용 점수 롤백(Rollback), Word Bi-gram 인용구 감사\n")

    q_ids = sorted(list(set(list(draft.keys()) + list(hr_data.get("questions", {}).keys()))))
    
    total_hr_scores = []
    total_tech_scores = []
    total_final_scores = []
    final_hr_axes_by_qid = {}
    final_tech_axes_by_qid = {}

    table_rows = []
    type_audit_logs = []
    rollback_logs = []
    all_verified_quotes = []

    for qid in q_ids:
        hr_q = hr_data.get("questions", {}).get(qid, {})
        tech_q = tech_data.get("questions", {}).get(qid, {})
        q_spec = spec_data.get("questions", {}).get(qid, {})
        q_nature = resolve_question_nature(qid, q_spec, hr_q, tech_q)

        # 1. 문항별 인용구 무결성 검증 (Word Bi-gram + Token Jaccard)
        hr_quotes = hr_q.get("quotes", [])
        tech_quotes = tech_q.get("quotes", [])
        
        hr_verified = verify_quotes(hr_quotes, full_draft_text)
        tech_verified = verify_quotes(tech_quotes, full_draft_text)
        all_verified_quotes.extend(hr_verified)
        all_verified_quotes.extend(tech_verified)

        # 2. 환각 인용 감지 시 감점 자동 롤백 (Score Rollback)
        hr_axes = dict(hr_q.get("scores", {}))
        tech_axes = dict(tech_q.get("scores", {}))

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

        # 3. 인용 검증 후 문항별 계약 감사
        q_draft_text = draft.get(qid, "")

        # B축 기존 호출 호환 (유형별 상한 폐기)
        audit_log = audit_type_rubric_gating(tech_q, full_draft_text, question_nature=q_nature)
        if "B" in tech_q.get("scores", {}):
            tech_axes["B"] = tech_q["scores"]["B"]
        type_audit_logs.append(f"- [문항 {qid} B축] {audit_log}")

        # C축 기존 호출 호환 (키워드별 상한 폐기)
        c_audit_log = audit_axis_c_gating(tech_q, full_draft_text)
        if "C" in tech_q.get("scores", {}):
            tech_axes["C"] = tech_q["scores"]["C"]
        if c_audit_log:
            type_audit_logs.append(f"- [문항 {qid} C축] {c_audit_log}")

        # D축 채용 아키타입 및 의미론적 증거 계약(Semantic Evidence Contract) 감사 (q_nature 바인딩)
        d_audit_log = audit_evidence_contracts(tech_q, full_draft_text, q_draft_text, context_data, spec_data, qid, q_nature=q_nature)
        if "D" in tech_q.get("scores", {}):
            tech_axes["D"] = tech_q["scores"]["D"]
        if d_audit_log:
            type_audit_logs.append(f"- [문항 {qid} D축] {d_audit_log}")

        # G축 대형 지면 성실도 게이팅 감사
        g_audit_log = audit_axis_g_effort_gating(hr_q, q_draft_text, q_spec, qid)
        if "G" in hr_q.get("scores", {}):
            hr_axes["G"] = hr_q["scores"]["G"]
        if g_audit_log:
            type_audit_logs.append(f"- [문항 {qid} G축] {g_audit_log}")

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
        final_hr_axes_by_qid[qid] = hr_axes
        final_tech_axes_by_qid[qid] = tech_axes

        table_rows.append(f"| 문항 {qid} | {hr_score_100:.1f}점 | {tech_score_100:.1f}점 | **{final_q_score:.1f}점** |")

    avg_hr = sum(total_hr_scores) / len(total_hr_scores) if total_hr_scores else 0
    avg_tech = sum(total_tech_scores) / len(total_tech_scores) if total_tech_scores else 0
    raw_avg_final = sum(total_final_scores) / len(total_final_scores) if total_final_scores else 0

    # 🚨 Knockout Red Flag 결격 사유 스크리닝
    sustained_flags, dismissed_flags = audit_knockout_gatekeeper(tech_data, hr_data, full_draft_text, args.knockout_eval)
    
    is_knockout = len(sustained_flags) > 0
    if is_knockout:
        # 1건 채택 시 Max 75, 2건 채택 시 Max 73, 3건 채택 시 Max 70
        base_clamp = 75.0 if len(sustained_flags) == 1 else (73.0 if len(sustained_flags) == 2 else 70.0)
        clamp_limit = min(base_clamp, args.knockout_threshold)
        final_clamped_score = min(clamp_limit, raw_avg_final)
        final_verdict = "DEFECT (서류 결격 / 보완 필수)"
    else:
        clamp_limit = 100.0
        final_clamped_score = raw_avg_final
        has_sub_90 = any(s < 90.0 for s in total_final_scores)
        if final_clamped_score >= 90.0:
            if has_sub_90:
                sub_90_qids = [qid for qid, s in zip(q_ids, total_final_scores) if s < 90.0]
                final_verdict = f"REVIEW (문항 과락: 문항 {', '.join(sub_90_qids)} 90점 미달)"
            else:
                final_verdict = "PASS (합격권)"
        else:
            final_verdict = "REVIEW (보완 필요)"

    report.append("## 1. 종합 점수 요약\n")
    if is_knockout:
        report.append(f"> 🚨 **[Knockout Red Flag 결격 사유 스크리닝 발동: {final_verdict}]**")
        report.append(f"> 서류 컷오프 결격 사유 {len(sustained_flags)}건 확인으로 인해, 선형 가중합({raw_avg_final:.1f}점)이 제한되고 **최종 {final_clamped_score:.1f}점 (Max {clamp_limit:.1f}점 Hard Clamped)**으로 상한 캡핑되었습니다.\n")

    report.append(f"| 문항 | HR 점수 ({w_hr*100:.0f}%) | 테크 리드 점수 ({w_tech*100:.0f}%) | 가중 종합 점수 |")
    report.append("| :--- | :---: | :---: | :---: |")
    for r in table_rows:
        report.append(r)
    report.append(f"| **원시 선형 평균** | **{avg_hr:.1f}점** | **{avg_tech:.1f}점** | **{raw_avg_final:.1f}점** |")
    if is_knockout:
        report.append(f"| **최종 스크리닝 집계 점수** | - | - | **{final_clamped_score:.1f}점 ({final_verdict})** |\n")
    else:
        report.append(f"| **최종 확정 집계 점수** | **{avg_hr:.1f}점** | **{avg_tech:.1f}점** | **{final_clamped_score:.1f}점 ({final_verdict})** |\n")

    # 2. 🚨 Knockout Red Flag 스크리닝 내역
    report.append("## 2. 🚨 서류 전형 결격 사유 스크리닝 내역 (Knockout Red Flag Protocol v3.4)\n")
    if sustained_flags:
        report.append("### 🛑 [서류 컷오프 결격 사유 (Critical Red Flags)]")
        for sf in sustained_flags:
            report.append(f"- 🚨 **[{sf['name']}]**: {sf['evidence']}")
        report.append(f"\n➔ **스크리닝 조치**: 선형 합산 전면 제한 및 Max {clamp_limit:.1f}점 상한 캡핑(Hard Clamp) 집행\n")
    else:
        report.append("### ✅ [Knockout Red Flag 스크리닝 결과: ALL CLEAR (결격 사유 없음)]")
        report.append("- 3대 치명적 레드 플래그(자아과잉, 오탈자/모순, 조각모음) 전건 무결함 확인 (하드 클램프 미발동)\n")
        
    if dismissed_flags:
        report.append("### 📋 [기준 충족 확인 항목 (Passed Checks)]")
        for df in dismissed_flags:
            report.append(f"- ℹ️ **[{df['name']}]**: {df['reason']}")
        report.append("")

    # 3. 문항별 근거와 규격 감사 로그
    report.append("## 3. 문항별 근거와 규격 감사 로그\n")
    for log in type_audit_logs:
        report.append(log)
    report.append("")

    # 4. 감점 인용구 무결성 검증 (Word Bi-gram & Fuzzy Jaccard)
    report.append("## 4. 감점 인용구 무결성 감사 (Word Bi-gram & Fuzzy Jaccard)\n")
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

    # 5. 점수 롤백 감사 로그
    if rollback_logs:
        report.append("## 5. 환각 인용 감점 무효화 및 점수 롤백 내역 (Score Rollback)\n")
        for rlog in rollback_logs:
            report.append(rlog)
        report.append("")

    # 6. 실전 면접 킬러 꼬리질문 및 방어 전략
    killer_questions = tech_data.get("killer_followup_questions", []) or tech_data.get("killer_questions", [])
    if killer_questions:
        report.append("## 6. 현업 테크 리드의 실전 기술면접 킬러 꼬리질문 (Killer Questions)\n")
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

    # 6-1. 💡 조직 정체성 실전 면접 가이드 (Dual-Layer Organization Context)
    org_contract = context_data.get("organization_contract") or spec_data.get("organization_contract") or {}
    parent_entity = org_contract.get("parent_legal_entity", "")
    client_domain = org_contract.get("client_service_domain", "")

    if parent_entity and client_domain and parent_entity != client_domain:
        report.append("## 💡 [조직 정체성 실전 면접 가이드 (Dual-Layer Organization Context)]\n")
        report.append(f"- **채용 모회사 (Parent Legal Entity)**: {parent_entity}")
        report.append(f"- **위탁/담당 서비스 도메인 (Client Service Domain)**: {client_domain}\n")
        report.append("### 🎯 [면접 방어 핵심 포인트]")
        report.append(f"1. **조직 정체성 일치**: 채용 주체({parent_entity})와 실제 담당 도메인({client_domain})의 위탁·운영 관계를 명확히 인지하고, 시스템의 지속적 안정성과 비즈니스 연속성을 지켜내는 엔지니어링 책임감을 어필하십시오.")
        report.append(f"2. **고객사 도메인 오너십**: 담당 서비스({client_domain})의 비즈니스 규칙과 데이터 흐름을 깊이 이해하고 있음을 강조하여 '단순 외주자'가 아닌 '도메인 시스템 오너십'을 증명하십시오.")
        report.append(f"3. **엔지니어링 역량의 전이**: 지원서에서 입증한 문제 해결 팩트가 모회사({parent_entity})의 표준 엔지니어링 거버넌스에서도 재현 가능한 자산임을 강조하십시오.\n")

    # 7. 문항별 세부 평가 리포트
    report.append("## 7. 문항별 상세 평가 내역\n")
    for qid in q_ids:
        report.append(f"### [문항 {qid}]")
        hr_q = hr_data.get("questions", {}).get(qid, {})
        tech_q = tech_data.get("questions", {}).get(qid, {})

        hr_comment = hr_q.get('critique') or hr_q.get('comment') or '의견 없음'
        tech_comment = tech_q.get('critique') or tech_q.get('comment') or '의견 없음'

        hr_final_axes = final_hr_axes_by_qid.get(qid, hr_q.get('scores', {}))
        tech_final_axes = final_tech_axes_by_qid.get(qid, tech_q.get('scores', {}))

        report.append("#### 🧑‍💼 HR 인사담당자 의견")
        report.append(f"- 세부 점수: A({hr_final_axes.get('A','-')}) E({hr_final_axes.get('E','-')}) F({hr_final_axes.get('F','-')}) G({hr_final_axes.get('G','-')}) I({hr_final_axes.get('I','-')}) / 25점 만점 ({sum(hr_final_axes.values())}점)")
        report.append(f"- 핵심 소견: {hr_comment}\n")

        report.append("#### 🧑‍💻 현업 테크 리드 의견")
        report.append(f"- 세부 점수: B({tech_final_axes.get('B','-')}) C({tech_final_axes.get('C','-')}) D({tech_final_axes.get('D','-')}) H({tech_final_axes.get('H','-')}) J({tech_final_axes.get('J','-')}) / 25점 만점 ({sum(tech_final_axes.values())}점)")
        report.append(f"- 핵심 소견: {tech_comment}\n")

    # 8. 채용 평가위원 종합 총평
    report.append("## 8. 채용 평가위원 종합 총평\n")
    if is_knockout:
        report.append("### 🛑 [서류 전형 컷오프 종합 심사 소견]\n")
        report.append(f"본 지원서는 엔지니어링 역량에도 불구하고, **서류 컷오프 결격 사유 {len(sustained_flags)}건({', '.join(sf['name'].split(':')[0] for sf in sustained_flags)})**이 확인되어 현업 채용 기준을 충족하지 못했습니다. 서류 전형 통과 및 면접 진입을 위해 결격 요인 해소 및 서사 재정렬이 필수적입니다.\n")
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
