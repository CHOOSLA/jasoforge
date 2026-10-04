#!/usr/bin/env python3
"""자소서 기계 검사 (lint.py v3.4).
실제 공고에 명시된 분량·금지어를 검사하고, 표현 탐색 결과는 참고 정보로 제공한다.
표준 라이브러리만 사용합니다.
"""
import re, sys, json, unicodedata
from pathlib import Path
from evaluation_contract import ContractError, load_draft, read_json, validate_spec

def load(path):
    return load_draft(path)

def count(body):
    return len(body), len(re.sub(r'\s', '', body))

def count_metrics(body, metric_type="chars_with_space"):
    """
    지원하는 글자수/바이트 계량 규격:
    - chars_with_space: 공백 포함 글자수 (기본)
    - chars_without_space: 공백 제외 글자수
    - bytes_euckr: Python euc-kr 인코딩 바이트 수 (개행 CRLF)
    - legacy_nonascii_2byte: 비ASCII 2byte 시뮬레이션 (실제 ATS 규격 확인 필요)
    - bytes_utf8: UTF-8 바이트 (한글 3byte, 영수 1byte)
    """
    n_all = len(body)
    n_ns = len(re.sub(r'\s', '', body))
    crlf_body = body.replace('\r\n', '\n').replace('\n', '\r\n')
    
    # 1. 레거시 바이트 근사값. 기업명만으로 이 계량을 선택하지 않는다.
    b_ats = sum(2 if ord(c) > 127 else 1 for c in crlf_body)
    
    # 2. Strict EUC-KR 호환성 검사 (비호환 문자 검출)
    unsupported_chars = []
    b_euckr = None
    try:
        b_euckr = len(crlf_body.encode('euc-kr'))
    except UnicodeEncodeError:
        for ch in crlf_body:
            try:
                ch.encode('euc-kr')
            except UnicodeEncodeError:
                if ch not in unsupported_chars:
                    unsupported_chars.append(ch)
                    
    b_utf8 = len(crlf_body.encode('utf-8'))
    
    summary = f"공백포함 {n_all}자 / 공백제외 {n_ns}자 / EUC-KR {b_euckr if b_euckr is not None else '인코딩 불가'}B / UTF-8 {b_utf8}B"
    if unsupported_chars:
        summary += f" [⚠️ Strict EUC-KR 비호환 문자: {', '.join(unsupported_chars[:5])}]"
        
    if metric_type == "bytes_euckr":
        return b_euckr, summary, "EUC-KR Bytes", unsupported_chars
    elif metric_type == "legacy_nonascii_2byte":
        return b_ats, summary, "legacy 비ASCII 2바이트 근사 (ATS 검증 필요)", unsupported_chars
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
        out['issues'].append(f'FAIL EUC-KR 인코딩 불가 문자 ({len(unsupported_chars)}종: {unsupported_chars[:5]}): 지정 인코딩으로 계량할 수 없습니다.')
    
    lo, hi = spec.get('min'), spec.get('max')
    # 최소 분량은 실제 spec.min이 있을 때만 적용한다.
    if lo is not None and current_val is not None and current_val < lo:
        out['issues'].append(f'FAIL 글자수/용량 미달: {current_val} < {lo} ({unit_name})')
    if hi is not None and current_val is not None and current_val > hi:
        out['issues'].append(f'FAIL 글자수/용량 초과: {current_val} > {hi} ({unit_name})')

    # 키워드 미발견은 누락의 확증이 아니며 문맥을 검토한다.
    for item, kws in spec.get('required_items', {}).items():
        hits = [k for k in kws if k in body]
        if not hits:
            out['issues'].append(f'INFO 작성방법 항목 탐색어 미발견 (문맥 확인): "{item}" (탐색어 {kws})')
        else:
            out['info'].setdefault('탐색어발견(충족확정아님)', []).append(f'{item} ← {hits}')

    # 대안 비교가 실제 문항 요구라면 required_items에서 함께 확인한다.
    # 과거 discarded_alternative_keywords는 자동 문체·서사 조건으로 사용하지 않는다.

    # 블라인드 레벨 분기 적용
    effective_banned = list(banned)
    # Explicitly supplied prohibitions always apply, regardless of profile.
    if blind_level == "STRICT_PUBLIC_INSTITUTION":
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
    # N-gram 기반 상투적/중복 구문 탐지 (4-gram 2회 이상 또는 3-gram 3회 이상, 불용어 제외)
    rep_ngrams = check_repeated_ngrams(body, n=4, min_count=2)
    if not rep_ngrams:
        rep_ngrams = check_repeated_ngrams(body, n=3, min_count=3)
    if rep_ngrams:
        out['info']['중복어구(N-gram)'] = ', '.join(rep_ngrams)
        if len(rep_ngrams) >= 3:
            out['issues'].append(f'WARN 동일 N-gram 어구 {len(rep_ngrams)}건 반복 — 문장 단조로움 점검 권장')

    # 첫 단락 길이는 상황 설명의 의미나 필요한 비중을 판정하지 않는다.
    n_all = len(body)
    if real_paras and n_all:
        r = len(real_paras[0]) / n_all
        out['info']['첫본문단락비중'] = f'{r:.0%} ({len(real_paras[0])}/{n_all}자, 참고 정보)'

    return out

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("사용법: python3 lint.py <draft.txt> <spec.json>")
        sys.exit(1)
    try:
        draft = load(sys.argv[1])
        spec = read_json(sys.argv[2])
        validate_spec(spec, draft)
    except (ContractError, OSError, ValueError) as exc:
        print(f"FAIL 입력 규격: {exc}")
        sys.exit(1)
    banned = spec.get('banned', [])
    pn = spec.get('proper_nouns', [])
    blind_level = spec.get('blind_compliance_level', 'NONE')
    spec_questions = spec['questions']

    fails = 0
    total_typo_count = 0
    results = []
    for qid, body in draft.items():
        q_spec = dict(spec_questions[qid])
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
            print(f"\nℹ️ INFO [Closing Repetition]: 전체 {len(draft)}개 문항의 마무리가 모두 상투적 기여/노력 다짐({[c[1] for c in closings]})으로 반복됩니다. 문항에 필요한 결말인지 읽고 확인하십시오.")

    if total_typo_count >= 3:
        print(f"\nWARN 등록된 오탈자 유형 {total_typo_count}건 발견: 원문 문맥을 확인하고 교정하십시오. 채용 결격으로 판정하지 않습니다.")

    print(f"\n{'='*52}\nFAIL {fails}건")
    sys.exit(1 if fails else 0)
