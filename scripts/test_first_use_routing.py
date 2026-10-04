"""자료 없는 진입을 허용하면서 입력 읽기·오프라인·요청 범위를 보존한다."""
import unittest
from smart_router import SmartIngestionRouter


class FirstUseRoutingTests(unittest.TestCase):
    def test_conversation_can_start_without_a_document(self):
        for request in (
            '자소서 처음 써봐. 정리한 자료는 없고 경험부터 같이 찾아줘.',
            '아직 지원 회사는 못 정했고, 내가 해본 일부터 정리하고 싶어.',
        ):
            with self.subTest(request=request):
                result = SmartIngestionRouter.route_input(request, False)
                self.assertEqual(result['next_action'], 'CLASSIFY_REQUEST_AND_AVAILABLE_INPUTS')
                self.assertFalse(result['needs_user_question'])
                self.assertFalse(result['is_draft'])
                self.assertIsNone(result['file_path'])

    def test_no_materials_does_not_bypass_reading_a_supplied_job(self):
        result = SmartIngestionRouter.route_input(
            '자료나 초안은 없어. 이 공고로 처음부터 써줘. https://example.com/job', False)
        self.assertEqual(result['next_action'], 'READ_URL_AND_CLASSIFY')
        self.assertEqual(result['url'], 'https://example.com/job')

    def test_experience_language_inside_draft_does_not_start_an_interview(self):
        result = SmartIngestionRouter.route_input(
            '[문항 1] 경험을 같이 정리하자는 제안으로 회의를 시작했습니다. 이 초안 평가만 해줘.', False)
        self.assertEqual(result['next_action'], 'CLASSIFY_TEXT_AND_CONFIRM_SCOPE')

    def test_partial_edit_keeps_scope_with_host_instead_of_requesting_documents(self):
        result = SmartIngestionRouter.route_input('이 문장만 고쳐줘: 경험을 정리했습니다.', False)
        self.assertEqual(result['next_action'], 'CLASSIFY_REQUEST_AND_AVAILABLE_INPUTS')
        self.assertFalse(result['needs_user_question'])

    def test_offline_conversation_does_not_enable_network_or_notion(self):
        result = SmartIngestionRouter.route_input('--offline 경험부터 같이 정리해줘.', True)
        self.assertEqual(result['next_action'], 'CLASSIFY_REQUEST_AND_AVAILABLE_INPUTS')
        self.assertFalse(result['network_allowed'])
        self.assertEqual(result['mode'], 'LOCAL')

    def test_skill_maintenance_is_not_applicant_intake(self):
        result = SmartIngestionRouter.route_input('jaso-pipeline 스킬의 첫 사용자 경험 수집을 수정해줘.', False)
        self.assertEqual(result['next_action'], 'REVIEW_SKILL_WITHOUT_RUNNING_APPLICATION_PIPELINE')

    def test_experience_team_is_not_a_target_employer(self):
        for request in (
            '지원 회사는 아직 없어. 학생회 홍보팀에서 축제 안내문을 만든 경험부터 정리해줘.',
            '홍보팀에서 안내문을 만든 경험부터 정리해줘.',
            '--offline 홍보팀에서 안내문을 만든 경험부터 정리해줘.',
            '이 문장만 고쳐줘: 백엔드팀과 협업했습니다.',
        ):
            with self.subTest(request=request):
                result = SmartIngestionRouter.route_input(request, False)
                self.assertEqual(result['next_action'], 'CLASSIFY_REQUEST_AND_AVAILABLE_INPUTS')
                self.assertIsNone(result['candidate_team'])
                self.assertIsNone(result['search_query'])
                self.assertFalse(result['needs_identity_resolution'])

    def test_bare_team_call_still_resolves_target_with_offline_boundary(self):
        for request in ('이즐IS팀', '이즐IS팀 자소서 봐줘', '--offline 이즐IS팀 봐줘'):
            result = SmartIngestionRouter.route_input(request, False)
            self.assertEqual(result['candidate_team'], '이즐IS팀')
            expected = 'RESOLVE_IDENTITY_FROM_LOCAL_CONTEXT' if '--offline' in request else 'RESOLVE_ORGANIZATION_IDENTITY'
            self.assertEqual(result['next_action'], expected)

    def test_pipeline_experience_is_not_skill_maintenance(self):
        result = SmartIngestionRouter.route_input('이 문장만 고쳐줘: 배포 파이프라인을 개선했습니다.', False)
        self.assertEqual(result['next_action'], 'CLASSIFY_REQUEST_AND_AVAILABLE_INPUTS')


if __name__ == '__main__':
    unittest.main()
