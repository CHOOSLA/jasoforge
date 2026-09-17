#!/usr/bin/env python3
"""
JasoForge Smart Ingestion Router (smart_router.py)
==================================================
사용자의 다양한 첫 입력 형태(URL, 자소서 본문, 기업명 호출)를 결정론적으로 감지하고
최적의 파이프라인 경로(Audit-First vs From-Scratch, 노션 조회 여부)를 결정합니다.
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
        r'https?://(?:www\.)?notion\.(?:so|site)/[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+',
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

    # 3. 자소서 문항 구조 패턴
    DRAFT_HEADER_PATTERN = re.compile(
        r'(===.+?===|\[문항\s*\d+\]|문항\s*\d+[\.:]|Q\d+[\.:]|\b질문\s*\d+)',
        re.IGNORECASE
    )

    # 4. 실행 모드 제어 플래그
    LOCAL_FLAGS = ["--local", "-l", "--quick", "--offline", "로컬", "로컬모드", "노션없이", "오프라인"]
    NOTION_FLAGS = ["--sync-notion", "-s", "--notion", "노션동기화", "노션연동", "노션에저장"]

    @classmethod
    def route_input(cls, user_input: str, has_notion_env: bool = False) -> Dict[str, Any]:
        """
        사용자 입력 문자열을 분석하여 실행 모드, 진입 케이스 및 다음 조치를 반환합니다.
        """
        text = user_input.strip()

        # 모드 판별 (--local vs --sync-notion vs AUTO)
        is_local_flag = any(flag in text for flag in cls.LOCAL_FLAGS)
        is_notion_flag = any(flag in text for flag in cls.NOTION_FLAGS)
        if is_local_flag:
            mode = "LOCAL"
        elif is_notion_flag:
            mode = "NOTION_SYNC"
        else:
            mode = "AUTO"

        result = {
            "raw_input": text,
            "has_notion_env": has_notion_env,
            "mode": mode,
            "detected_case": None,
            "company": None,
            "file_path": None,
            "url": None,
            "is_draft": False,
            "next_action": None,
            "needs_user_question": False,
            "question_prompt": None
        }

        # Case 1-0: 노션 페이지 URL이 직접 인입된 경우 (Notion Draft Audit-First)
        notion_match = cls.NOTION_URL_PATTERN.search(text)
        if notion_match:
            notion_url = notion_match.group(0)
            result["detected_case"] = "CASE_NOTION_DRAFT_URL"
            result["url"] = notion_url
            result["is_draft"] = True
            for comp in cls.KNOWN_COMPANIES:
                if comp in text:
                    result["company"] = comp
                    break
            result["next_action"] = "READ_NOTION_PAGE_AND_AUDIT_FIRST"
            return result

        # Case 1: 일반 채용 공고 URL이 포함되어 있는 경우
        url_match = cls.URL_PATTERN.search(text)
        if url_match:
            result["detected_case"] = "CASE_1_URL"
            result["url"] = url_match.group(0)
            result["next_action"] = "PARSE_JOB_POSTING_AND_DEEP_RESEARCH"
            return result

        # Case 1-1: 로컬 파일 경로(.pdf, .txt, .md 등)가 직접 인입된 경우 (Audit-First 직행)
        file_match = cls.FILE_PATH_PATTERN.search(text)
        if file_match:
            file_path = file_match.group(1).strip()
            result["detected_case"] = "CASE_FILE_DRAFT"
            result["file_path"] = file_path
            result["is_draft"] = True

            # 파일명이나 본문에서 기업명 식별 시도
            for comp in cls.KNOWN_COMPANIES:
                if comp in text:
                    result["company"] = comp
                    break

            # 파일 입력 시 기본 정책: --sync-notion이 명시되지 않으면 Zero Notion 로컬 감사 직행
            if mode == "NOTION_SYNC":
                result["next_action"] = "LOOKUP_NOTION_AND_AUDIT_FIRST"
            else:
                result["mode"] = "LOCAL"
                result["next_action"] = "LOCAL_AUDIT_FIRST"
            return result

        # Case 2/3: 자소서 본문 텍스트가 들어온 경우 (문항 구조 패턴 또는 긴 글)
        is_structured_draft = bool(cls.DRAFT_HEADER_PATTERN.search(text))
        is_long_text = len(text) >= 200

        if is_structured_draft or is_long_text:
            result["is_draft"] = True
            # 본문 속에서 기업명 역파싱 시도
            matched_company = None
            for comp in cls.KNOWN_COMPANIES:
                if comp in text:
                    matched_company = comp
                    break

            if matched_company:
                result["detected_case"] = "CASE_2_DRAFT_WITH_COMPANY"
                result["company"] = matched_company
                if mode == "LOCAL" or not has_notion_env:
                    result["next_action"] = "LOCAL_AUDIT_FIRST"
                else:
                    result["next_action"] = "LOOKUP_NOTION_AND_AUDIT_FIRST"
            else:
                result["detected_case"] = "CASE_3_DRAFT_WITHOUT_COMPANY"
                result["next_action"] = "ASK_TARGET_COMPANY_BEFORE_AUDIT"
                result["needs_user_question"] = True
                result["question_prompt"] = "초안을 확인했습니다. 어느 기업 및 직무(부서)를 목표로 작성하셨나요? (공고 링크나 기업명을 알려주시면 현업 테크 리드의 부서 엣지케이스 D축까지 날카롭게 채점해 드립니다)"
            return result

        # Case 4: 회사명이나 지시어 호출형 ("다우기술 자소서 봐줘", "키움증권 평가해줘")
        for comp in cls.KNOWN_COMPANIES:
            if comp in text:
                result["detected_case"] = "CASE_4_COMPANY_CALL"
                result["company"] = comp
                if mode == "LOCAL" or not has_notion_env:
                    result["next_action"] = "LOAD_LOCAL_DRAFT"
                else:
                    result["next_action"] = "LOOKUP_NOTION_AND_LOAD_EXISTING_DRAFT"
                return result

        # 매칭되지 않는 짧은 일반 질문
        result["detected_case"] = "CASE_FALLBACK_QUERY"
        result["next_action"] = "PROMPT_USER_FOR_URL_OR_DRAFT"
        result["needs_user_question"] = True
        result["question_prompt"] = "채용 공고 링크(자소설닷컴/공식 ATS)를 보내주시거나, 평가받으실 자소서 초안을 입력해 주세요."
        return result
