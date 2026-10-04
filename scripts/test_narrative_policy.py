"""Regression checks for writing freedom and preserved factual/format checks."""
import contextlib,copy,importlib.util,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def module(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
lint=module('lint');grade=module('grade');pipeline=module('run_pipeline')
from evaluation_contract import ContractError, verify_manifest

TEXT=(
'서비스를 나누고 나니 다른 서비스가 가진 정보를 어떻게 가져오고 갱신할지가 고민이었습니다. '
'각 서비스가 필요한 정보만 복사해 자기 데이터베이스에 저장하면 호출 의존은 줄어들지만, '
'복사한 데이터를 계속 최신 상태로 맞춰야 한다면 우리가 분리를 통해 얻으려는 것이 무엇인지 다시 생각하게 됐습니다. '
'필요할 때마다 요청하는 방법도 상대 서비스의 응답을 기다려야 한다는 점에서 쉽게 선택할 수 없었습니다. '
'팀원들과 이 문제를 이야기하며 모든 데이터에 같은 최신성 기준을 적용하고 있었다는 점을 살펴봤습니다. '
'변경이 드문 정보와 현재 상태가 필요한 정보를 구분하면 각각에 맞는 갱신 방법을 선택할 수 있었습니다. '
'연결이 필요한 단계에서 상대 서비스에 문제가 생기면 그 부분을 사용자에게 알리고 다른 기능을 계속 제공할 수 있는지도 함께 검토했습니다. '
'이 판단은 장애 시험을 완료했다는 의미는 아니며 당시 설계 논의에서 정한 범위에 관한 설명입니다. '
'처음에는 데이터를 나누는 것 자체가 목적처럼 느껴졌지만, 각 기능이 어떤 정보를 언제 필요로 하는지를 보면서 선택의 기준을 구체화했습니다. '
'멘토에게 별도 데이터베이스를 사용하는 사례를 듣고 이 방식이 모든 정보를 항상 같게 만드는 일과는 다르다는 점을 다시 검토했습니다.'
)
class NarrativePolicyTests(unittest.TestCase):
 def test_first_paragraph_with_decisions_is_not_mistaken_for_background(self):
  self.assertGreater(len(TEXT),500)
  result=lint.check('1',TEXT+'\n\n갱신 방법을 나누어 설계를 정리했습니다.',
      {'min':1,'max':2000,'discarded_alternative_keywords':['기록에없는대안'],'question_nature':'TECH_PROJECT'},[],['서비스'])
  self.assertFalse(any(x.startswith('FAIL') for x in result['issues']))
  forbidden=['배경 압축','상황 설명','끊는 편','버린 대안','종결어미','리듬 없음']
  self.assertFalse([x for x in result['issues'] if any(f in x for f in forbidden)])
 def test_explicit_length_and_blind_rules_still_fail(self):
  self.assertTrue(any(x.startswith('FAIL') for x in lint.check('1',TEXT,{'max':10},[],[])['issues']))
  self.assertTrue(any(x.startswith('FAIL') for x in lint.check('1','짧은 글',{'min':100},[],[])['issues']))
  self.assertTrue(any(x.startswith('FAIL') for x in lint.check('1','OO대학교에서 수행했습니다.',{'min':1},['OO대학교'],[])['issues']))
 def test_narrative_metadata_does_not_cap_b_or_c(self):
  for kind in ['Type_A','Type_B','Type_C','Type_D','Type_E','', ['Type_A','Type_B']]:
   q={'scores':{'B':5,'C':5},'type_declaration':{'selected_type':kind,'negative_boundary_violated':True,'must_have_evidence_found':''}}
   grade.audit_type_rubric_gating(q,'초기화가 끝난 뒤 접근을 검사했습니다.','TECH_CORE')
   grade.audit_axis_c_gating(q,'초기화가 끝난 뒤 접근을 검사했습니다.')
   self.assertEqual(q['scores'],{'B':5,'C':5})
 def test_quote_integrity_preserved(self):
  self.assertTrue(grade.verify_quote_fuzzy('필요할 때마다 요청하는 방법도',TEXT))
  self.assertFalse(grade.verify_quote_fuzzy('사용자 백만 명에게 배포해 매출을 두 배로 높였습니다.',TEXT))
 def test_multiple_topics_are_not_a_knockout(self):
  kept,_=grade.audit_knockout_gatekeeper({}, {},'MFC MobileNet SSL Pinning 캠핑카 분산 클러스터')
  self.assertNotIn('FLAG_LAUNDRY_LIST',[r['key'] for r in kept])
 def test_old_external_story_flag_is_not_reactivated(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'judgment.json';p.write_text(json.dumps({'knockout_flags':{'FLAG_LAUNDRY_LIST':{'sustained':True}}}))
   kept,_=grade.audit_knockout_gatekeeper({}, {},TEXT,str(p))
   self.assertNotIn('FLAG_LAUNDRY_LIST',[r['key'] for r in kept])
 def test_packet_generation_and_hash_lock(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);draft=base/'draft.txt';spec=base/'spec.json';packets=base/'packets'
   draft.write_text('===1===\n'+TEXT)
   spec.write_text(json.dumps({'questions':{'1':{'min':1,'max':2000,'prompt':'문제 해결 경험을 설명하십시오.','applicable_axes':list('ABCDEFHI'),'axis_applicability_reasons':{a:'테스트용 평가 범위' for a in 'ABCDEFHI'}}},'proper_nouns':['서비스']}))
   run=subprocess.run([sys.executable,str(ROOT/'scripts/run_pipeline.py'),str(draft),str(spec),'--out-packets-dir',str(packets)],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr)
   hr=(packets/'hr_prompt_packet.txt').read_text();tech=(packets/'tech_prompt_packet.txt').read_text()
   self.assertIn(TEXT,hr);self.assertIn(TEXT,tech)
   self.assertNotIn('"type_declaration":',tech)
   self.assertNotIn('Typed Locked Rubric',tech)
   for name in ['hr_eval.json','tech_eval.json']:(packets/name).write_text('{}')
   with contextlib.redirect_stdout(io.StringIO()):
    verify_manifest(packets/'session_token.json',draft,spec,None,ROOT)
    draft.write_text('===1===\n수정된 본문')
    with self.assertRaises(ContractError):
     verify_manifest(packets/'session_token.json',draft,spec,None,ROOT)

if __name__=='__main__':unittest.main()
