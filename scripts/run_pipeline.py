#!/usr/bin/env python3
"""자소서 E2E 원클릭 파이프라인 드라이버 (run_pipeline.py v2.3).
Local-First Sovereign Architecture:
오프라인 환경에서도 로컬 파일만으로 100% 자립 완결되며,
Step 4(기계 린트) ➔ Step 5(평가 패킷 생성 or 2인 채점 집계) ➔ 최종 리포트 출력을 단번에 체이닝합니다.
"""

import sys, os, json, subprocess, argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
REFS_DIR = BASE_DIR / "references"

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def main():
    parser = argparse.ArgumentParser(description="jaso-pipeline v2.3 E2E 원클릭 드라이버")
    parser.add_argument("draft", help="초안 텍스트 파일 (===1=== 구분자)")
    parser.add_argument("spec", help="공고 규격 JSON 파일 (references/spec_example.json)")
    parser.add_argument("--hr-eval", help="HR 평가 결과 JSON 파일 (선택)")
    parser.add_argument("--tech-eval", help="테크 리드 평가 결과 JSON 파일 (선택)")
    parser.add_argument("--out-packets-dir", default="scratch/packets", help="평가 패킷 저장 폴더 (기본: scratch/packets)")
    parser.add_argument("--out", help="최종 마크다운 리포트 저장 파일 (선택)")
    parser.add_argument("--hr-weight", type=float, default=0.4, help="HR 가중치 (기본: 0.4)")
    parser.add_argument("--tech-weight", type=float, default=0.6, help="테크 리드 가중치 (기본: 0.6)")
    args = parser.parse_args()

    draft_path = Path(args.draft).resolve()
    spec_path = Path(args.spec).resolve()

    if not draft_path.exists():
        print(f"❌ [에러] 초안 파일이 존재하지 않습니다: {draft_path}")
        sys.exit(1)
    if not spec_path.exists():
        print(f"❌ [에러] 스펙 파일이 존재하지 않습니다: {spec_path}")
        sys.exit(1)

    print("=" * 60)
    print("🚀 [Step 4] lint.py v2.3 기계 린터 결정적 검증 시작")
    print("=" * 60)

    lint_script = SCRIPTS_DIR / "lint.py"
    code, out, err = run_cmd([sys.executable, str(lint_script), str(draft_path), str(spec_path)])
    print(out)
    if code != 0:
        print("❌ [LINT FAIL] 기계적 규격 위반(글자수 미달/초과, 금지어 등)이 발견되었습니다.")
        print("파이프라인이 중단됩니다. 위 결함을 수정한 후 다시 실행하십시오.")
        sys.exit(code)

    print("✅ [LINT PASS] 모든 기계적 검증 통과 완료!")

    # 평가 JSON이 없는 경우: 평가 에이전트용 패킷 자동 생성
    if not (args.hr_eval and args.tech_eval):
        packets_dir = Path(args.out_packets_dir).resolve()
        packets_dir.mkdir(parents=True, exist_ok=True)

        draft_content = draft_path.read_text(encoding="utf-8")
        spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
        hr_rubric = (REFS_DIR / "rubric_hr.json").read_text(encoding="utf-8")
        tech_rubric = (REFS_DIR / "rubric_tech.json").read_text(encoding="utf-8")

        # 1. HR Packet
        hr_packet_path = packets_dir / "hr_prompt_packet.txt"
        hr_prompt = f"""당신은 인사담당자(HR Talent Acquisition Lead)로서 완전히 독립된 블라인드 평가를 수행합니다.
작성 대화 맥락, 이전 피드백, AI 메모리는 일체 배제하고 오직 주어진 텍스트와 지침만으로 평가하십시오.

[평가 대상 공고 및 문항 스펙]
{json.dumps(spec_data, ensure_ascii=False, indent=2)}

[HR 전용 평가 축 및 루브릭 (references/rubric_hr.json)]
{hr_rubric}

[지원서 본문 텍스트]
{draft_content}

[출력 요구사항]
반드시 순수 JSON 포맷만을 출력하거나 hr_eval.json 파일에 저장하십시오:
{{
  "evaluator": "HR",
  "questions": {{
    "1": {{
      "scores": {{"A": 5, "E": 5, "F": 5, "G": 5, "I": 5}},
      "critique": "감점 사유 또는 핵심 소견",
      "quotes": ["본문에서 직접 인용한 문장"]
    }}
  }},
  "overall_comment": "HR 총평 및 조직 적합성 소견"
}}
(※ quotes 배열에는 반드시 본문에 실존하는 문장만 넣으십시오.)
"""
        hr_packet_path.write_text(hr_prompt, encoding="utf-8")

        # 2. Tech Lead Packet (Red Teamer 결함 추궁 가드레일 내재화)
        tech_packet_path = packets_dir / "tech_prompt_packet.txt"
        tech_prompt = f"""당신은 지원 부서의 현업 테크 리드(Principal Engineer)이자 엄격한 시니어 레드팀(Red Teamer)으로서 완전히 독립된 기술 블라인드 채점을 수행합니다.
작성 대화 맥락, 온정주의, 칭찬은 일체 배제하고, 오직 엔지니어링 진실성, 'So What?' 3단계 결함 추궁, 그리고 Typed Locked Rubric 관점에서 냉정하게 평가하십시오.

[현업 테크 리드 레드팀 평가 원칙]
1. 칭찬 및 무비판적 만점 부여 절대 금지. 실전 시스템 관점에서 '왜 이 구현이 불합격인가'를 3단계 'So What?'으로 날카롭게 추궁할 것.
2. Typed Locked Rubric 집행: 문항별로 단 하나의 직교 서사 유형(Type_A: 의사결정형, Type_B: 심층디버깅형, Type_C: 시스템조망형, Type_D: 알고리즘최적화형, Type_E: 데이터인프라형)을 선언하고, 필수 증거가 누락되었거나 Negative Boundary에 저촉되면 예외 없이 Max 3점으로 감점할 것.
3. 축 C 상용 프로덕션 실전성 vs 독립 피어 검증: 단순 과제/수업 프로젝트는 Max 3점 캡핑. 실제 트래픽/장애 책임 또는 독립 제3자 공인 피어 검증(스타 100+ 오픈소스 머지 PR, 학술 논문 등재, 공인 벤치마크 SOTA, 실전 SLA/유료 고객 지표) 통과 시에만 5점 인정.
4. 근거 무결성 및 서사 모순 감사: 가짜 수치, 또는 "디테일을 챙긴다"고 공언하고 본문에 오탈자를 방치한 서사 모순 발견 시 J축에서 단호히 감점할 것.

[공식 부서 맥락 및 공고 스펙]
{json.dumps(spec_data, ensure_ascii=False, indent=2)}

[현업 테크 리드 전용 루브릭 (references/rubric_tech.json - Typed Locked Rubric Gating)]
{tech_rubric}

[지원서 본문 텍스트]
{draft_content}

[출력 요구사항]
반드시 순수 JSON 포맷만을 출력하거나 tech_eval.json 파일에 저장하십시오:
{{
  "evaluator": "TECH",
  "questions": {{
    "1": {{
      "scores": {{"B": 5, "C": 5, "D": 5, "H": 5, "J": 5}},
      "type_declaration": {{
        "selected_type": "Type_A | Type_B | Type_C | Type_D | Type_E",
        "justification": "해당 서사 유형을 선택한 명확한 기술적 근거",
        "must_have_evidence_found": "본문에서 발췌한 필수 증거 인용문",
        "negative_boundary_violated": false
      }},
      "critique": "기술적 소견 (선택된 유형의 Locked Rubric 기준)",
      "quotes": ["본문에서 직접 인용한 문장"]
    }}
  }},
  "killer_followup_questions": [
    {{
      "question": "실전 기술면접 킬러 꼬리질문 1",
      "intent": "질문의 취약점 의도",
      "recommended_defense": "지원자 추천 방어 전략"
    }}
  ],
  "overall_comment": "현업 테크 리드 총평 및 면접 방어 가능성 소견"
}}
(※ selected_type은 반드시 Type_A, Type_B, Type_C, Type_D, Type_E 중 단 하나만 선언하십시오. 복수 유형 혼합 시 기계 감사에서 강제 캡핑됩니다.)
(※ quotes 배열에는 반드시 본문에 실존하는 문장만 넣으십시오.)
"""
        tech_packet_path.write_text(tech_prompt, encoding="utf-8")

        print("\n" + "=" * 60)
        print("📋 [Step 5] 2인 독립 평가 패킷 생성 완료")
        print("=" * 60)
        print(f"👉 HR 평가 프롬프트 패킷: {hr_packet_path}")
        print(f"👉 Tech 평가 프롬프트 패킷: {tech_packet_path}")
        print("\n[다음 안내]: 서브에이전트 또는 평가 모델에 위 두 패킷을 각각 입력하여 hr_eval.json과 tech_eval.json을 획득하십시오.")
        print("그 후 아래 명령어로 최종 채점 리포트를 실행하십시오:")
        print(f"python3 {__file__} {args.draft} {args.spec} --hr-eval <hr_eval.json> --tech-eval <tech_eval.json> [--out <report.md>]")
        return

    # 두 평가 JSON이 모두 제공된 경우: grade.py 즉시 실행
    print("\n" + "=" * 60)
    print("📊 [Step 5] grade.py 결정론적 기계 채점 및 감사 시작")
    print("=" * 60)

    grade_script = SCRIPTS_DIR / "grade.py"
    grade_cmd = [
        sys.executable, str(grade_script),
        str(draft_path), str(args.hr_eval), str(args.tech_eval),
        "--hr-weight", str(args.hr_weight),
        "--tech-weight", str(args.tech_weight)
    ]
    if args.out:
        grade_cmd.extend(["--out", str(args.out)])

    code, out, err = run_cmd(grade_cmd)
    print(out)
    if code != 0:
        print(f"❌ [에러] 채점 집계 중 결함 발생: {err}")
        sys.exit(code)

    print("=" * 60)
    print("🎉 [SUCCESS] jaso-pipeline E2E 실행 완료!")
    if args.out:
        print(f"📄 최종 검증 리포트: {Path(args.out).resolve()}")
    print("=" * 60)

if __name__ == "__main__":
    main()
