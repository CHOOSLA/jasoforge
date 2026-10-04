"""Regression tests for observed scoring, provenance and scope failures.

Fixtures are synthetic contract tests. They are not independent essay evaluations.
"""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation_contract import ALL_AXES, ContractError, file_hash, validate_spec, parse_json
import lint
from grade import verify_quote_fuzzy, audit_knockout_gatekeeper
from smart_router import SmartIngestionRouter

ROOT = Path(__file__).resolve().parent.parent
BODY = "요청이 두 번 처리되는 조건을 확인했습니다. 중복 요청을 구분하여 처리했습니다."


class EvaluationIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "skill"
        shutil.copytree(ROOT / "scripts", self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "references", self.root / "references")
        self.draft = self.base / "draft.txt"
        self.spec_path = self.base / "spec.json"
        self.context = self.base / "context.json"
        self.packets = self.base / "packets"
        self.draft.write_text("===1===\n" + BODY)
        self.spec = {"questions": {"1": {"prompt": "문제 해결 경험을 설명하십시오.", "max": 1000,
            "applicable_axes": list("ABCEF H".replace(" ", "")),
            "axis_applicability_reasons": {a: ("문제 해결 경험 설명의 근거 검토" if a not in "DI" else "직무 적용·가치관을 요구하지 않음") for a in ALL_AXES}}}}
        self.spec_path.write_text(json.dumps(self.spec, ensure_ascii=False))
        self.context.write_text("{}")
        run = self.generate()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.token = json.loads((self.packets / "session_token.json").read_text())
        self.hr, self.tech = self.review("HR"), self.review("TECH")

    def command(self, script, *args):
        return subprocess.run([sys.executable, str(self.root / "scripts" / script), *map(str,args)], capture_output=True, text=True)

    def generate(self, *extra):
        return self.command("run_pipeline.py",self.draft,self.spec_path,"--context",self.context,"--out-packets-dir",self.packets,*extra)

    def review(self, role):
        axes = "AEFI" if role == "HR" else "BCDH"
        applicable = set(self.spec["questions"]["1"]["applicable_axes"])
        data = {"evaluator": role, "run_id": self.token["run_id"], "draft_hash": self.token["inputs"]["draft"]["sha256"],
                "packet_hash": self.token["inputs"][f"{role.lower()}_packet"]["sha256"], "questions":{"1":{"scores":{},"axis_evidence":{}}}}
        q = data["questions"]["1"]
        for axis in axes:
            q["scores"][axis] = 5 if axis in applicable else None
            q["axis_evidence"][axis] = {"status":"ASSESSED","quotes":[BODY],"rationale":"합성 테스트 자료와 주장 범위를 비교했다.","severity":"none"} if axis in applicable else {"status":"NOT_APPLICABLE","reason":self.spec["questions"]["1"]["axis_applicability_reasons"][axis]}
        if role == "TECH":
            q['fact_review'] = {'findings': []}
            q['interview'] = {'questions': [], 'omission_reason': '합성 계약 검사이며 실제 면접 질문은 평가하지 않음.'}
        return data

    def grade(self, hr=None, tech=None, *extra):
        hr_path, tech_path = self.base / "hr.json", self.base / "tech.json"
        hr_path.write_text(json.dumps(hr if hr is not None else self.hr, ensure_ascii=False))
        tech_path.write_text(json.dumps(tech if tech is not None else self.tech, ensure_ascii=False))
        return self.command("run_pipeline.py",self.draft,self.spec_path,"--context",self.context,"--hr-eval",hr_path,"--tech-eval",tech_path,"--session-token",self.packets / "session_token.json",*extra)

    def assert_invalid(self, run):
        self.assertNotEqual(run.returncode, 0, run.stdout)
        self.assertIn("NOT_EVALUABLE",run.stdout)
        self.assertNotIn("/100 (미보정)",run.stdout)
        self.assertNotIn("**REVIEW_COMPLETE**",run.stdout)

    def test_end_to_end_valid_review_is_internal_only(self):
        run = self.grade()
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertIn("**REVIEW_COMPLETE**",run.stdout)
        self.assertIn("100.0/100 (미보정)",run.stdout)
        self.assertNotIn("PASS (합격권)",run.stdout)
        self.assertNotIn("킬러",run.stdout)
        self.assertIn("D: N/A",run.stdout)
        self.assertFalse((self.base / "score_ledger.json").exists())

    def test_missing_optional_archive_does_not_decrease_score(self):
        output=self.base / "new-user.json"
        run=self.grade(None,None,"--out-json",output)
        self.assertEqual(run.returncode,0,run.stdout)
        data=json.loads(output.read_text())
        self.assertEqual(data["mean_weighted_index"],100)
        self.assertEqual(data["questions"]["1"]["fact_review"]["coverage"],"NOT_PROVIDED")
        self.assertEqual(data["questions"]["1"]["compliance"]["status"],"UNVERIFIED")


    def test_missing_quote_cannot_be_perfect(self):
        self.hr["questions"]["1"]["axis_evidence"]["A"]["quotes"]=[]
        self.assert_invalid(self.grade())

    def test_invalid_quote_does_not_restore_low_score(self):
        self.tech["questions"]["1"]["scores"]["H"]=1
        self.tech["questions"]["1"]["axis_evidence"]["H"].update(quotes=["백만 명에게 배포했다."],severity="revise")
        self.assert_invalid(self.grade())

    def test_missing_axis_or_rater_is_invalid(self):
        for field in ("scores","axis_evidence"):
            with self.subTest(field=field):
                data=copy.deepcopy(self.hr);del data["questions"]["1"][field]["A"]
                self.assert_invalid(self.grade(hr=data))
        data=copy.deepcopy(self.tech);data["evaluator"]="HR"
        self.assert_invalid(self.grade(tech=data))

    def test_invalid_scores_do_not_exceed_scale(self):
        for value in (10,True,-1,5.0,None,"5"):
            with self.subTest(value=value):
                data=copy.deepcopy(self.tech);data["questions"]["1"]["scores"]["B"]=value
                self.assert_invalid(self.grade(tech=data))

    def test_na_needs_declared_scope_and_reason(self):
        data=copy.deepcopy(self.tech)
        data["questions"]["1"]["scores"]["B"]=None
        data["questions"]["1"]["axis_evidence"]["B"]={"status":"NOT_APPLICABLE","reason":"평가자 임의 제외"}
        self.assert_invalid(self.grade(tech=data))
        data=copy.deepcopy(self.tech);del data["questions"]["1"]["axis_evidence"]["D"]["reason"]
        self.assert_invalid(self.grade(tech=data))

    def test_wrong_review_question_id_is_invalid(self):
        self.hr["questions"]["2"]=self.hr["questions"].pop("1")
        self.assert_invalid(self.grade())

    def test_changed_inputs_invalidate_review(self):
        for key in ("draft","spec","context","rubric_hr","rubric_tech","question_flows","lint_report","hr_packet","tech_packet"):
            with self.subTest(key=key):
                path=Path(self.token["inputs"][key]["path"]);before=path.read_bytes()
                try:
                    path.write_bytes(before+b"\n ")
                    self.assert_invalid(self.grade())
                finally:path.write_bytes(before)

    def test_stale_or_mixed_review_is_invalid(self):
        for key in ("run_id","draft_hash","packet_hash"):
            with self.subTest(key=key):
                data=copy.deepcopy(self.tech);data[key]="wrong"
                self.assert_invalid(self.grade(tech=data))

    def test_missing_token_fails_closed(self):
        (self.packets / "session_token.json").unlink()
        self.assert_invalid(self.grade())

    def test_historical_import_has_no_current_score(self):
        run=self.grade({}, {}, "--historical-import")
        self.assertEqual(run.returncode,0,run.stdout)
        self.assertIn("HISTORICAL_UNVERIFIED",run.stdout)
        self.assertNotIn("/100",run.stdout)
        self.assert_invalid(self.grade({}, {}, "--allow-stale"))

    def test_packet_creation_is_not_evaluation_and_will_not_overwrite(self):
        self.assertFalse((self.packets / "hr_eval.json").exists())
        before=file_hash(self.packets / "session_token.json")
        self.assert_invalid(self.generate())
        self.assertEqual(before,file_hash(self.packets / "session_token.json"))

    def test_input_edit_during_prepare_cannot_seal_old_packet(self):
        packets=self.base / "racing-packets"
        probe=self.base / "race.py"
        probe.write_text('''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import run_pipeline as p
original=p.run_cmd
spec=Path(sys.argv[3])
def racing_run(command):
    result=original(command)
    data=json.loads(spec.read_text());data['questions']['1']['max']=1
    spec.write_text(json.dumps(data))
    return result
p.run_cmd=racing_run
sys.argv=['run_pipeline.py',sys.argv[2],sys.argv[3],'--context',sys.argv[4],'--out-packets-dir',sys.argv[5]]
sys.exit(p.main())
''')
        run=subprocess.run([sys.executable,str(probe),str(self.root / "scripts"),str(self.draft),str(self.spec_path),str(self.context),str(packets)],capture_output=True,text=True)
        self.assert_invalid(run)
        self.assertFalse((packets / "session_token.json").exists())

    def test_actual_length_limits_only_and_id_integrity(self):
        run=self.command("lint.py",self.draft,self.spec_path)
        self.assertEqual(run.returncode,0,run.stdout)
        self.assertNotIn("80%",run.stdout)
        self.spec["questions"]["1"]["min"]=100
        self.spec_path.write_text(json.dumps(self.spec))
        self.assertNotEqual(self.command("lint.py",self.draft,self.spec_path).returncode,0)
        self.draft.write_text("===wrong===\n글")
        self.assertNotEqual(self.command("lint.py",self.draft,self.spec_path).returncode,0)

    def test_invalid_scope_metadata_is_controlled_error(self):
        for axes in (None, [], ["A",["B"]], ["A","A"]):
            with self.subTest(axes=axes):
                data=copy.deepcopy(self.spec);data["questions"]["1"]["applicable_axes"]=axes
                with self.assertRaises(ContractError):validate_spec(data,{"1":BODY},True)
        data=copy.deepcopy(self.spec);data["questions"]["1"]["min"]=None
        validate_spec(data,{"1":BODY},True)

    def test_explicit_ban_and_zero_max_always_apply(self):
        result=lint.check("1","연구실에서 확인했습니다.",{"max":100},["연구실"],[],"ACADEMIC_RND_PERMISSIVE")
        self.assertTrue(any(issue.startswith("FAIL") for issue in result["issues"]))
        result=lint.check("1","글",{"max":0},[],[])
        self.assertTrue(any(issue.startswith("FAIL") for issue in result["issues"]))

    def test_euckr_uses_actual_encoding_and_rejects_unencodable_text(self):
        actual,_,_,_=lint.count_metrics("똠","bytes_euckr")
        self.assertEqual(actual,len("똠".encode("euc-kr")))
        result=lint.check("1","똠",{"max":2,"length_metric_type":"bytes_euckr"},[],[])
        self.assertTrue(any(issue.startswith("FAIL") for issue in result["issues"]))
        result=lint.check("1","😀",{"max":100,"length_metric_type":"bytes_euckr"},[],[])
        self.assertTrue(any(issue.startswith("FAIL") for issue in result["issues"]))

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(ContractError):
            parse_json('{"scores":{"A":1,"A":5}}')

    def test_meaning_reversal_quote_and_negated_promise(self):
        self.assertFalse(verify_quote_fuzzy("서버는 요청 중복 처리를 차단해 데이터 무결성을 보장한다","서버는 요청 중복 처리를 허용해 데이터 무결성을 보장한다"))
        flags,_=audit_knockout_gatekeeper({}, {}, "코어를 재작성하지 않겠습니다.")
        self.assertFalse(flags)

    def test_current_notion_and_local_scope(self):
        result=SmartIngestionRouter.route_input("https://app.notion.com/p/abc?source=copy_link",True)
        self.assertEqual(result["next_action"],"READ_NOTION_PAGE_AND_CLASSIFY")
        result=SmartIngestionRouter.route_input("--local https://notion.so/abc",True)
        self.assertEqual(result["next_action"],"LOCAL_NEEDS_PAGE_EXPORT")
        result=SmartIngestionRouter.route_input("카카오뱅크 자소서 봐줘",True)
        self.assertEqual(result["company"],"카카오뱅크")
        result=SmartIngestionRouter.route_input("jaso-pipeline 스킬을 검증하고 다듬어봐 https://app.notion.com/p/abc",True)
        self.assertEqual(result["next_action"],"REVIEW_SKILL_WITHOUT_RUNNING_APPLICATION_PIPELINE")


if __name__ == "__main__":
    unittest.main()
