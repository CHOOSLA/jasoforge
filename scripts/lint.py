#!/usr/bin/env python3
"""자소서 기계 검사 (lint.py v3.4).
판단이 필요 없는 결정적 규격(글자수, 금지어, 키워드 충족도, 본문 30% 룰, 문장 리듬)만 본다.
표준 라이브러리만 사용합니다.
"""
import re, sys, json, unicodedata
from pathlib import Path

def load(path):
    parts = re.split(r'^===(\S+)===\s*$', Path(path).read_text(encoding='utf-8'), flags=re.M)
    return {parts[i]: parts[i+1].strip('\n') for i in range(1, len(parts), 2)}

def count(body):
    return len(body), len(re.sub(r'\s', '', body))

def count_metrics(body, metric_type="chars_with_space"):
    """
    지원하는 글자수/바이트 계량 규격:
    - chars_with_space: 공백 포함 글자수 (기본)
    - chars_without_space: 공백 제외 글자수
    - bytes_euckr: 국내 대기업(삼성, 현대차 등) ATS 표준 시뮬레이션 (Non-ASCII 2byte, ASCII 1byte, 개행 CRLF 2byte)
    - bytes_utf8: UTF-8 바이트 (한글 3byte, 영수 1byte)
    """
    n_all = len(body)
    n_ns = len(re.sub(r'\s', '', body))
    crlf_body = body.replace('\r\n', '\n').replace('\n', '\r\n')
    
    # 1. ATS 보수적 계량: 삼성/현대차 등 대기업 웹폼 JS 카운터 (charCode > 127 ? 2 : 1)
    b_ats = sum(2 if ord(c) > 127 else 1 for c in crlf_body)
    
    # 2. Strict EUC-KR 호환성 검사 (비호환 문자 검출)
    unsupported_chars = []
    try:
        crlf_body.encode('euc-kr')
    except UnicodeEncodeError:
        for ch in crlf_body:
            try:
                ch.encode('euc-kr')
            except UnicodeEncodeError:
                if ch not in unsupported_chars:
                    unsupported_chars.append(ch)
                    
    b_euckr = b_ats  # 언더카운팅 마감 폭탄 방지를 위해 보수적 ATS 시뮬레이션 계량 적용
    b_utf8 = len(crlf_body.encode('utf-8'))
    
    summary = f"공백포함 {n_all}자 / 공백제외 {n_ns}자 / ATS(EUC-KR) {b_euckr}B / UTF-8 {b_utf8}B"
    if unsupported_chars:
        summary += f" [⚠️ Strict EUC-KR 비호환 문자: {', '.join(unsupported_chars[:5])}]"
        
    if metric_type == "bytes_euckr":
        return b_euckr, summary, "ATS(EUC-KR) Bytes", unsupported_chars
    elif metric_type == "bytes_utf8":
        return b_utf8, summary, "UTF-8 Bytes", unsupported_chars
    elif metric_type == "chars_without_space":
        return n_ns, summary, "공백제외 글자수", unsupported_chars
    else:
        return n_all, summary, "공백포함 글자수", unsupported_chars

def sentences(body):
    # '다' 오분리 버그 수정: 마침표, 물음표, 느낌표 및 닫는 따옴표 뒤 공백 기준 분리 (고정 너비 룩비하인드)
    clean = body.replace('\n', ' ')
    raw_sents = re.split(r'(?<=[.!?])\s+|(?<=[.!?][\'"])\s+', clean)
    return [s.strip() for s in raw_sents if s.strip()]

def extract_real_paragraphs(body):
    """소제목(###, [소제목]), 구분선, 마크다운 메타를 제외한 순수 본문 텍스트 단락만 추출"""
    raw_paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
    content_paras = []
    header_pattern = re.compile(r'^(#+|\[.*?\]|===.*?===|[-*]\s|<.*?>)')
    for p in raw_paras:
        lines = [line.strip() for line in p.split('\n') if line.strip()]
        body_lines = [line for line in lines if not header_pattern.match(line)]
        if body_lines:
            content_paras.append(' '.join(body_lines))
    return content_paras

TECH_STOPWORDS = {
    '위해', '통해', '과정에서', '수', '있었습니다', '분석하여', '처리하고', '구현하여',
    '발생한', '문제를', '원인을', '파악하고', '개발하고', '적용하여', '진행하며', '개선하여',
    '대해', '있도록', '위한', '대한', '있는', '것을', '것이', '이를', '하고', '하며',
    '프로젝트를', '기능을', '데이터를', '시스템을', '코드를'
}

def check_repeated_ngrams(body, n=4, min_count=2):
    """연속된 n단어 이상의 동일 구문/클리셰 반복 사용 탐지 (불용어 필터링 탑재)"""
    clean = re.sub(r'[\.\,\!\?\'\"…\(\)\[\]\{\}\<\>\~\`\:\;\-\_]', ' ', body)
    tokens = [t for t in clean.split() if len(t) > 0]
    if len(tokens) < n:
        return []
    ngrams = [' '.join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]
    counts = {}
    for ng in ngrams:
        words = ng.split()
        # 불용어 비율이 50% 이상이면 일반 한국어 문맥 연결어로 간주하여 제외
        stop_ratio = sum(1 for w in words if w in TECH_STOPWORDS) / len(words)
        if stop_ratio >= 0.5:
            continue
        counts[ng] = counts.get(ng, 0) + 1
    repeated = [f'"{ng}"({c}회)' for ng, c in counts.items() if c >= min_count]
    return repeated[:4]

STRICT_PUBLIC_PATTERNS = [
    (r"(?<![가-힣])(부친|모친|아버지|어머니|삼촌|외삼촌|부모님|조부|조모|형제|자매|가족관계)(?![가-힣])", "공기업 블라인드 금지어: 가족/친인척 신원"),
    (r"(?<![가-힣])(육군|해군|공군|해병대|의경|공익근무|상근예비역|현역복무|하사|장교|복무부대|\b\d+사단\b)(?![가-힣])", "공기업 블라인드 금지어: 병역/군부대 세부정보"),
    (r"(\d{2}학번|\d{4}년생|\d{2}년생|\d{2}세(?:의|에|는|은|를|을|인|로|가|와|과|도|로서|라)?(?![가-힣0-9]))", "공기업 블라인드 금지어: 연령/학번 신원"),
    (r"(?<![가-힣])(남성|여성|남학생|여학생)(?![가-힣])", "공기업 블라인드 금지어: 성별 직접 표기"),
    (r"(출신\s*지역|고향은|태어난\s*곳)", "공기업 블라인드 금지어: 출신 지역")
]

def check(qid, body, spec, banned, proper_nouns, blind_level="NONE"):
    out = {'문항': qid, 'issues': [], 'info': {}}
    metric_type = spec.get('length_metric_type', spec.get('basis', 'chars_with_space'))
    if metric_type == 'with_spaces':
        metric_type = 'chars_with_space'
    elif metric_type == 'without_spaces':
        metric_type = 'chars_without_space'

    current_val, summary, unit_name, unsupported_chars = count_metrics(body, metric_type)
    out['info']['계량규격'] = f"{unit_name} 기준 ({summary})"
    if metric_type == "bytes_euckr" and unsupported_chars:
        out['issues'].append(f'WARN Strict EUC-KR 인코딩 불가 특수문자 발견 ({len(unsupported_chars)}종: {unsupported_chars[:5]}): 대기업 ATS 환경에 따라 깨짐 또는 바이트 오차 가능성')
    
    lo, hi = spec.get('min'), spec.get('max')
    # 상한선 기반 하드 하한선(80%) 및 소프트 안전선(85%)
    if not lo and hi:
        lo = int(hi * 0.8)

    if lo and current_val < lo:
        out['issues'].append(f'FAIL 글자수/용량 미달: {current_val} < {lo} ({unit_name}, 상한 대비 80% 미만)')
    elif hi and int(hi * 0.8) <= current_val < int(hi * 0.85):
        out['info']['압축서술구제'] = f"{current_val}/{hi} ({current_val/hi:.1%}) — 고밀도 압축 서술 구간 (핵심 4요소 충족 시 G축 5점 만점 구제 대상)"
    if hi and current_val > hi:
        out['issues'].append(f'FAIL 글자수/용량 초과: {current_val} > {hi} ({unit_name})')

    # 작성방법 항목 커버리지 — 키워드 0건이면 확실한 누락 신호
    for item, kws in spec.get('required_items', {}).items():
        hits = [k for k in kws if k in body]
        if not hits:
            out['issues'].append(f'WARN 작성방법 항목 근거 없음: "{item}" (탐색어 {kws})')
        else:
            out['info'].setdefault('항목충족', []).append(f'{item} ← {hits}')

    # 버린 대안(트레이드오프) 키워드 출현 게이트 (비기술 문항 면제)
    q_nature = spec.get('question_nature', '')
    is_exempt_tradeoff = spec.get('exempt_tradeoff') or q_nature in [
        'MOTIVATION', 'VALUES', 'VISION', 'COLLABORATION',
        'MOTIVATION_ASPIRATION', 'CULTURE_COLLAB_SOFT'
    ]
    discarded_kws = spec.get('discarded_alternative_keywords', [])
    if is_exempt_tradeoff:
        out['info']['버린대안식별'] = "비기술/지원동기 문항으로 버린 대안(Why Not) 검사 면제 (EXEMPT)"
    elif discarded_kws:
        d_hits = [dk for dk in discarded_kws if dk in body]
        if not d_hits:
            out['issues'].append(f'WARN 버린 대안(Why Not) 키워드 미발견: {discarded_kws} — B축 감점 방지를 위해 본문 명시 필수')
        else:
            out['info']['버린대안식별'] = f"확인됨: {d_hits}"

    # 블라인드 레벨 분기 적용
    effective_banned = list(banned)
    if blind_level == "ACADEMIC_RND_PERMISSIVE":
        # R&D 직무: 졸업논문, 연구실(Lab), 학회 발표 허용
        effective_banned = [b for b in effective_banned if "논문" not in b and "연구실" not in b]
    elif blind_level == "STRICT_PUBLIC_INSTITUTION":
        for pat, desc in STRICT_PUBLIC_PATTERNS:
            if re.search(pat, body):
                out['issues'].append(f'FAIL {desc} 발견: /{pat}/')

    for b in effective_banned:
        if re.search(b, body):
            out['issues'].append(f'FAIL 금지 표현 발견: /{b}/')

    # 순수 본문 단락 추출 (소제목/헤더 무시)
    real_paras = extract_real_paragraphs(body)

    # 1. 문항 단위 고유명사 밀도 검사 (Macro Specificity)
    matched_pns = [pn for pn in proper_nouns if pn in body]
    out['info']['고유명사'] = f'{len(matched_pns)}개 식별 ({", ".join(matched_pns[:5])}{"..." if len(matched_pns) > 5 else ""})'
    if len(matched_pns) == 0:
        out['issues'].append('WARN 문항 전체에 회사/도메인 고유명사 부재 — 어느 회사에나 붙을 수 있는 일반론 자소서 의심')

    # 2. 상투적 클리셰 템플릿 탐지 (Boilerplate / Cliche Detection)
    COMMON_CLICHES = [
        r"다양한\s*경험을\s*통해",
        r"문제\s*해결\s*역량을\s*(기르|키우|함양)",
        r"회사와\s*함께\s*성장하",
        r"열정을\s*가지고\s*(임하|배우)",
        r"최선을\s*다해\s*(노력|업무)",
        r"소통과\s*협력을\s*바탕으로",
        r"책임감을\s*가지고\s*완수",
        r"성실함을\s*무기로",
        r"빠르게\s*적응하여\s*기여",
        r"배우는\s*자세로\s*임하"
    ]
    for pattern in COMMON_CLICHES:
        m = re.search(pattern, body)
        if m:
            out['issues'].append(f"WARN 상투적 클리셰 감지: '{m.group(0)}' — 추상적 표현 대신 구체적 행동/결과 서술 권장")

    # 2-1. AI 번역투 '~이 아니라 ~' 과다 대조 구문 검사 (문항당 2회 이상 시 경고)
    contrast_pattern = r"([가-힣]+(?:이|가)\s*아니라|[가-힣]+(?:은|는)\s*아니었지만|[가-힣]+(?:이|가)\s*아닌)"
    contrast_matches = re.findall(contrast_pattern, body)
    if len(contrast_matches) >= 2:
        out['issues'].append(f"WARN AI 번역투 대조 구문 과다({len(contrast_matches)}회): {contrast_matches[:3]} — 인위적 대조 대신 긍정형 직설 문장 권장")

    # 3. 단순 키워드 나열 억제 (Keyword Stuffing Detection)
    keyword_stuffing_pattern = r"([가-힣A-Za-z0-9_#+]+,\s*){3,}[가-힣A-Za-z0-9_#+]+"
    km = re.search(keyword_stuffing_pattern, body)
    if km:
        out['issues'].append(f"WARN 단순 키워드 나열 감지: '{km.group(0)}' — 쉼표 나열 대신 유기적 인과관계 서술 권장")

    # 4. 치명적 오탈자 및 맞춤법 결함 검출 (Typo & Integrity Gate)
    COMMON_TYPO_PATTERNS = [
        (r'\b곳\b(?=\s*(?:고객|서버|데이터|자산))', '곳 ➔ 곧(부사) 오기'),
        (r'끕어올려', '끕어올려 ➔ 끌어올려 오기'),
        (r'가늘할', '가늘할 ➔ 가늠할 오기'),
        (r'옷기던', '옷기던 ➔ 옮기던 오기'),
        (r'옷겨본', '옷겨본 ➔ 옮겨본 오기'),
        (r'끋까지', '끋까지 ➔ 끝까지 오기'),
        (r'몯한', '몯한 ➔ 못한 오기')
    ]
    detected_typos = []
    for pat, desc in COMMON_TYPO_PATTERNS:
        if re.search(pat, body):
            detected_typos.append(desc)
    if detected_typos:
        out['info']['오탈자검출'] = f"{len(detected_typos)}건: {', '.join(detected_typos)}"
        for dt in detected_typos:
            out['issues'].append(f"WARN 치명적 오탈자 검출: '{dt}' — 문맥상 명백한 오기로 서류 검수 무결성 훼손")


    # 문장 길이 분포 및 리듬 검사
    ss = sentences(body)
    if ss:
        L = [len(s) for s in ss]
        out['info']['문장'] = f'{len(ss)}개, 평균 {sum(L)//len(L)}자, 최장 {max(L)}, 최단 {min(L)}'
        if max(L) > 120:
            out['issues'].append(f'WARN 최장 문장 {max(L)}자 — 끊는 편이 낫다')
        if len(set(l // 20 for l in L)) <= 1 and len(L) > 3:
            out['issues'].append('WARN 문장 길이가 균일 — 리듬 없음')

        # 5. 종결어미 다양성 분포 검사 (동일 종결어미 60% 이상 독점 시 경고)
        endings = []
        for s in ss:
            s_clean = s.strip()
            em = re.search(r'([가-힣]{2,4}[.!?]?)$', s_clean)
            if em:
                endings.append(em.group(1).rstrip('.!?'))
        if len(endings) >= 4:
            from collections import Counter
            counts = Counter(endings)
            top_ending, top_count = counts.most_common(1)[0]
            ratio = top_count / len(endings)
            if ratio >= 0.60:
                out['issues'].append(f"WARN 종결어미 획일화: '{top_ending}' 종결 {top_count}/{len(endings)}개({ratio:.0%}) — 리듬감 개선을 위해 어미 변주 권장")

    # N-gram 기반 상투적/중복 구문 탐지 (4-gram 2회 이상 또는 3-gram 3회 이상, 불용어 제외)
    rep_ngrams = check_repeated_ngrams(body, n=4, min_count=2)
    if not rep_ngrams:
        rep_ngrams = check_repeated_ngrams(body, n=3, min_count=3)
    if rep_ngrams:
        out['info']['중복어구(N-gram)'] = ', '.join(rep_ngrams)
        if len(rep_ngrams) >= 3:
            out['issues'].append(f'WARN 동일 N-gram 어구 {len(rep_ngrams)}건 반복 — 문장 단조로움 점검 권장')

    # 첫 본문 단락 비중 (소제목 제외 후 실제 상황 설명 측정, 500자 이하 면제)
    n_all = len(body)
    if n_all > 500 and real_paras:
        r = len(real_paras[0]) / n_all if n_all > 0 else 0
        out['info']['첫본문단락비중'] = f'{r:.0%} ({len(real_paras[0])}/{n_all}자)'
        threshold = 0.45 if q_nature in ['MOTIVATION', 'VALUES', 'VISION', 'COLLABORATION', 'MOTIVATION_ASPIRATION', 'CULTURE_COLLAB_SOFT'] else 0.35
        if r > threshold:
            out['issues'].append(f'WARN 첫 본문 단락이 {r:.0%} — 상황 설명 {int(threshold*100)}% 초과 가능 (배경 압축 권장)')
            
    return out

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("사용법: python3 lint.py <draft.txt> <spec.json>")
        sys.exit(1)
    draft = load(sys.argv[1])
    spec = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    banned = spec.get('banned', [])
    pn = spec.get('proper_nouns', [])
    blind_level = spec.get('blind_compliance_level', 'NONE')
    spec_questions = spec.get('questions', {})
    
    # 문항 분할 단언 계약 검사 (Hard Assertion Gate)
    if spec_questions and len(draft) != len(spec_questions):
        print(f"\n🚨 CRITICAL FAIL [Segmentation Mismatch]: 초안 파싱 문항 수({len(draft)})와 spec.json 문항 수({len(spec_questions)})가 불일치합니다. 구분자(===qid===)를 점검하십시오.")
        sys.exit(1)

    fails = 0
    total_typo_count = 0
    results = []
    for qid, body in draft.items():
        q_spec = spec_questions.get(qid, {})
        # 전역 length_metric_type 상속
        if 'length_metric_type' not in q_spec and 'length_metric_type' in spec:
            q_spec['length_metric_type'] = spec['length_metric_type']
            
        r = check(qid, body, q_spec, banned, pn, blind_level=blind_level)
        results.append(r)
        if '오탈자검출' in r['info']:
            count_str = r['info']['오탈자검출'].split('건')[0]
            try:
                total_typo_count += int(count_str)
            except Exception:
                pass

    for r in results:
        print(f"\n{'='*52}\n[문항 {r['문항']}]")
        for k, v in r['info'].items():
            print(f'  {k}: {v}' if not isinstance(v, list) else f'  {k}:\n' + ''.join(f'    - {x}\n' for x in v).rstrip())
        if r['issues']:
            for i in r['issues']:
                print(f'  {i}')
                fails += i.startswith('FAIL')
        else:
            print('  지적 없음')

    # 지원서 전역 마무리 종결어 반복 검사 (예: 전 문항 '기여하겠습니다' 반복 획일화 탐지)
    if len(draft) >= 3:
        closings = []
        for qid, body in draft.items():
            ss = sentences(body)
            if ss:
                last_s = ss[-1].strip()
                m = re.search(r'([가-힣]+(?:기여하겠습니다|이바지하겠습니다|노력하겠습니다|보탬이\s*되겠습니다))', last_s)
                if m:
                    closings.append((qid, m.group(0)))
        if len(closings) >= len(draft):
            print(f"\n⚠️ WARN [Closing Monotony]: 전체 {len(draft)}개 문항의 마무리가 모두 상투적 기여/노력 다짐({[c[1] for c in closings]})으로 획일화되었습니다. 문항별 구체적 완성/방어 목표로 변주를 권장합니다.")

    if total_typo_count >= 3:
        print(f"\n🚨 CRITICAL FAIL [Knockout Red Flag]: 지원서 전체에서 치명적 오탈자가 {total_typo_count}건 누적되었습니다. (3건 이상 방치 시 Step 5 사법 심판에서 자동 탈락/Hard Clamp 대상이 되므로 전수 교정 필수)")
        fails += 1

    print(f"\n{'='*52}\nFAIL {fails}건")
    sys.exit(1 if fails else 0)
