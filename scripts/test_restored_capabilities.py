"""Behavioral checks for restored capabilities; synthetic reviews are not model calls."""
import copy
import json
import unittest
from datetime import datetime, timezone

import test_evaluation_integrity as fixtures
from grade import summarize_review, review_age_notice
from run_pipeline import seniority_directive, SENIORITY_RUBRIC_MATRIX


class RestoredCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.EvaluationIntegrityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def interview(self):
        return {'questions': [{'topic': 'technical', 'question': '중복 판단 조건은 무엇인가요?',
                'intent': '구분 기준 확인', 'anchor_quote': '중복 요청을 구분하여 처리했습니다.',
                'answer_scope': '원고는 중복 구분 사실만 담고 있어 구현 조건은 미확인이다.',
                'facts_to_confirm': ['실제 구분 기준']}], 'omission_reason': ''}

    def test_track_selection_reaches_each_packet_and_handles_unknown(self):
        f = self.f
        for n, track in enumerate(['CONVERTIBLE_INTERN', 'NEW_GRAD', 'EXPERIENCED', '신입', '미공개']):
            with self.subTest(track=track):
                f.context.write_text(json.dumps({'recruitment_track_type': track}), encoding='utf-8')
                f.packets = f.base / ('track-' + str(n))
                self.assertEqual(f.generate().returncode, 0)
                directive = seniority_directive({'recruitment_track_type': track})
                for role in ('hr', 'tech'):
                    self.assertIn(directive, (f.packets / (role + '_prompt_packet.txt')).read_text(encoding='utf-8'))
        self.assertEqual(seniority_directive({'recruitment_track_type': '신입'}), seniority_directive({'recruitment_track_type': 'NEW_GRAD'}))
        self.assertNotEqual(seniority_directive({'recruitment_track_type': '미공개'}), seniority_directive({'recruitment_track_type': 'EXPERIENCED'}))

    def test_tech_questions_survive_validation_json_and_report(self):
        f = self.f
        q = f.tech['questions']['1']['interview'] = self.interview()
        output = f.base / 'summary.json'
        run = f.grade(None, None, '--out-json', output)
        self.assertEqual(run.returncode, 0, run.stdout)
        data = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(data['questions']['1']['interview'], q)
        self.assertIn(q['questions'][0]['question'], run.stdout)
        self.assertIn(q['questions'][0]['answer_scope'], run.stdout)
        self.assertEqual(data['role_means'], {'HR': 100.0, 'TECH': 100.0})

    def test_missing_interview_empty_reason_and_false_anchor_are_rejected(self):
        f = self.f
        for variant in ('missing', 'empty', 'false_quote'):
            tech = copy.deepcopy(f.tech)
            if variant == 'missing':
                del tech['questions']['1']['interview']
            elif variant == 'empty':
                tech['questions']['1']['interview'] = {'questions': [], 'omission_reason': ''}
            else:
                tech['questions']['1']['interview'] = self.interview()
                tech['questions']['1']['interview']['questions'][0]['anchor_quote'] = '없는 과거 행동'
            run = f.grade(tech=tech)
            self.assertEqual(run.returncode, 2, run.stdout)
            self.assertIn('NOT_EVALUABLE', run.stdout)

    def test_na_role_is_excluded_from_question_denominator_and_role_mean(self):
        f = self.f
        spec = copy.deepcopy(f.spec)
        spec['questions']['1']['applicable_axes'] = ['A', 'B']
        spec['questions']['2'] = copy.deepcopy(spec['questions']['1'])
        spec['questions']['2']['applicable_axes'] = ['A']
        reviews = {'HR': copy.deepcopy(f.hr), 'TECH': copy.deepcopy(f.tech)}
        reviews['HR']['questions']['1']['scores']['A'] = 4
        reviews['TECH']['questions']['1']['scores']['B'] = 2
        for role in reviews:
            reviews[role]['questions']['2'] = copy.deepcopy(reviews[role]['questions']['1'])
        reviews['HR']['questions']['2']['scores']['A'] = 5
        data = summarize_review({'1': fixtures.BODY, '2': fixtures.BODY}, spec, reviews, {'HR': .4, 'TECH': .6})
        self.assertEqual(data['questions']['1']['weighted_index'], 56)
        self.assertEqual(data['questions']['2']['weighted_index'], 100)
        self.assertIsNone(data['questions']['2']['role_indices']['TECH'])
        self.assertEqual(data['role_means'], {'HR': 90, 'TECH': 40})
        self.assertEqual(data['mean_weighted_index'], 78)

    def test_weight_profile_freezes_and_mismatch_fails(self):
        f = self.f
        f.packets = f.base / 'profile'
        self.assertEqual(f.generate('--weight-profile', 'HR_PUBLIC_DRIVEN').returncode, 0)
        f.token = json.loads((f.packets / 'session_token.json').read_text(encoding='utf-8'))
        self.assertEqual(f.token['review_weights'], {'HR': .6, 'TECH': .4})
        f.hr, f.tech = f.review('HR'), f.review('TECH')
        self.assertEqual(f.grade(None, None, '--weight-profile', 'HR_PUBLIC_DRIVEN').returncode, 0)
        self.assertEqual(f.grade().returncode, 2)
        self.assertEqual(f.grade(None, None, '--weight-profile', 'BALANCED', '--hr-weight', '.5').returncode, 2)

    def test_expired_age_is_information_only_with_unchanged_inputs(self):
        f = self.f
        f.token['created_at'] = '2000-01-01T00:00:00+00:00'
        (f.packets / 'session_token.json').write_text(json.dumps(f.token), encoding='utf-8')
        run = f.grade()
        self.assertEqual(run.returncode, 0)
        self.assertIn('시간 경과', run.stdout)
        self.assertIn('**REVIEW_COMPLETE**', run.stdout)
        self.assertIsNone(review_age_notice({'created_at': '2026-10-04T00:00:00+00:00'}, datetime(2026, 10, 4, 1, tzinfo=timezone.utc)))

    def test_organization_guide_does_not_invent_relationship_evidence(self):
        f = self.f
        f.context.write_text(json.dumps({'organization_contract': {'parent_legal_entity': '가상 법인', 'client_service_domain': '가상 서비스'}}), encoding='utf-8')
        f.packets = f.base / 'organization'
        self.assertEqual(f.generate().returncode, 0)
        f.token = json.loads((f.packets / 'session_token.json').read_text(encoding='utf-8'))
        f.hr, f.tech = f.review('HR'), f.review('TECH')
        run = f.grade()
        self.assertEqual(run.returncode, 0)
        self.assertIn('가상 법인', run.stdout)
        self.assertIn('관계 근거: 미확인', run.stdout)

    def test_invalid_json_output_does_not_leave_old_score(self):
        f = self.f
        output = f.base / 'summary.json'
        self.assertEqual(f.grade(None, None, '--out-json', output).returncode, 0)
        f.tech['questions']['1']['interview'] = self.interview()
        f.tech['questions']['1']['interview']['questions'][0]['anchor_quote'] = '없는 인용'
        self.assertEqual(f.grade(None, None, '--out-json', output).returncode, 2)
        data = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(data['state'], 'NOT_EVALUABLE')
        self.assertNotIn('mean_weighted_index', data)


if __name__ == '__main__':
    unittest.main()
