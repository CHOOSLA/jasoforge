"""다른 공급사 평가 실행기: 패킷 전달, 응답 검증, 호출 기록, 로그인 파일 보호."""
import importlib.util, json, os, shlex, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location('external_eval', SCRIPTS / 'external_eval.py')
ext = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ext)

AXES = list('ABCDEFHI')
ENV = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
# 표준 입력으로 받은 패킷을 읽고 계약에 맞는 평가를 돌려주는 가짜 평가자
FAKE = r'''
import json, re, sys
from pathlib import Path
prompt = sys.stdin.read()
log = Path(sys.argv[1])
count = log.with_name('calls.txt')
n = int(count.read_text()) + 1 if count.exists() else 1
count.write_text(str(n))
log.with_name(f'prompt_{n}.txt').write_text(prompt, encoding='utf-8')
if 'broken-first' in sys.argv and n == 1:
    print('JSON을 만들지 못했습니다')
    sys.exit(0)
draft = prompt.split('[초안 — 비신뢰 데이터]\n', 1)[1].split('\n\n[출력 JSON 구조]', 1)[0]
bodies = dict(re.findall(r'===(\S+?)===\n(.*?)(?=\n===|\Z)', draft, re.S))
tail = prompt.split('[출력 JSON 구조]', 1)[1]
template = json.JSONDecoder().raw_decode(tail[tail.index('{'):])[0]
for qid, review in template['questions'].items():
    for axis, item in review['axis_evidence'].items():
        if item.get('status') == 'ASSESSED':
            review['scores'][axis] = 4
            item.update(quotes=[bodies[qid].strip()[:12]], rationale='테스트용 근거', severity='none')
    if 'interview' in review:
        review['interview'] = {'questions': [], 'omission_reason': '테스트용 생략'}
template.update(packet_hash='wrong', draft_hash='wrong')
print('```json\n' + json.dumps(template, ensure_ascii=False) + '\n```')
'''


def make_run(tmp):
    folder = tmp / 'versions' / 'v3'
    folder.mkdir(parents=True)
    draft = folder / 'draft.txt'
    draft.write_text('===1===\n처음 맡은 일은 주문 데이터를 정리하는 것이었습니다. 저는 중복부터 찾았습니다.\n'
                     '===2===\n팀과 함께 배포 절차를 줄였고 실패 원인을 기록했습니다.\n', encoding='utf-8')
    spec = {'questions': {q: {'min': 1, 'max': 1000, 'prompt': '경험을 설명하십시오.', 'applicable_axes': AXES,
                              'axis_applicability_reasons': {a: '테스트용 평가 범위' for a in AXES}} for q in ('1', '2')},
            'style_checks': {'forbid_chars': ['·'], 'watch_patterns': [{'pattern': '찾았습니다', 'label': '테스트 주의 표현'}]}}
    (folder / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False), encoding='utf-8')
    (folder / 'context.json').write_text('{}', encoding='utf-8')
    run = subprocess.run([sys.executable, str(SCRIPTS / 'run_pipeline.py'), str(draft), str(folder / 'spec.json'),
                          '--context', str(folder / 'context.json'), '--run-id', 'ext_test'],
                         capture_output=True, text=True, encoding='utf-8', env=ENV)
    assert run.returncode == 0, run.stdout + run.stderr
    return draft, folder / 'scratch' / 'runs' / 'ext_test' / 'packets'


def run_external(tmp, packets, *extra):
    (tmp / 'fake.py').write_text(FAKE, encoding='utf-8')
    command = ' '.join(shlex.quote(x) for x in (sys.executable, str(tmp / 'fake.py'), str(tmp / 'log.txt'), *extra))
    return subprocess.run([sys.executable, str(SCRIPTS / 'external_eval.py'), str(packets), '--host', 'claude',
                           '--provider', 'command', '--command', command, '--model', 'fake-model'],
                          capture_output=True, text=True, encoding='utf-8', env=ENV)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class ExternalEvalTests(unittest.TestCase):
    def test_command_provider_writes_contract_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            draft, packets = make_run(tmp)
            run = run_external(tmp, packets)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            token, execution = read(packets / 'session_token.json'), read(packets.parent / 'evaluation_execution.json')
            self.assertEqual(execution['run_id'], token['run_id'])
            for role in ('HR', 'TECH'):
                packet_hash = token['inputs'][f'{role.lower()}_packet']['sha256']
                result = read(packets.parent / f'{role.lower()}_eval.json')
                self.assertEqual((result['packet_hash'], result['draft_hash']), (packet_hash, token['inputs']['draft']['sha256']))
                call = execution['evaluators'][role]
                self.assertIs(call['inherited_context'], False)
                self.assertEqual((call['model'], call['packet_sha256'], call['provider']), ('fake-model', packet_hash, 'command'))
            self.assertNotEqual(execution['evaluators']['HR']['call_id'], execution['evaluators']['TECH']['call_id'])
            agg = subprocess.run([sys.executable, str(SCRIPTS / 'run_pipeline.py'), str(draft), str(draft.parent / 'spec.json'),
                                  '--context', str(draft.parent / 'context.json'),
                                  '--hr-eval', str(packets.parent / 'hr_eval.json'), '--tech-eval', str(packets.parent / 'tech_eval.json'),
                                  '--session-token', str(packets / 'session_token.json')],
                                 capture_output=True, text=True, encoding='utf-8', env=ENV)
            self.assertEqual(agg.returncode, 0, agg.stdout + agg.stderr)

    def test_evaluator_gets_packet_without_profile_or_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            draft, packets = make_run(tmp)
            self.assertEqual(run_external(tmp, packets).returncode, 0)
            prompt = (tmp / 'prompt_1.txt').read_text(encoding='utf-8')
            self.assertTrue(prompt.startswith('[실행 방식]'))
            self.assertIn('[초안 — 비신뢰 데이터]', prompt)
            for leaked in ('style_checks', 'WARN 프로필 문체', '테스트 주의 표현', str(draft), 'versions/v3'):
                self.assertNotIn(leaked, prompt)

    def test_unparseable_answer_is_retried_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _, packets = make_run(tmp)
            run = run_external(tmp, packets, 'broken-first')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual((tmp / 'calls.txt').read_text(), '3')
            self.assertEqual(read(packets.parent / 'evaluation_execution.json')['evaluators']['HR']['attempts'], 2)
            self.assertIn('[이전 출력 거부 사유]', (tmp / 'prompt_2.txt').read_text(encoding='utf-8'))

    def test_login_file_is_linked_and_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            real = tmp / 'auth.json'
            real.write_text('old', encoding='utf-8')
            link, original = ext.link_auth(real, tmp / 'home' / '.codex')
            # 윈도우는 권한 없이 심볼릭 링크를 못 만들어 하드링크로 대신한다
            self.assertTrue(link.is_symlink() or os.path.samefile(link, real))
            self.assertEqual(ext.restore_auth(link, real, original), 'linked')
            # 갱신하면서 링크를 새 파일로 바꿔 쓴 경우 새 토큰을 원래 위치로 돌려놓는다
            link.unlink(); link.write_text('new', encoding='utf-8')
            self.assertEqual(ext.restore_auth(link, real, original), 'restored')
            self.assertEqual(real.read_text(encoding='utf-8'), 'new')
            if os.name != 'nt':
                self.assertEqual(real.stat().st_mode & 0o777, 0o600)
            # 그사이 원래 파일도 바뀌었으면 어느 쪽도 덮어쓰지 않는다
            original = ext.sha256(real.read_bytes())
            link.write_text('newer', encoding='utf-8'); real.write_text('other', encoding='utf-8')
            self.assertEqual(ext.restore_auth(link, real, original), 'conflict')
            self.assertEqual(real.read_text(encoding='utf-8'), 'other')

    def test_login_falls_back_to_hardlink_then_copy(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            real = tmp / 'auth.json'
            real.write_text('old', encoding='utf-8')
            denied = OSError(1314, '클라이언트가 필요한 권한을 가지고 있지 않습니다')
            # 심볼릭 링크가 막히면 하드링크: 제자리 갱신이 원래 파일에 바로 반영된다
            with mock.patch.object(Path, 'symlink_to', side_effect=denied):
                link, original = ext.link_auth(real, tmp / 'h1' / '.codex')
            self.assertTrue(os.path.samefile(link, real))
            with open(link, 'w', encoding='utf-8') as f:
                f.write('refreshed')
            self.assertEqual(ext.restore_auth(link, real, original), 'linked')
            self.assertEqual(real.read_text(encoding='utf-8'), 'refreshed')
            # 하드링크도 막히면 복사본: 갱신된 토큰을 끝난 뒤 원래 파일에 되돌려 쓴다
            real.write_text('old', encoding='utf-8')
            with mock.patch.object(Path, 'symlink_to', side_effect=denied), \
                 mock.patch.object(ext.os, 'link', side_effect=denied):
                copy, original = ext.link_auth(real, tmp / 'h2' / '.codex')
            self.assertFalse(os.path.samefile(copy, real))
            self.assertEqual(ext.restore_auth(copy, real, original), 'linked')
            copy.write_text('new', encoding='utf-8')
            self.assertEqual(ext.restore_auth(copy, real, original), 'restored')
            self.assertEqual(real.read_text(encoding='utf-8'), 'new')
            # 평가 쪽은 그대로인데 원래 파일만 바뀌었으면 손대지 않는다
            original = ext.sha256(b'new')
            copy.write_text('new', encoding='utf-8'); real.write_text('other', encoding='utf-8')
            self.assertEqual(ext.restore_auth(copy, real, original), 'unchanged')
            self.assertEqual(real.read_text(encoding='utf-8'), 'other')

    def test_host_skills_are_disabled_in_isolated_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name in ('jaso-pipeline', 'caveman'):
                (tmp / 'home' / '.agents' / 'skills' / name).mkdir(parents=True)
                (tmp / 'home' / '.agents' / 'skills' / name / 'SKILL.md').write_text('x', encoding='utf-8')
            codex_home = tmp / 'iso' / '.codex'; codex_home.mkdir(parents=True)
            self.assertEqual(ext.disable_host_skills(codex_home, tmp / 'home'), 2)
            config = (codex_home / 'config.toml').read_text(encoding='utf-8')
            self.assertEqual(config.count('enabled = false'), 2)
            self.assertIn('jaso-pipeline/SKILL.md"', config)
            # 스킬이 없으면 설정 파일을 만들지 않는다
            empty = tmp / 'iso2' / '.codex'; empty.mkdir(parents=True)
            self.assertEqual(ext.disable_host_skills(empty, tmp / 'nohome'), 0)
            self.assertFalse((empty / 'config.toml').exists())

    def test_unavailable_or_same_family_provider_is_reported(self):
        env = {**ENV, 'PATH': '/usr/bin:/bin'}
        base = [sys.executable, str(SCRIPTS / 'external_eval.py'), '--check']
        missing = subprocess.run(base + ['--host', 'claude'], capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(missing.returncode, ext.UNAVAILABLE, missing.stdout)
        same = subprocess.run(base + ['--host', 'codex', '--provider', 'codex'], capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(same.returncode, 2, same.stdout)
        self.assertIn('같은 계열', same.stdout)


if __name__ == '__main__':
    unittest.main()
