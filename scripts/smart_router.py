#!/usr/bin/env python3
"""
JasoForge Smart Ingestion Router (smart_router.py)
==================================================
사용자의 다양한 첫 입력 형태(URL, 자소서 본문, 기업명 호출)를 결정론적으로 감지하고
자료의 위치를 식별하고 내용을 읽어 종류와 요청 범위를 확인할 다음 단계를 안내합니다.
분류 결과만으로 평가·작성·동기화를 시작하지 않습니다.
"""

import re
from typing import Dict, Any, Optional

class SmartIngestionRouter:
    # 1. 일반 웹 URL 패턴
    URL_PATTERN = re.compile(
        r'https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+',
        re.IGNORECASE
    )

    # 1-0. 노션 페이지 URL 패턴 (자소서 초안 페이지 직접 인입)
    NOTION_URL_PATTERN = re.compile(
        r'https?://(?:(?:www\.)?notion\.(?:so|site)|(?:app\.)?notion\.com)/[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+',
        re.IGNORECASE
    )

    # 1-1. 로컬 파일 경로 패턴 (.pdf, .txt, .md, .docx, .json 등)
    FILE_PATH_PATTERN = re.compile(
        r'(?:^|\s)(/[^\s]+?\.(?:pdf|txt|md|docx|json)|\./[^\s]+?\.(?:pdf|txt|md|docx|json)|~/[^\s]+?\.(?:pdf|txt|md|docx|json))',
        re.IGNORECASE
    )

    # 2. 알려진 주요 IT/테크/금융 기업 패턴
    KNOWN_COMPANIES = [
        "다우기술", "키움증권", "네이버", "카카오", "라인", "쿠팡", "배달의민족", "우아한형제들",
        "토스", "비바리퍼블리카", "당근", "당근마켓", "삼성전자", "SK하이닉스", "현대자동차",
        "LG전자", "카카오뱅크", "카카오페이", "토스뱅크", "토스증권", "신한은행", "KB국민은행",
        "하나은행", "우리은행", "NH농협은행", "엔씨소프트", "넥슨", "넷마블", "크래프톤", "야놀자"
    ]

    # 2-1. 특정 부서/팀/파트 패턴 (단문 호출용: "이즐IS팀 봐줘", "코어플랫폼파트")
    TEAM_PATTERN = re.compile(
        r'([가-힣A-Za-z0-9\-_]{2,20}(?:팀|파트|본부|실|센터|그룹))',
        re.IGNORECASE
    )
    TEAM_CALL_PATTERN = re.compile(
        TEAM_PATTERN.pattern
        + r'(?:\s+(?:자소서|지원서|채용|공고))?'
        + r'(?:\s+(?:봐줘|봐주세요|평가해줘|분석해줘|알려줘))?[.!?]?',
        re.IGNORECASE
    )

    # 2-2. 명시적 지원 대상 헤더 패턴 (초안 상단 메타데이터: "[지원부서: 이즐IS팀]", "지원팀: ...", "희망부서: ...")
    EXPLICIT_HEADER_TEAM_PATTERN = re.compile(
        r'(?:\[?(?:지원\s*(?:기업|회사|부서|팀|직무)|희망\s*(?:부서|팀|직무)|목표\s*(?:부서|팀))\s*[:：\-]\s*([가-힣A-Za-z0-9\-_]{2,20}(?:팀|파트|본부|실|센터|그룹))\]?)',
        re.IGNORECASE
    )

    # 3. 자소서 문항 구조 패턴
    DRAFT_HEADER_PATTERN = re.compile(
        r'(===.+?===|\[문항\s*\d+\]|문항\s*\d+[\.:]|Q\d+[\.:]|\b질문\s*\d+)',
        re.IGNORECASE
    )

    # 4. 실행 모드 제어 플래그
    LOCAL_FLAGS = ["--local", "-l", "--quick", "--offline", "로컬", "로컬모드", "노션없이", "오프라인"]
    OFFLINE_FLAGS = ["--offline", "오프라인"]
    NOTION_FLAGS = ["--sync-notion", "-s", "--notion", "노션동기화", "노션연동", "노션에저장"]

    @classmethod
    def format_confirmation_prompt(
        cls,
        candidate_team: str,
        parent_company: Optional[str] = None,
        service_domain: Optional[str] = None,
        work_env: str = "확인된 담당 업무"
    ) -> str:
        """3단계 점진적 조직 정체성 확인 질문 프로토콜 (Tier 3) 포맷팅"""
        if parent_company and service_domain:
            return (
                f"🔍 탐색 결과, **[{candidate_team}]**은 **'{parent_company}'** 소속의 "
                f"[{service_domain}] 관련 포지션으로 파악됩니다.\n"
                f"👉 **'{parent_company}'**의 [{work_env}] 직무 지원서가 맞으신가요?\n"
                f"*(맞다면 그대로 진행하며, 다른 법인/직무라면 실제 지원 대상을 알려주세요.)*"
            )
        elif parent_company:
            return (
                f"🔍 탐색 결과, **[{candidate_team}]**은 **'{parent_company}'** 관련 조직으로 파악됩니다.\n"
                f"👉 **'{parent_company}'** 지원서가 맞으신가요?\n"
                f"*(맞다면 구체적인 담당 업무나 서비스 도메인을, 다르다면 실제 지원 대상을 알려주세요.)*"
            )
        else:
            return (
                f"🔍 **[{candidate_team}]**의 공식 채용 법인을 명확히 확인하기 어렵습니다.\n"
                f"👉 해당 지원서의 **채용 법인(회사명)**과 **구체적인 담당 직무(운영/개발 등)**를 알려주시면 "
                f"문항과 경험의 관련성을 확인하겠습니다."
            )

    @classmethod
    def create_organization_contract(
        cls,
        declared_target: str,
        entity_pattern: str,
        parent_legal_entity: str,
        client_service_domain: str
    ) -> Dict[str, str]:
        """조직 정체성 이원화 계약 객체 생성"""
        return {
            "declared_target": declared_target,
            "entity_pattern": entity_pattern,
            "parent_legal_entity": parent_legal_entity,
            "client_service_domain": client_service_domain
        }

    @classmethod
    def route_input(cls, user_input: str, has_notion_env: bool = False) -> Dict[str, Any]:
        """
        사용자 입력 문자열을 분석하여 실행 모드, 진입 케이스 및 다음 조치를 반환합니다.
        """
        text = user_input.strip()

        # 모드 판별 (--local vs --sync-notion vs AUTO)
        is_local_flag = any(re.search(r"(?<!\S)" + re.escape(flag) + r"(?!\S)", text) for flag in cls.LOCAL_FLAGS)
        is_offline_flag = any(re.search(r"(?<!\S)" + re.escape(flag) + r"(?!\S)", text) for flag in cls.OFFLINE_FLAGS)
        is_notion_flag = any(re.search(r"(?<!\S)" + re.escape(flag) + r"(?!\S)", text) for flag in cls.NOTION_FLAGS)
        if is_local_flag:
            mode = "LOCAL"
        elif is_notion_flag:
            mode = "NOTION_SYNC"
        else:
            mode = "AUTO"

        result = {
            "raw_input": text,
            "has_notion_env": has_notion_env,
            "network_allowed": not is_offline_flag,
            "content_classified": False,
            "mode": mode,
            "detected_case": None,
            "company": None,
            "candidate_team": None,
            "search_query": None,
            "file_path": None,
            "url": None,
            "is_draft": False,
            "next_action": None,
            "needs_user_question": False,
            "needs_identity_resolution": False,
            "question_prompt": None
        }

        # 스킬 유지보수 요청은 지원서 작성·채점·동기화 실행 요청이 아니다.
        maintenance_target = re.search(
            r'(?:jaso[-_]pipeline|jasoforge)(?=\s|[을를의]|$)|(?:이|해당)\s*스킬|^스킬', text, re.I)
        target_suffix = text[maintenance_target.end():] if maintenance_target else ''
        invoked_for_work = re.match(
            r'\s*(?:스킬|파이프라인)?\s*(?:(?:로|으로)(?:\s|$)|(?:을|를)?\s*(?:사용|활용))',
            target_suffix)
        if maintenance_target and not invoked_for_work and re.search(
                r'(?:검증|수정|다듬|개선|검토|고쳐|점검)', target_suffix[:80]):
            result["detected_case"] = "CASE_SKILL_MAINTENANCE"
            result["next_action"] = "REVIEW_SKILL_WITHOUT_RUNNING_APPLICATION_PIPELINE"
            return result

        # Case 1-0: 노션 페이지 URL이 직접 인입된 경우 (Notion Draft Audit-First)
        notion_match = cls.NOTION_URL_PATTERN.search(text)
        if notion_match:
            notion_url = notion_match.group(0)
            result["detected_case"] = "CASE_NOTION_PAGE_URL"
            result["url"] = notion_url
            result["is_draft"] = False  # 페이지 본문을 읽기 전 초안/컨설팅 자료로 단정하지 않는다.
            for comp in sorted(cls.KNOWN_COMPANIES, key=len, reverse=True):
                if comp in text:
                    result["company"] = comp
                    break
            if mode == "LOCAL":
                result["next_action"] = "LOCAL_NEEDS_PAGE_EXPORT"
                result["needs_user_question"] = True
                result["question_prompt"] = "로컬 전용 모드에서는 Notion을 읽지 않습니다. 로컬로 제공된 내용을 사용하십시오."
            else:
                result["next_action"] = "READ_NOTION_PAGE_AND_CLASSIFY"
            return result

        # URL은 공고·가이드·초안 어느 것도 될 수 있으므로 읽고 분류한다.
        url_match = cls.URL_PATTERN.search(text)
        if url_match:
            result["detected_case"] = "CASE_1_URL"
            result["url"] = url_match.group(0)
            if is_offline_flag:
                result["next_action"] = "LOCAL_NEEDS_SOURCE_TEXT"
                result["needs_user_question"] = True
                result["question_prompt"] = "오프라인 모드에서는 URL을 열지 않습니다. 제공된 로컬 자료를 사용하고 없는 원문은 미확인으로 남기십시오."
            else:
                result["next_action"] = "READ_URL_AND_CLASSIFY"
            return result

        # 로컬 파일은 경로만으로 초안이라 판정하지 않는다.
        file_match = cls.FILE_PATH_PATTERN.search(text)
        if file_match:
            file_path = file_match.group(1).strip()
            result["detected_case"] = "CASE_LOCAL_FILE"
            result["file_path"] = file_path
            result["is_draft"] = False

            # 파일명이나 본문에서 기업명 식별 시도
            for comp in sorted(cls.KNOWN_COMPANIES, key=len, reverse=True):
                if comp in text:
                    result["company"] = comp
                    break

            if mode != "NOTION_SYNC":
                result["mode"] = "LOCAL"
            result["next_action"] = "READ_LOCAL_FILE_AND_CLASSIFY"
            return result

        # Case 2/3: 자소서 본문 텍스트가 들어온 경우 (문항 구조 패턴 또는 긴 글)
        is_structured_draft = bool(cls.DRAFT_HEADER_PATTERN.search(text))
        is_long_text = len(text) >= 200

        if is_structured_draft or is_long_text:
            result["is_draft"] = False  # 문항 머리말·길이는 분류 힌트이지 초안 확정이 아니다.
            # 본문 속에서 기업명 역파싱 시도
            matched_company = None
            for comp in sorted(cls.KNOWN_COMPANIES, key=len, reverse=True):
                if comp in text:
                    matched_company = comp
                    break

            if matched_company:
                result["detected_case"] = "CASE_2_DRAFT_WITH_COMPANY"
                result["company"] = matched_company
                result["next_action"] = "CLASSIFY_TEXT_AND_CONFIRM_SCOPE"
            else:
                # 3단계 점진적 리졸버: 초안 상단의 명시적 헤더([지원부서: XX팀])만 검사
                # (서사 본문 속 협업 팀명인 QA팀, 백엔드팀 등의 오탐/환각 원천 차단)
                header_match = cls.EXPLICIT_HEADER_TEAM_PATTERN.search(text)
                if header_match:
                    candidate_team = header_match.group(1)
                    result["detected_case"] = "CASE_DRAFT_WITH_TEAM_RESOLVER"
                    result["candidate_team"] = candidate_team
                    result["search_query"] = None
                    result["next_action"] = "CLASSIFY_TEXT_AND_CONFIRM_SCOPE"
                    result["needs_identity_resolution"] = True
                    result["needs_user_question"] = False
                    result["question_prompt"] = cls.format_confirmation_prompt(candidate_team=candidate_team)
                else:
                    result["detected_case"] = "CASE_3_DRAFT_WITHOUT_COMPANY"
                    result["next_action"] = "CLASSIFY_TEXT_AND_CONFIRM_SCOPE"
                    result["needs_user_question"] = False
                    result["question_prompt"] = "제공된 내용이 초안·작성 가이드·경험 기록 중 무엇인지와 현재 요청을 먼저 확인하십시오. 지원 대상은 작업에 필요할 때 기존 문맥에서 확인하고 없는 정보만 물으십시오."
            return result

        # Case 4: 회사명이나 지시어 호출형 ("다우기술 자소서 봐줘", "키움증권 평가해줘")
        for comp in sorted(cls.KNOWN_COMPANIES, key=len, reverse=True):
            # '파이프라인' 안의 '라인'처럼 일반 단어의 일부를 회사명으로 잡지 않는다.
            if re.search(r'(?<![가-힣A-Za-z0-9])' + re.escape(comp), text):
                result["detected_case"] = "CASE_4_COMPANY_CALL"
                result["company"] = comp
                if mode != "NOTION_SYNC" or not has_notion_env:
                    result["next_action"] = "LOAD_LOCAL_MATERIALS_AND_CONFIRM_SCOPE"
                else:
                    result["next_action"] = "READ_NOTION_MATERIALS_AND_CONFIRM_SCOPE"
                return result

        # Case 4-1: 모호한 팀명 단문 호출형 ("이즐IS팀 봐줘", "코어플랫폼팀 평가해줘", "이즐IS팀")
        # 팀명 중심의 단독 호출에만 적용한다. 경험·수정할 문장 속 팀은 지원 대상이 아니다.
        if len(text) <= 100:
            call_text = text
            for flag in cls.LOCAL_FLAGS + cls.NOTION_FLAGS:
                call_text = re.sub(r'(?<!\S)' + re.escape(flag) + r'(?!\S)', '', call_text)
            team_match = cls.TEAM_CALL_PATTERN.fullmatch(call_text.strip())
            if team_match:
                candidate_team = team_match.group(1)
                result["detected_case"] = "CASE_TEAM_CALL_RESOLVER"
                result["candidate_team"] = candidate_team
                if is_offline_flag:
                    result["search_query"] = None
                    result["next_action"] = "RESOLVE_IDENTITY_FROM_LOCAL_CONTEXT"
                else:
                    result["search_query"] = f"{candidate_team} 채용"
                    result["next_action"] = "RESOLVE_ORGANIZATION_IDENTITY"
                result["needs_identity_resolution"] = True
                result["needs_user_question"] = True
                result["question_prompt"] = cls.format_confirmation_prompt(candidate_team=candidate_team)
                return result

        # 자료가 없는 요청도 정상 진입이다. 작업 범위는 호스트가 대화에서 판단한다.
        result["detected_case"] = "CASE_FALLBACK_QUERY"
        result["next_action"] = "CLASSIFY_REQUEST_AND_AVAILABLE_INPUTS"
        result["needs_user_question"] = False
        result["question_prompt"] = (
            "현재 요청과 기존 대화에서 작업 범위와 가진 자료를 파악하십시오. "
            "명확한 요청을 다시 확인받지 말고, 자료 없는 신규 작성·경험 정리는 대화로 시작하십시오. "
            "기존 초안 평가·부분 수정에는 필요한 입력만 확인하며, 불명확한 경우에만 질문하십시오."
        )
        return result
