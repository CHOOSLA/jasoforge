"""Behavioral regressions: optional evidence cannot become a writing penalty."""
import copy
import json
import unittest
import test_evaluation_integrity as fixtures


class ReviewSeparationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.EvaluationIntegrityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.n = 0

    def refresh(self, context=None):
        f=self.f;self.n+=1
        if context is not None:f.context.write_text(json.dumps(context,ensure_ascii=False))
        f.spec_path.write_text(json.dumps(f.spec,ensure_ascii=False))
        f.packets=f.base/f'packets-{self.n}'
        run=f.generate();self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        f.token=json.loads((f.packets/'session_token.json').read_text())
        f.hr,f.tech=f.review('HR'),f.review('TECH')

    def result(self):
        out=self.f.base/'aggregate.json'
        run=self.f.grade(None,None,'--out-json',out)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        return json.loads(out.read_text()),run.stdout

    def evidence(self,kind='record',availability='provided'):
        data={'fact_check':{'sources':[],'claims':{'1':[{'id':'c1','quote':fixtures.BODY,'availability':availability,'source_ids':[]}]}}}
        if availability=='provided':
            data['fact_check']['sources']=[{'id':'s1','kind':kind,'text':'요청의 중복 처리 구분은 구현하지 않았습니다.'}]
            data['fact_check']['claims']['1'][0]['source_ids']=['s1']
        return data

    def finding(self,status='CONFLICT',impact='minor',evidence=True):
        return {'claim_id':'c1','status':status,'impact':impact,'rationale':'합성 기록에서 구현 범위가 다르다. 실제 지원자 평가가 아니다.',
                'evidence':[{'source_id':'s1','quote':'요청의 중복 처리 구분은 구현하지 않았습니다.'}] if evidence else []}

    def test_optional_archive_and_unknown_counter_are_not_writing_penalties(self):
        first,_=self.result()
        self.assertEqual(first['mean_weighted_index'],100)
        self.assertEqual(first['questions']['1']['fact_review']['coverage'],'NOT_PROVIDED')
        self.f.spec['questions']['1'].update(spec_confirmation='CONFIRMED',spec_source='합성 공고의 규격')
        self.refresh()
        second,_=self.result()
        self.assertEqual(first['mean_weighted_index'],second['mean_weighted_index'])
        self.assertEqual(second['questions']['1']['compliance']['status'],'MET')

    def test_small_fact_correction_stays_local_and_material_conflict_is_prominent(self):
        base,_=self.result()
        self.refresh(self.evidence())
        q=self.f.tech['questions']['1'];q['fact_review']['findings']=[self.finding()]
        minor,_=self.result()
        self.assertEqual(minor['mean_weighted_index'],base['mean_weighted_index'])
        self.assertEqual(minor['attention_flags'],[])
        q['fact_review']['findings'][0]['impact']='material'
        material,text=self.result()
        self.assertEqual(material['mean_weighted_index'],base['mean_weighted_index'])
        self.assertEqual(material['score_interpretation'],'PROVISIONAL_FACT_CONFLICT')
        self.assertIn({'question_id':'1','flag':'MATERIAL_FACT_CONFLICT'},material['attention_flags'])
        self.assertLess(text.index('핵심 주장 불일치'),text.index('작성 점수 요약'))

    def test_source_addition_does_not_change_fixed_writing_review(self):
        base,_=self.result();ctx=self.evidence(kind='user_statement')
        ctx['fact_check']['sources'][0]['text']=fixtures.BODY
        self.refresh(ctx)
        finding=self.finding(status='CONSISTENT');finding['evidence'][0]['quote']=fixtures.BODY
        self.f.tech['questions']['1']['fact_review']['findings']=[finding]
        result,_=self.result()
        self.assertEqual(result['mean_weighted_index'],base['mean_weighted_index'])
        self.assertEqual(result['questions']['1']['fact_review']['findings'][0]['source_kinds'],['user_statement'])

    def test_host_omission_is_distinguished_from_new_user(self):
        self.refresh(self.evidence(availability='input_missing'))
        self.f.tech['questions']['1']['fact_review']['findings']=[self.finding('UNVERIFIED','material',False)]
        result,_=self.result()
        self.assertEqual(result['mean_weighted_index'],100)
        self.assertEqual(result['questions']['1']['fact_review']['coverage'],'INPUT_INCOMPLETE')
        self.assertIn({'question_id':'1','flag':'INPUT_INCOMPLETE'},result['attention_flags'])

    def test_draft_derived_source_cannot_circularly_verify(self):
        self.refresh(self.evidence(kind='draft_derived'))
        self.f.tech['questions']['1']['fact_review']['findings']=[self.finding('CONSISTENT')]
        self.f.assert_invalid(self.f.grade())

    def test_fact_quote_and_source_ids_and_coverage_are_validated(self):
        self.refresh(self.evidence())
        for variant in ['missing','wrong_quote','unknown_source','duplicate','bad_id']:
            with self.subTest(variant=variant):
                tech=copy.deepcopy(self.f.tech);finding=self.finding()
                findings=[] if variant=='missing' else [finding]
                if variant=='wrong_quote':finding['evidence'][0]['quote']='자료에 없는 말'
                if variant=='unknown_source':finding['evidence'][0]['source_id']='missing'
                if variant=='duplicate':findings.append(copy.deepcopy(finding))
                if variant=='bad_id':finding['claim_id']=[]
                tech['questions']['1']['fact_review']['findings']=findings
                self.f.assert_invalid(self.f.grade(tech=tech))

    def test_no_source_cannot_be_reported_as_confirmed(self):
        self.refresh(self.evidence(availability='not_provided'))
        self.f.tech['questions']['1']['fact_review']['findings']=[self.finding('CONSISTENT',evidence=False)]
        self.f.assert_invalid(self.f.grade())

    def test_missing_required_prompt_yields_no_misleading_partial_total(self):
        q=self.f.hr['questions']['1'];q['scores']['F']=None
        q['axis_evidence']['F']={'status':'DEFERRED','missing_input':'prompt','reason':'축약 제목만 있어 전체 지시문 미확보'}
        result,text=self.result()
        self.assertIsNone(result['mean_weighted_index'])
        self.assertIsNone(result['questions']['1']['weighted_index'])
        self.assertEqual(result['state'],'INPUT_INCOMPLETE')
        self.assertIn('평가 유보',text)
        q['axis_evidence']['F']['missing_input']='personal_evidence'
        self.f.assert_invalid(self.f.grade())

    def test_length_violation_is_reported_without_changing_writing_score(self):
        base,_=self.result();self.f.spec['questions']['1']['max']=1;self.refresh()
        result,_=self.result()
        self.assertEqual(result['mean_weighted_index'],base['mean_weighted_index'])
        self.assertEqual(result['questions']['1']['compliance']['status'],'VIOLATION')
        self.assertIn({'question_id':'1','flag':'COMPLIANCE_VIOLATION'},result['attention_flags'])

    def test_writing_change_still_changes_score_and_missing_archive_is_not_a_severity(self):
        base,_=self.result();q=self.f.tech['questions']['1'];q['scores']['B']=2
        q['axis_evidence']['B'].update(rationale='어떤 조건으로 중복을 구분했는지 설명이 빠졌다.',severity='revise')
        result,_=self.result();self.assertLess(result['mean_weighted_index'],base['mean_weighted_index'])
        q['axis_evidence']['B']['severity']='verify';self.f.assert_invalid(self.f.grade())

    def test_legacy_token_and_scores_are_not_relabelled(self):
        self.f.token['schema_version']=2
        (self.f.packets/'session_token.json').write_text(json.dumps(self.f.token))
        self.f.assert_invalid(self.f.grade())

    def test_missing_prompt_can_be_deferred_without_blocking_other_feedback(self):
        del self.f.spec['questions']['1']['prompt']
        self.refresh()
        self.f.assert_invalid(self.f.grade())
        q=self.f.hr['questions']['1']
        for axis in ['E','F']:
            q['scores'][axis]=None
            q['axis_evidence'][axis]={'status':'DEFERRED','missing_input':'prompt','reason':'문항 원문이 없어 요구를 확정할 수 없다.'}
        result,_=self.result()
        self.assertIsNone(result['mean_weighted_index'])
        self.assertEqual(result['state'],'INPUT_INCOMPLETE')

    def test_legacy_sources_cannot_be_hidden_by_empty_fact_check(self):
        f=self.f
        f.context.write_text(json.dumps({'experience_sources':[{'text':'존재하는 실제 기록'}],'fact_check':{'sources':[],'claims':{}}}))
        f.packets=f.base/'hidden-source'
        self.f.assert_invalid(f.generate())

    def test_unverified_finding_preserves_available_source_kind(self):
        self.refresh(self.evidence(kind='user_statement'))
        self.f.tech['questions']['1']['fact_review']['findings']=[self.finding('UNVERIFIED','material',False)]
        result,_=self.result()
        self.assertEqual(result['questions']['1']['fact_review']['findings'][0]['source_kinds'],['user_statement'])

    def test_contextless_first_use_reaches_ledger_without_creating_fake_context(self):
        f=self.f;f.context.unlink();f.packets=f.base/'contextless-packets'
        run=f.command('run_pipeline.py',f.draft,f.spec_path,'--out-packets-dir',f.packets)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        f.token=json.loads((f.packets/'session_token.json').read_text())
        hr,tech=f.review('HR'),f.review('TECH')
        (f.base/'hr.json').write_text(json.dumps(hr));(f.base/'tech.json').write_text(json.dumps(tech))
        log={'run_id':f.token['run_id'],'evaluators':{r:{'call_id':'fixture-'+r,'model':'synthetic','started_at':'2026-10-04','inherited_context':False,'packet_sha256':f.token['inputs'][r.lower()+'_packet']['sha256']} for r in ['HR','TECH']}}
        (f.base/'execution.json').write_text(json.dumps(log))
        run=f.command('record_review.py',f.draft,f.spec_path,'--hr-eval',f.base/'hr.json','--tech-eval',f.base/'tech.json','--session-token',f.packets/'session_token.json','--execution-log',f.base/'execution.json','--application-key','new-user','--version','v1','--ledger',f.base/'no-context-ledger.json')
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        stored=json.loads((f.base/'no-context-ledger.json').read_text())['runs'][0]
        self.assertEqual(stored['context'],{})
        self.assertNotIn('context',stored['source_file_hashes'])


if __name__=='__main__':unittest.main()
