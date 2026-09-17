#!/usr/bin/env python3
"""자소서 기계 검사 (lint.py v2.2).
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
    - bytes_euckr: 국내 대기업(삼성, 현대차 등) ATS 표준 (한글 2byte, 영수공백 1byte, 개행 \r\n 2byte)
    - bytes_utf8: UTF-8 바이트 (한글 3byte, 영수 1byte)
    """
    n_all = len(body)
    n_ns = len(re.sub(r'\s', '', body))
    crlf_body = body.replace('\r\n', '\n').replace('\n', '\r\n')
    try:
        b_euckr = len(crlf_body.encode('euc-kr'))
    except UnicodeEncodeError:
        b_euckr = len(crlf_body.encode('cp949', errors='replace'))
    b_utf8 = len(crlf_body.encode('utf-8'))
    
    summary = f"공백포함 {n_all}자 / 공백제외 {n_ns}자 / EUC-KR {b_euckr}B / UTF-8 {b_utf8}B"
    if metric_type == "bytes_euckr":
        return b_euckr, summary, "EUC-KR Bytes"
    elif metric_type == "bytes_utf8":
        return b_utf8, summary, "UTF-8 Bytes"
    elif metric_type == "chars_without_space":
        return n_ns, summary, "공백제외 글자수"
    else:
        return n_all, summary, "공백포함 글자수"

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

def check_repeated_ngrams(body, n=3):
    """연속된 3단어 이상의 동일 구문/클리셰 반복 사용 탐지 (N-gram)"""
    clean = re.sub(r'[\.\,\!\?\'\"…\(\)\[\]\{\}\<\>\~\`\:\;\-\_]', ' ', body)
    tokens = [t for t in clean.split() if len(t) > 0]
    if len(tokens) < n:
        return []
    ngrams = [' '.join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]
    counts = {}
    for ng in ngrams:
        counts[ng] = counts.get(ng, 0) + 1
    repeated = [f'"{ng}"({c}회)' for ng, c in counts.items() if c >= 2]
    return repeated[:4]

STRICT_PUBLIC_PATTERNS = [
    (r"(부친|모친|아버지|어머니|삼촌|외삼촌|부모님|조부|조모|형제|자매|가족관계)", "공기업 블라인드 금지어: 가족/친인척 신원"),
    (r"(육군|해군|공군|해병대|의경|공익|상근|현역|병장|하사|장교|복무부대|\b\d+사단\b)", "공기업 블라인드 금지어: 병역/군부대 세부정보"),
    (r"(\d{2}학번|\d{4}년생|\d{2}년생|\b\d{2}세\b)", "공기업 블라인드 금지어: 연령/학번 신원"),
    (r"(남성|여성|남학생|여학생)", "공기업 블라인드 금지어: 성별 직접 표기"),
    (r"(출신\s*지역|고향은|태어난\s*곳)", "공기업 블라인드 금지어: 출신 지역")
]

def check(qid, body, spec, banned, proper_nouns, blind_level="NONE"):
    out = {'문항': qid, 'issues': [], 'info': {}}
    metric_type = spec.get('length_metric_type', spec.get('basis', 'chars_with_space'))
    if metric_type == 'with_spaces':
        metric_type = 'chars_with_space'
    elif metric_type == 'without_spaces':
        metric_type = 'chars_without_space'

    current_val, summary, unit_name = count_metrics(body, metric_type)
    out['info']['계량규격'] = f"{unit_name} 기준 ({summary})"
    
    lo, hi = spec.get('min'), spec.get('max')
    if lo and current_val < lo:
        out['issues'].append(f'FAIL 글자수/용량 미달: {current_val} < {lo} ({unit_name})')
    if hi and current_val > hi:
        out['issues'].append(f'FAIL 글자수/용량 초과: {current_val} > {hi} ({unit_name})')

    # 작성방법 항목 커버리지 — 키워드 0건이면 확실한 누락 신호
    for item, kws in spec.get('required_items', {}).items():
        hits = [k for k in kws if k in body]
        if not hits:
            out['issues'].append(f'WARN 작성방법 항목 근거 없음: "{item}" (탐색어 {kws})')
        else:
            out['info'].setdefault('항목충족', []).append(f'{item} ← {hits}')

    # 버린 대안(트레이드오프) 키워드 출현 게이트
    discarded_kws = spec.get('discarded_alternative_keywords', [])
    if discarded_kws:
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

    # 3. 단순 키워드 나열 억제 (Keyword Stuffing Detection)
    keyword_stuffing_pattern = r"([가-힣A-Za-z0-9_#+]+,\s*){3,}[가-힣A-Za-z0-9_#+]+"
    km = re.search(keyword_stuffing_pattern, body)
    if km:
        out['issues'].append(f"WARN 단순 키워드 나열 감지: '{km.group(0)}' — 쉼표 나열 대신 유기적 인과관계 서술 권장")

    # 문장 길이 분포 및 리듬 검사
    ss = sentences(body)
    if ss:
        L = [len(s) for s in ss]
        out['info']['문장'] = f'{len(ss)}개, 평균 {sum(L)//len(L)}자, 최장 {max(L)}, 최단 {min(L)}'
        if max(L) > 120:
            out['issues'].append(f'WARN 최장 문장 {max(L)}자 — 끊는 편이 낫다')
        if len(set(l // 20 for l in L)) <= 1 and len(L) > 3:
            out['issues'].append('WARN 문장 길이가 균일 — 리듬 없음')

    # N-gram 기반 상투적/중복 구문 탐지
    rep_ngrams = check_repeated_ngrams(body, n=3)
    if rep_ngrams:
        out['info']['중복어구(3-gram)'] = ', '.join(rep_ngrams)
        if len(rep_ngrams) >= 3:
            out['issues'].append(f'WARN 동일 3-gram 어구 {len(rep_ngrams)}건 반복 — 문장 단조로움 점검 권장')

    # 첫 본문 단락 비중 (소제목 제외 후 실제 상황 설명 30% 룰 측정)
    if real_paras:
        r = len(real_paras[0]) / n_all if n_all > 0 else 0
        out['info']['첫본문단락비중'] = f'{r:.0%} ({len(real_paras[0])}/{n_all}자)'
        if r > 0.35:
            out['issues'].append(f'WARN 첫 본문 단락이 {r:.0%} — 상황 설명 30% 초과 가능 (배경 압축 권장)')
            
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
    
    # 문항 분할 단언 계약 검사
    if spec_questions and len(draft) != len(spec_questions):
        print(f"\n⚠️ WARN [Segmentation Mismatch]: 초안 파싱 문항 수({len(draft)})와 spec.json 문항 수({len(spec_questions)})가 불일치합니다. 구분자(===qid===)를 점검하십시오.")

    fails = 0
    for qid, body in draft.items():
        q_spec = spec_questions.get(qid, {})
        # 전역 length_metric_type 상속
        if 'length_metric_type' not in q_spec and 'length_metric_type' in spec:
            q_spec['length_metric_type'] = spec['length_metric_type']
            
        r = check(qid, body, q_spec, banned, pn, blind_level=blind_level)
        print(f"\n{'='*52}\n[문항 {r['문항']}]")
        for k, v in r['info'].items():
            print(f'  {k}: {v}' if not isinstance(v, list) else f'  {k}:\n' + ''.join(f'    - {x}\n' for x in v).rstrip())
        if r['issues']:
            for i in r['issues']:
                print(f'  {i}')
                fails += i.startswith('FAIL')
        else:
            print('  지적 없음')
    print(f"\n{'='*52}\nFAIL {fails}건")
    sys.exit(1 if fails else 0)
