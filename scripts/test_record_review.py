"""Synthetic ledger integration checks; these are not independent model reviews."""
import json
import unittest

import test_evaluation_integrity as fixtures
from smart_router import SmartIngestionRouter


class RecordReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EvaluationIntegrityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.assertEqual(f.grade().returncode, 0)
        self.ledger = f.base / 'ledger.json'
        self.execution = f.base / 'execution.json'
        self.execution.write_text(json.dumps({'run_id': f.token['run_id'], 'evaluators': {
            role: {'call_id': 'synthetic-fixture-' + role, 'model': 'synthetic-no-model',
                   'started_at': '2026-10-03T00:00:00Z', 'inherited_context': False,
                   'packet_sha256': f.token['inputs'][role.lower() + '_packet']['sha256']}
            for role in ('HR', 'TECH')}}))

    def record(self, key='synthetic-test', version='v1'):
        f = self.fixture
        return f.command('record_review.py', f.draft, f.spec_path, '--context', f.context,
                         '--hr-eval', f.base / 'hr.json', '--tech-eval', f.base / 'tech.json',
                         '--session-token', f.packets / 'session_token.json', '--execution-log', self.execution,
                         '--application-key', key, '--version', version, '--ledger', self.ledger)

    def test_records_full_snapshot_and_is_idempotent(self):
        run = self.record()
        self.assertEqual(run.returncode, 0, run.stderr)
        first = self.ledger.read_bytes()
        stored = json.loads(first)['runs'][0]
        self.assertEqual(stored['draft_text'], self.fixture.draft.read_bytes().decode('utf-8'))
        self.assertEqual(stored['reviews']['HR'], self.fixture.hr)
        self.assertIn('REVIEW_COMPLETE', stored['aggregate_report'])
        run = self.record()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('ALREADY_RECORDED', run.stdout)
        self.assertEqual(self.ledger.read_bytes(), first)

    def test_a_new_run_is_appended_without_replacing_history(self):
        self.assertEqual(self.record().returncode, 0)
        before = json.loads(self.ledger.read_text())['runs'][0]
        f = self.fixture
        f.packets = f.base / 'second_packets'
        self.assertEqual(f.generate().returncode, 0)
        f.token = json.loads((f.packets / 'session_token.json').read_text())
        f.hr, f.tech = f.review('HR'), f.review('TECH')
        self.assertEqual(f.grade().returncode, 0)
        log = json.loads(self.execution.read_text())
        log['run_id'] = f.token['run_id']
        for role, call in log['evaluators'].items():
            call['call_id'] += '-second'
            call['packet_sha256'] = f.token['inputs'][role.lower() + '_packet']['sha256']
        self.execution.write_text(json.dumps(log))
        run = self.record()
        self.assertEqual(run.returncode, 0, run.stderr)
        runs = json.loads(self.ledger.read_text())['runs']
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0], before)
        self.assertNotEqual(runs[0]['run_id'], runs[1]['run_id'])

    def test_conflicting_application_and_run_are_preserved(self):
        self.assertEqual(self.record().returncode, 0)
        before = self.ledger.read_bytes()
        for run in (self.record(key='another-application'), self.record(version='v2')):
            self.assertEqual(run.returncode, 2)
            self.assertEqual(self.ledger.read_bytes(), before)

    def test_legacy_schema_is_not_overwritten(self):
        self.ledger.write_text('[{"score": 95}]')
        before = self.ledger.read_bytes()
        self.assertEqual(self.record().returncode, 2)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_changed_input_cannot_be_recorded(self):
        self.fixture.draft.write_text('===1===\n바뀐 원고입니다.')
        self.assertEqual(self.record().returncode, 2)
        self.assertFalse(self.ledger.exists())

    def test_context_application_mismatch_is_rejected(self):
        f = self.fixture
        context = json.loads(f.context.read_text())
        context['application_key'] = 'another-application'
        f.context.write_text(json.dumps(context))
        f.packets = f.base / 'context_packets'
        self.assertEqual(f.generate().returncode, 0)
        f.token = json.loads((f.packets / 'session_token.json').read_text())
        f.hr, f.tech = f.review('HR'), f.review('TECH')
        self.assertEqual(f.grade().returncode, 0)
        run = self.record()
        self.assertEqual(run.returncode, 2)
        self.assertIn('context의 지원서키', run.stderr)
        self.assertFalse(self.ledger.exists())

    def test_invalid_quote_cannot_be_recorded(self):
        f = self.fixture
        f.hr['questions']['1']['axis_evidence']['A']['quotes'] = ['원고에 없는 인용']
        (f.base / 'hr.json').write_text(json.dumps(f.hr))
        self.assertEqual(self.record().returncode, 2)
        self.assertFalse(self.ledger.exists())

    def test_same_evaluator_call_is_rejected(self):
        log = json.loads(self.execution.read_text())
        log['evaluators']['TECH']['call_id'] = log['evaluators']['HR']['call_id']
        self.execution.write_text(json.dumps(log))
        self.assertEqual(self.record().returncode, 2)
        self.assertFalse(self.ledger.exists())

    def test_locked_ledger_is_not_modified(self):
        self.assertEqual(self.record().returncode, 0)
        before = self.ledger.read_bytes()
        lock = self.ledger.with_name('ledger.json.lock')
        lock.write_text('other writer')
        self.assertEqual(self.record().returncode, 2)
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertTrue(lock.exists())


class StorageNetworkModeTests(unittest.TestCase):
    def test_local_storage_still_allows_public_research(self):
        route = SmartIngestionRouter.route_input('--local https://example.com/job', True)
        self.assertTrue(route['network_allowed'])
        self.assertEqual(route['mode'], 'LOCAL')
        self.assertEqual(route['next_action'], 'READ_URL_AND_CLASSIFY')
        route = SmartIngestionRouter.route_input('/tmp/draft.txt', True)
        self.assertTrue(route['network_allowed'])
        self.assertEqual(route['mode'], 'LOCAL')

    def test_local_storage_does_not_read_notion(self):
        route = SmartIngestionRouter.route_input('--local https://app.notion.com/p/example', True)
        self.assertEqual(route['next_action'], 'LOCAL_NEEDS_PAGE_EXPORT')

    def test_offline_file_has_no_network(self):
        route = SmartIngestionRouter.route_input('--offline /tmp/draft.txt', True)
        self.assertFalse(route['network_allowed'])
        self.assertEqual(route['next_action'], 'READ_LOCAL_FILE_AND_CLASSIFY')


if __name__ == '__main__':
    unittest.main()
