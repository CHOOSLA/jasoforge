"""v5.2 행동 검사: 작성 프로필 문체 규칙, 면책 문장, 문항 사이 반복, 평가 패킷의 프로필 차단."""
import importlib.util, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


lint = module('lint'); pipeline = module('run_pipeline')
from evaluation_contract import ContractError, validate_spec

STYLED = ('[지원 동기]\n화면·API·DB를 함께 봤고, 요청 수, 응답 크기, 캐시 정책을 하나씩 비교했습니다. '
          '이 일을 계속 맡고 싶습니다.')
AXES = list('ABCDEFHI')


def spec_for(qids, **extra):
    spec = {'questions': {q: {'min': 1, 'max': 2000, 'prompt': '경험을 설명하십시오.', 'applicable_axes': AXES,
                              'axis_applicability_reasons': {a: '테스트용 평가 범위' for a in AXES}} for q in qids}}
    spec.update(extra)
    return spec


def run_lint(draft_text, spec):
    with tempfile.TemporaryDirectory() as tmp:
        draft, spec_path = Path(tmp) / 'draft.txt', Path(tmp) / 'spec.json'
        draft.write_text(draft_text, encoding='utf-8')
        spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding='utf-8')
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / 'lint.py'), str(draft), str(spec_path)],
                              capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})


class FeedbackControlTests(unittest.TestCase):
    def test_style_signals_are_reference_only_without_profile(self):
        result = lint.check('1', STYLED, {'min': 1, 'max': 2000}, [], [])
        self.assertIn('가운뎃점 2개', result['info']['문체신호'])
        self.assertFalse([x for x in result['issues'] if '프로필 문체' in x])
        self.assertFalse([x for x in result['issues'] if x.startswith('FAIL')])

    def test_profile_style_rules_warn_but_never_fail(self):
        checks = {'forbid_chars': ['·'], 'max_commas_per_sentence': 1, 'forbid_headings': True,
                  'watch_patterns': [{'pattern': r'싶습니다', 'label': '바람 표현'}]}
        issues = lint.check('1', STYLED, {'min': 1, 'max': 2000}, [], [], style_checks=checks)['issues']
        warns = [x for x in issues if x.startswith('WARN 프로필 문체')]
        self.assertEqual(len(warns), 4, issues)
        self.assertTrue(any("금지 문자 '·' 2회" in x for x in warns))
        self.assertTrue(any('바람 표현 1회' in x for x in warns))
        self.assertFalse([x for x in issues if x.startswith('FAIL')])

    def test_digit_grouping_commas_are_not_counted(self):
        info = lint.check('1', '예시 가격 3,428,000원이 답에 찍혔습니다.', {'min': 1}, [], [])['info']
        self.assertIn('쉼표 0개', info['문체신호'])

    def test_disclaimer_sentences_are_flagged_and_can_be_disabled(self):
        text = '팀은 일정 안에 마쳤습니다. 다만 실제로 아낀 시간을 잰 것은 아닙니다. 대조한 범위에서는 틀린 답이 없었습니다.'
        issues = lint.check('1', text, {'min': 1}, [], [])['issues']
        self.assertEqual(len([x for x in issues if x.startswith('WARN 면책')]), 2, issues)
        off = lint.check('1', text, {'min': 1}, [], [], style_checks={'hedge_check': False})['issues']
        self.assertFalse([x for x in off if x.startswith('WARN 면책')])

    def test_cross_question_repetition_is_info_only(self):
        draft = ('===1===\n수집과 분류 사이에 버퍼를 두었고 경험을 바로 쓸 수 있어 지원했습니다.\n'
                 '===2===\n계열사 시스템 위에서도 경험을 바로 쓸 수 있어 지원했습니다. 회사A의 업무입니다.\n')
        spec = spec_for(['1', '2'], proper_nouns=['회사A'])
        run = run_lint(draft, spec)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn('INFO 문항 간 같은 표현', run.stdout)
        self.assertNotIn('WARN 문항 간', run.stdout)
        self.assertIn('FAIL 0건', run.stdout)

    def test_spec_rejects_malformed_profile_fields(self):
        draft = {'1': '본문'}
        bad = [
            spec_for(['1'], style_checks={'forbid_char': ['·']}),
            spec_for(['1'], style_checks={'watch_patterns': [{'pattern': '(', 'label': '깨진 패턴'}]}),
            spec_for(['1'], style_checks={'max_commas_per_sentence': -1}),
        ]
        for spec in bad:
            with self.assertRaises(ContractError):
                validate_spec(spec, draft, require_axes=True)
        ok = spec_for(['1'], style_checks={'forbid_chars': ['·'], 'hedge_check': True})
        validate_spec(ok, draft, require_axes=True)


    def test_reinstall_keeps_user_workspace(self):
        spec = importlib.util.spec_from_file_location('installer', ROOT / 'installer.py')
        installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'src', Path(tmp) / 'dst'
            (source / 'scripts').mkdir(parents=True)
            (source / 'SKILL.md').write_text('new', encoding='utf-8')
            (source / 'scripts' / 'lint.py').write_text('# new', encoding='utf-8')
            (target / 'scratch' / '2026H2_app' / 'versions').mkdir(parents=True)
            (target / 'scratch' / '2026H2_app' / 'versions' / 'draft.txt').write_text('사용자 원고', encoding='utf-8')
            (target / 'old_reference.md').write_text('old', encoding='utf-8')
            self.assertEqual(installer.install_target(source, target), 'copied (user data kept)')
            self.assertEqual((target / 'scratch' / '2026H2_app' / 'versions' / 'draft.txt').read_text(encoding='utf-8'), '사용자 원고')
            self.assertFalse((target / 'old_reference.md').exists())
            self.assertEqual((target / 'SKILL.md').read_text(encoding='utf-8'), 'new')
            # 사용자 데이터가 있으면 심볼릭 링크로 바꾸지 않고 복사한다.
            self.assertEqual(installer.install_target(source, target, use_symlink=True), 'copied (user data kept)')
            self.assertTrue((target / 'scratch').is_dir())

    def test_packet_template_keeps_reader_side_rules(self):
        # 패킷 문구는 코드가 만든다. LLM 출력 검사가 아니라 템플릿 회귀 검사다.
        spec = spec_for(['1'], style_checks={'forbid_chars': ['·']})
        rubric = json.loads((ROOT / 'references' / 'rubric_hr.json').read_text(encoding='utf-8'))
        lint_report = "WARN 프로필 문체: 금지 문자 '·' 1회\nFAIL 0건"
        inputs = {'draft': {'path': '/tmp/app/versions/v9.txt', 'sha256': '0'}}
        text = pipeline.packet('HR', 'r1', inputs, '===1===\n본문', spec, {}, rubric, lint_report, '')
        self.assertIn('가정임을 밝힌 업무 상황', text)
        self.assertIn('최대 분량과 현재 분량', text)
        # 작성 프로필 규칙과 판 번호가 붙은 원고 경로는 평가자에게 가지 않는다
        for leaked in ('style_checks', 'WARN 프로필 문체', 'versions/v9.txt'):
            self.assertNotIn(leaked, text)
        self.assertIn('FAIL 0건', text)


if __name__ == '__main__':
    unittest.main()
