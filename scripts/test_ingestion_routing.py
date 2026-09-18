#!/usr/bin/env python3
"""
JasoForge Ingestion & Routing Verification Suite (test_ingestion_routing.py)
=============================================================================
모든 사용자 진입 케이스(공고 링크, 자소서 본문, 기업명 호출, 범용 초안)에 대해
올바른 감지, 노션 선행 조회 분기, 선행 역질문 트리거가 완벽하게 동작하는지 기계적으로 검증합니다.
"""

import unittest
from smart_router import SmartIngestionRouter

class TestSmartIngestionRouter(unittest.TestCase):

    def test_case_1_url_input(self):
        """Case 1: 자소설닷컴 또는 공식 채용 링크 유입 시 URL 감지 및 파싱 라우팅 검증"""
        inputs = [
            "https://jasoseol.com/recruit/105432 이거 분석해줘",
            "공고 링크입니다: https://daou.recruiter.co.kr/app/jobnotice/view?systemKindCode=MRS2&jobnoticeSn=123",
            "https://toss.im/career/job-detail?job_id=456"
        ]
        for user_in in inputs:
            res = SmartIngestionRouter.route_input(user_in, has_notion_env=True)
            self.assertEqual(res["detected_case"], "CASE_1_URL", f"Failed for {user_in}")
            self.assertIsNotNone(res["url"])
            self.assertEqual(res["next_action"], "PARSE_JOB_POSTING_AND_DEEP_RESEARCH")

    def test_case_2_draft_with_company(self):
        """Case 2: 본문 내에 기업명이 포함된 초안 유입 시 기업명 자동 역파싱 및 Audit-First 직행 검증"""
        user_in = """
        [문항 1] 본인의 지원동기를 서술하시오.
        저는 다우기술의 금융/증권 IT 개발 직무에서 키움증권 원장과 고객채널을 직접 개발하고 끝까지 책임지는 엔지니어가 되고자 지원했습니다.
        화면 뒤의 보이지 않는 시스템이 무너지지 않도록 C++과 Java 네이티브 메모리 해제 로직을 구현했던 경험이 있습니다.
        대용량 트랜잭션 환경에서 데이터 무결성을 유지하는 원장 시스템의 안정성에 기여하겠습니다.
        """
        res = SmartIngestionRouter.route_input(user_in, has_notion_env=True)
        self.assertEqual(res["detected_case"], "CASE_2_DRAFT_WITH_COMPANY")
        self.assertEqual(res["company"], "다우기술")
        self.assertTrue(res["is_draft"])
        self.assertEqual(res["next_action"], "LOOKUP_NOTION_AND_AUDIT_FIRST")
        self.assertFalse(res["needs_user_question"])

    def test_case_3_draft_without_company(self):
        """Case 3: 기업명이 명시되지 않은 범용 기술 초안 유입 시 선행 타깃 확인 질문 트리거 검증"""
        user_in = """
        [문항 1] 문제 해결 경험을 기술하시오.
        학부 시절 MFC로 리스트 컨트롤 위에 직접 진행 막대를 그리는 프로그램을 개발했습니다.
        컨트롤이 셀 내부 컨트롤 삽입을 지원하지 않았기에 헤더의 사각형과 행의 사각형을 합성하여 렌더링 좌표를 직접 계산했습니다.
        원인을 끝까지 파고들어 문제를 해결하는 집요함을 배웠습니다.
        """
        res = SmartIngestionRouter.route_input(user_in, has_notion_env=True)
        self.assertEqual(res["detected_case"], "CASE_3_DRAFT_WITHOUT_COMPANY")
        self.assertIsNone(res["company"])
        self.assertTrue(res["is_draft"])
        self.assertEqual(res["next_action"], "ASK_TARGET_COMPANY_BEFORE_AUDIT")
        self.assertTrue(res["needs_user_question"], "Should prompt user for target company")
        self.assertIn("어느 기업 및 직무", res["question_prompt"])

    def test_case_4_company_call(self):
        """Case 4: 기업명이나 작업 지시어만 유입 시 노션 원장 조회 및 기존 초안 로드 라우팅 검증"""
        inputs = [
            "다우기술 자소서 봐줘",
            "키움증권 초안 평가해줘",
            "네이버 지원서 상태 확인해줘"
        ]
        expected_companies = ["다우기술", "키움증권", "네이버"]
        for user_in, exp_comp in zip(inputs, expected_companies):
            res = SmartIngestionRouter.route_input(user_in, has_notion_env=True)
            self.assertEqual(res["detected_case"], "CASE_4_COMPANY_CALL")
            self.assertEqual(res["company"], exp_comp)
            self.assertEqual(res["next_action"], "LOOKUP_NOTION_AND_LOAD_EXISTING_DRAFT")

    def test_fallback_short_query(self):
        """Case 5: 단순 인사나 불명확한 단문 질의 시 공고 링크 또는 초안 요청 유도 검증"""
        user_in = "자소서 작성 도와줘"
        res = SmartIngestionRouter.route_input(user_in, has_notion_env=False)
        self.assertEqual(res["detected_case"], "CASE_FALLBACK_QUERY")
        self.assertTrue(res["needs_user_question"])

    def test_case_file_draft_routing(self):
        """Case 6: PDF나 TXT 파일 경로 유입 시 CASE_FILE_DRAFT 인식 및 로컬 감사 직행 검증"""
        user_in = "/Users/choosla/Downloads/다우기술.pdf 이거 평가해봐"
        res = SmartIngestionRouter.route_input(user_in, has_notion_env=True)
        self.assertEqual(res["detected_case"], "CASE_FILE_DRAFT")
        self.assertEqual(res["file_path"], "/Users/choosla/Downloads/다우기술.pdf")
        self.assertEqual(res["company"], "다우기술")
        self.assertEqual(res["mode"], "LOCAL", "File path audit should default to LOCAL mode")
        self.assertEqual(res["next_action"], "LOCAL_AUDIT_FIRST", "Should bypass Notion and audit locally")

    def test_execution_mode_flags(self):
        """Case 7: --local 및 --sync-notion 플래그에 따른 결정론적 분기 검증"""
        # --local 강제 시 노션 환경이 있어도 LOCAL_AUDIT_FIRST 직행
        local_in = "[문항 1] 다우기술 지원동기 ... (200자 이상 본문) " + "테스트 " * 40 + " --local"
        res_local = SmartIngestionRouter.route_input(local_in, has_notion_env=True)
        self.assertEqual(res_local["mode"], "LOCAL")
        self.assertEqual(res_local["next_action"], "LOCAL_AUDIT_FIRST")

        # --sync-notion 강제 시 노션 조회 활성화
        sync_in = "/Users/choosla/Downloads/다우기술.pdf --sync-notion"
        res_sync = SmartIngestionRouter.route_input(sync_in, has_notion_env=True)
        self.assertEqual(res_sync["mode"], "NOTION_SYNC")
        self.assertEqual(res_sync["next_action"], "LOOKUP_NOTION_AND_AUDIT_FIRST")

    def test_case_notion_draft_url(self):
        """Case 8: 노션 페이지 링크(notion.so/...) 유입 시 CASE_NOTION_DRAFT_URL 인식 검증"""
        user_in = "https://www.notion.so/my-workspace/daou-draft-31bf58c3261e81d6aad0e3c2bdb637e3 다우기술 이거 평가해봐"
        res = SmartIngestionRouter.route_input(user_in, has_notion_env=True)
        self.assertEqual(res["detected_case"], "CASE_NOTION_DRAFT_URL")
        self.assertTrue(res["is_draft"])
        self.assertEqual(res["company"], "다우기술")
        self.assertEqual(res["next_action"], "READ_NOTION_PAGE_AND_AUDIT_FIRST")

    def test_case_draft_with_team_resolver(self):
        """Case 9: 모호한 팀명(이즐IS팀)이 포함된 초안 유입 시 3단계 점진적 리졸버 트리거 검증"""
        user_in = """
        [지원부서: 이즐IS팀]
        [문항 1] 지원동기 및 입사 후 포부를 기술하시오.
        이즐의 대중교통 및 결제 정산 플랫폼 시스템을 안정적으로 운영하고 장애를 사전에 방어하는 엔지니어가 되겠습니다.
        트래픽 폭주 상황에서도 데이터 정합성을 유지하기 위해 트랜잭션 격리 수준을 분석하고 쿼리 병목을 개선했던 경험이 있습니다.
        """
        res = SmartIngestionRouter.route_input(user_in, has_notion_env=True)
        self.assertEqual(res["detected_case"], "CASE_DRAFT_WITH_TEAM_RESOLVER")
        self.assertEqual(res["candidate_team"], "이즐IS팀")
        self.assertEqual(res["search_query"], "이즐IS팀 채용")
        self.assertTrue(res["needs_identity_resolution"])
        self.assertEqual(res["next_action"], "RESOLVE_ORGANIZATION_IDENTITY")
        self.assertTrue(res["needs_user_question"])
        self.assertIn("이즐IS팀", res["question_prompt"])

    def test_case_team_call_resolver(self):
        """Case 10: 팀명만 단독 호출("이즐IS팀 자소서 봐줘") 유입 시 리졸버 트리거 검증"""
        user_in = "이즐IS팀 자소서 봐줘"
        res = SmartIngestionRouter.route_input(user_in, has_notion_env=False)
        self.assertEqual(res["detected_case"], "CASE_TEAM_CALL_RESOLVER")
        self.assertEqual(res["candidate_team"], "이즐IS팀")
        self.assertEqual(res["search_query"], "이즐IS팀 채용")
        self.assertTrue(res["needs_identity_resolution"])
        self.assertEqual(res["next_action"], "RESOLVE_ORGANIZATION_IDENTITY")

    def test_generic_team_exclusion(self):
        """Case 11: 일반적인 협업 서술용 팀 단어(우리팀, 프로젝트팀)는 리졸버를 오발동하지 않음 검증"""
        user_in = """
        [문항 1] 협업 경험을 기술하시오.
        학부 시절 프로젝트팀에서 개발을 주도하며 우리팀의 일정 지연을 막기 위해 커스텀 린터를 도입했습니다.
        팀원들과의 적극적인 소통을 통해 정해진 기간 내에 배포를 완료했습니다.
        """
        res = SmartIngestionRouter.route_input(user_in, has_notion_env=True)
        # 우리팀, 프로젝트팀은 리졸버 트리거 대상이 아니므로 일반 무회사 초안(CASE_3)으로 분류되어야 함
        self.assertEqual(res["detected_case"], "CASE_3_DRAFT_WITHOUT_COMPANY")
        self.assertIsNone(res["candidate_team"])
        self.assertFalse(res["needs_identity_resolution"])

    def test_organization_contract_and_prompt_formatting(self):
        """Case 12: 조직 정체성 이원화 계약 생성 및 Tier 3 확인 프롬프트 포맷팅 무결성 검증"""
        # 1. 1회 대화형 확인 프롬프트 (검색으로 모회사-도메인 식별된 경우)
        prompt_identified = SmartIngestionRouter.format_confirmation_prompt(
            candidate_team="이즐IS팀",
            parent_company="롯데이노베이트",
            service_domain="이즐(교통/결제 서비스)",
            work_env="SM(운영)"
        )
        self.assertIn("이즐IS팀", prompt_identified)
        self.assertIn("롯데이노베이트", prompt_identified)
        self.assertIn("이즐(교통/결제 서비스)", prompt_identified)
        self.assertIn("SM(운영)", prompt_identified)

        # 2. 조직 정체성 이원화 계약 객체 생성
        contract = SmartIngestionRouter.create_organization_contract(
            declared_target="이즐IS팀",
            entity_pattern="SI_SM_OUTSOURCING",
            parent_legal_entity="롯데이노베이트",
            client_service_domain="이즐(교통/결제 서비스)"
        )
        self.assertEqual(contract["declared_target"], "이즐IS팀")
        self.assertEqual(contract["entity_pattern"], "SI_SM_OUTSOURCING")
        self.assertEqual(contract["parent_legal_entity"], "롯데이노베이트")
        self.assertEqual(contract["client_service_domain"], "이즐(교통/결제 서비스)")

if __name__ == "__main__":
    unittest.main(verbosity=2)
