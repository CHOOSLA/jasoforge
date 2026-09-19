#!/usr/bin/env python3
"""자소서 E2E 원클릭 파이프라인 드라이버 (run_pipeline.py v3.4).
Local-First Sovereign Architecture:
오프라인 환경에서도 로컬 파일만으로 100% 자립 완결되며,
Step 4(기계 린트) ➔ Step 5(평가 패킷 생성 or 2인 채점 집계) ➔ 최종 리포트 출력을 단번에 체이닝합니다.
"""

import sys, os, json, subprocess, argparse, re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
REFS_DIR = BASE_DIR / "references"

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

JUDICIAL_STEERING_PATTERNS = [
    r'(감점하지\s*말|부당하게\s*요구하지|평가할\s*것|높이\s*평가|최우선으로\s*평가)',
    r'(인정할\s*것|봐줘|유효하게\s*연결|우대할|면제할|잣대를\s*들이대지)',
    r'(평가\s*헌법|인재상으로\s*인정|높은\s*평가를\s*줄)'
]

def audit_context_integrity(context_data):
    """context.json 내 평가 지침 및 사법 사주 오염을 기계적으로 적발"""
    raw_str = json.dumps(context_data, ensure_ascii=False)
    for pat in JUDICIAL_STEERING_PATTERNS:
        m = re.search(pat, raw_str)
        if m:
            print(f"❌ [CRITICAL CONTEXT CONTAMINATION] context.json 내 사법 사주 오염 문구 적발: '{m.group(0)}'")
            print("도메인 컨텍스트에는 순수 시스템 기술 팩트와 정형 Enum만 허용됩니다.")
            print("평가 지침이나 면제 사주는 엄격히 금지됩니다. 파이프라인을 중단합니다.")
            sys.exit(1)

SENIORITY_RUBRIC_MATRIX = {
    "CONVERTIBLE_INTERN": {
        "track_name": "채용연계형 인턴",
        "evaluation_directive": (
            "[공식 채용 트랙 공학 평가 헌법 (Seniority Tier: CONVERTIBLE_INTERN)]\n"
            "1. 본 평가는 [채용연계형 인턴] 전형입니다.\n"
            "2. 축 C/D 평가 기준: 가설-검증 기반 원인 좁히기 규율(대조군 설정, 정량 지표 개선 등)과 공고 최상위 1순위 과업 정합 시 5점을 인정하십시오.\n"
            "3. 부당 감점 금지: 상용 임베디드 저수준 HAL 드라이버 직접 설계나 실차 양산 릴리즈 등 경력직 전용 요건은 본 전형의 감점 사유가 아니며, 이를 이유로 감점할 시 사법 감사에서 기각됩니다."
        )
    },
    "NEW_GRAD": {
        "track_name": "신입 공채",
        "evaluation_directive": (
            "[공식 채용 트랙 공학 평가 헌법 (Seniority Tier: NEW_GRAD)]\n"
            "1. 본 평가는 [신입 공채] 전형입니다.\n"
            "2. 축 C/D 평가 기준: 단일 완성 프로젝트 아키텍처 및 신입 5대 완수 앵커(실사용자 배포, 자원 제약 극복, Linter/CI 도구화 등)와 최상위 1~2순위 코어 과업 정합 시 5점을 인정하십시오."
        )
    },
    "EXPERIENCED": {
        "track_name": "경력직",
        "evaluation_directive": (
            "[공식 채용 트랙 공학 평가 헌법 (Seniority Tier: EXPERIENCED)]\n"
            "1. 본 평가는 [경력직] 전형입니다.\n"
            "2. 축 C/D 평가 기준: 상용 프로덕션 대규모 트래픽 무중단 운영, 아키텍처 전면 설계, 비즈니스 장애 완수 리스크 책임을 엄격하게 검증하십시오."
        )
    }
}

def main():
    parser = argparse.ArgumentParser(description="jaso-pipeline v3.7 E2E 원클릭 드라이버")
    parser.add_argument("draft", help="초안 텍스트 파일 (===1=== 구분자)")
    parser.add_argument("spec", help="공고 규격 JSON 파일 (references/spec_example.json)")
    parser.add_argument("--context", help="기업/직무 컨텍스트 JSON 파일 (선택, 미지정 시 spec/draft 부모 폴더 자동 탐색)")
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

    # context.json 탐색 및 로드 (명시 인자 우선, 없으면 spec 또는 draft 동위 폴더 자동 감지)
    context_path = None
    if args.context:
        context_path = Path(args.context).resolve()
    else:
        cand1 = spec_path.parent / "context.json"
        cand2 = draft_path.parent / "context.json"
        if cand1.exists():
            context_path = cand1
        elif cand2.exists():
            context_path = cand2

    context_data = {}
    if context_path and context_path.exists():
        try:
            context_data = json.loads(context_path.read_text(encoding="utf-8"))
            print(f"📦 [Context Auto-Merge] 컨텍스트 파일 감지 및 병합: {context_path.name}")
            audit_context_integrity(context_data)
        except Exception as e:
            print(f"⚠️ [주의] context.json 로드 실패: {e}")

    print("=" * 60)
    print("🚀 [Step 4] lint.py v3.4 기계 린터 결정적 검증 시작")
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

        # Deep Merge: context_data를 바탕에 두고 spec_data로 정밀 융합
        merged_spec = dict(context_data)
        for k, v in spec_data.items():
            if k in merged_spec and isinstance(merged_spec[k], dict) and isinstance(v, dict):
                merged_spec[k].update(v)
            else:
                merged_spec[k] = v

        hr_rubric = (REFS_DIR / "rubric_hr.json").read_text(encoding="utf-8")
        tech_rubric = (REFS_DIR / "rubric_tech.json").read_text(encoding="utf-8")

        # 1. HR Packet
        hr_packet_path = packets_dir / "hr_prompt_packet.txt"
        hr_prompt = f"""당신은 인사담당자(HR Talent Acquisition Lead)로서 완전히 독립된 블라인드 평가를 수행합니다.
작성 대화 맥락, 이전 피드백, AI 메모리는 일체 배제하고 오직 주어진 텍스트와 지침만으로 평가하십시오.

[평가 대상 공고 및 문항 스펙]
{json.dumps(merged_spec, ensure_ascii=False, indent=2)}

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
        recruitment_track = merged_spec.get("recruitment_track_type", "NEW_GRAD")
        seniority_entry = SENIORITY_RUBRIC_MATRIX.get(recruitment_track, SENIORITY_RUBRIC_MATRIX["NEW_GRAD"])
        seniority_block = seniority_entry["evaluation_directive"]

        tech_packet_path = packets_dir / "tech_prompt_packet.txt"
        tech_prompt = f"""당신은 지원 부서의 현업 테크 리드(Principal Engineer)이자 엄격한 시니어 레드팀(Red Teamer)으로서 완전히 독립된 기술 블라인드 채점을 수행합니다.
작성 대화 맥락, 온정주의, 칭찬은 일체 배제하고, 오직 엔지니어링 진실성, 'So What?' 3단계 결함 추궁, 그리고 Typed Locked Rubric 관점에서 냉정하게 평가하십시오.

[현업 테크 리드 레드팀 평가 원칙]
1. 칭찬 및 무비판적 만점 부여 절대 금지. 실전 시스템 관점에서 '왜 이 구현이 불합격인가'를 3단계 'So What?'으로 날카롭게 추궁할 것.
2. Typed Locked Rubric 집행: 기술 프로젝트 문항은 Type_A~E 중 하나를 선언하고 필수 증거 결여 시 Max 3점 캡핑. (단, 지원동기, 포부, 인성 문항은 버린 대안 및 유형 강제 면제/EXEMPT).
3. 축 C 신입 엔지니어링 5대 완수 인정: 상용 프로덕션뿐만 아니라, ① 실사용자 배포 & 피드백 루프, ② 극한의 가용 자원 제약 환경 극복, ③ 가상 부하 및 벤치마크 스트레스 테스트, ④ 커스텀 Linter/CI 도구화, ⑤ 데이터 및 상태 불일치 무결성 선제 방어, 또는 독립 피어 검증(Star 100+ PR, 논문 등) 중 1개라도 실증되면 5점 만점 인정.
4. 축 H CS Safe Harbor & 축 J 근거 무결성: 지원자 본인만의 구체적 문제 현상, 재현 조건, 시스템 내부 동작 원리(OS/네트워크/DB/런타임/렌더링 등) 기반의 대체 불가능한 실전 팩트 서술 시 회사 고유명사 없어도 H축 5점 보장 (단, 단순 교과서 이론 나열 제외). 측정 근거 없는 가짜 수치 날조나 본문 내 서사 모순은 J축에서 단호히 감점하되, 사소한 오탈자 1~2개는 단순 교정 권고(INFO)로 처리하여 서사 모순 비약을 금지함.
5. 담당업무 우선순위(Key Responsibilities) 정합도: 공고의 담당업무는 상단 순서(Top-Heavy)가 기본 Core Mission입니다. 지원자가 상위 1~2순위 핵심 코어 업무(또는 Layer 2/3 시스템 치명도 직결 과업)를 외면하고 3순위 이하 곁다리 업무에만 치중한 경우 D축을 Max 3점으로 엄격히 캡핑하십시오.

{seniority_block}

[공식 부서 맥락 및 공고 스펙]
{json.dumps(merged_spec, ensure_ascii=False, indent=2)}

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
        "--tech-weight", str(args.tech_weight),
        "--spec", str(spec_path)
    ]
    if context_path and context_path.exists():
        grade_cmd.extend(["--context", str(context_path)])
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
