#!/usr/bin/env python3
"""자소서 E2E 원클릭 파이프라인 드라이버 (run_pipeline.py v3.4).
Local-First Sovereign Architecture:
오프라인 환경에서도 로컬 파일만으로 100% 자립 완결되며,
Step 4(기계 린트) ➔ Step 5(평가 패킷 생성 or 2인 채점 집계) ➔ 최종 리포트 출력을 단번에 체이닝합니다.
"""

import sys, os, json, subprocess, argparse, re, time, uuid
from datetime import datetime
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

def compute_file_hash(path):
    """파일 내용의 SHA-256 해시 앞 16자리 계산 (공백 정규화)"""
    try:
        content = Path(path).read_text(encoding="utf-8").strip()
        import hashlib
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return None

def verify_evaluation_integrity(hr_eval_path, tech_eval_path, draft_path, allow_mismatch=False):
    """Draft Content Hash Lock: 초안 내용 변경 시 과거 평가 캐시 재사용 Hard Fail"""
    for eval_name, eval_path in [("HR 평가", hr_eval_path), ("Tech Lead 평가", tech_eval_path)]:
        if not eval_path.exists():
            print(f"❌ [에러] {eval_name} 파일이 존재하지 않습니다: {eval_path}")
            sys.exit(1)

    current_draft_hash = compute_file_hash(draft_path)

    # 1. 평가 파일과 동일 디렉토리 또는 상위 디렉토리의 session_token.json 탐색
    token_candidates = [
        hr_eval_path.parent / "session_token.json",
        hr_eval_path.parent.parent / "session_token.json",
        tech_eval_path.parent / "session_token.json"
    ]
    token_data = None
    for cand in token_candidates:
        if cand.exists():
            try:
                token_data = json.loads(cand.read_text(encoding="utf-8"))
                break
            except Exception:
                pass

    if token_data and "draft_hash" in token_data:
        saved_hash = token_data["draft_hash"]
        if saved_hash and current_draft_hash and saved_hash != current_draft_hash:
            if allow_mismatch:
                print(f"⚠️ [DRAFT HASH MISMATCH ALLOWED] 초안 본문 해시 불일치({saved_hash} != {current_draft_hash})가 --allow-stale에 의해 허용되었습니다.")
            else:
                print("=" * 60)
                print("❌ [DRAFT CONTENT MISMATCH] 초안 본문 변경 감지! 과거 평가 재사용 차단")
                print(f"   • 평가 당시 초안 해시: {saved_hash}")
                print(f"   • 현재 대상 초안 해시: {current_draft_hash}")
                print("   🚨 초안 내용이 수정되었으나, 이전 초안으로 채점된 과거 평가 JSON을 재사용하려 했습니다.")
                print("   [해결책]:")
                print("   1. 수정된 초안에 맞추어 독립 채점 서브에이전트(Step 5)를 새로 실행하십시오.")
                print("   2. 단순 디버깅 및 회고 목적이라면 --allow-stale 플래그를 명시하십시오.")
                print("=" * 60)
                sys.exit(1)
        else:
            print(f"🔒 [Draft Hash Verified] 초안 본문 무결성 확인 완료 (Hash: {current_draft_hash})")

    # 2. 24시간 이상 경과 안내 (정보성 알림, Hard Fail 아님)
    now = time.time()
    hr_age = now - os.path.getmtime(hr_eval_path)
    if hr_age > 86400:
        print(f"ℹ️ [INFO] 평가 파일이 생성된 지 24시간 이상 경과했습니다 ({int(hr_age // 3600)}시간 전 생성).")

SENIORITY_RUBRIC_MATRIX = {
    "CONVERTIBLE_INTERN": {
        "track_name": "채용연계형 인턴",
        "evaluation_directive": (
            "[공식 채용 트랙 공학 평가 헌법 (Seniority Tier: CONVERTIBLE_INTERN)]\n"
            "1. 본 평가는 [채용연계형 인턴] 전형입니다.\n"
            "2. 축 C는 인턴 지원자가 수행한 범위와 확인된 결과로, 축 D는 공고 과업과의 관련성으로 평가하십시오. 실험·정량 지표는 실제 주장에 필요할 때 확인하십시오.\n"
            "3. 부당 감점 금지: 상용 임베디드 저수준 HAL 드라이버 직접 설계나 실차 양산 릴리즈 등 경력직 전용 요건은 본 전형의 감점 사유가 아니며, 이를 이유로 감점할 시 사법 감사에서 기각됩니다."
        )
    },
    "NEW_GRAD": {
        "track_name": "신입 공채",
        "evaluation_directive": (
            "[공식 채용 트랙 공학 평가 헌법 (Seniority Tier: NEW_GRAD)]\n"
            "1. 본 평가는 [신입 공채] 전형입니다.\n"
            "2. 축 C는 본인이 맡은 범위의 수행과 확인된 결과로, 축 D는 공고의 핵심 과업과의 관련성으로 평가하십시오. 특정 프로젝트 수나 완수 방식을 필수 조건으로 두지 마십시오."
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
    parser.add_argument("--run-id", help="실행 격리 세션 ID (선택, 미지정 시 타임스탬프+UUID 기반 자동 생성)")
    parser.add_argument("--out-packets-dir", help="평가 패킷 저장 폴더 (선택, 기본: scratch/runs/<run_id>/packets)")
    parser.add_argument("--allow-stale", action="store_true", help="오래된(5분 초과) 평가 캐시 파일 재사용 허용 (디버깅용)")
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

    # 세션 격리 ID 및 패킷 디렉토리 설정 (Session Isolation)
    run_id = args.run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    if args.out_packets_dir:
        packets_dir = Path(args.out_packets_dir).resolve()
    else:
        packets_dir = BASE_DIR / "scratch" / "runs" / run_id / "packets"

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

    # 평가 JSON이 없는 경우: 평가 에이전트용 패킷 자동 생성 (Session Isolation: 유니크 격리 폴더)
    if not (args.hr_eval and args.tech_eval):
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

        # 0. Session Run Token 생성 (격리 메타데이터)
        token_path = packets_dir / "session_token.json"
        draft_hash = compute_file_hash(draft_path)
        spec_hash = compute_file_hash(spec_path)
        token_data = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(),
            "timestamp": time.time(),
            "draft_hash": draft_hash,
            "spec_hash": spec_hash,
            "draft_file": str(draft_path),
            "spec_file": str(spec_path),
            "context_file": str(context_path) if context_path else None
        }
        token_path.write_text(json.dumps(token_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 1. HR Packet
        hr_packet_path = packets_dir / "hr_prompt_packet.txt"
        hr_prompt = f"""당신은 인사담당자(HR Talent Acquisition Lead)로서 완전히 독립된 블라인드 평가를 수행합니다.
작성 대화 맥락, 이전 피드백, AI 메모리는 일체 배제하고 오직 주어진 텍스트와 지침만으로 평가하십시오.

[세션 격리 토큰 (Session Run ID)]: {run_id}
[초안 본문 해시 (Draft Hash Lock)]: {draft_hash}

[평가 대상 공고 및 문항 스펙]
{json.dumps(merged_spec, ensure_ascii=False, indent=2)}

[HR 전용 평가 축 및 루브릭 (references/rubric_hr.json)]
{hr_rubric}

[서술 평가 범위]\n경험 서술은 배경 S를 짧게 하고 과제 T와 판단·행동 A를 중심에 두었는지 평가하십시오. 과도한 배경은 지적하되 T·A의 고민·원리·선택 이유를 배경으로 오인하지 마십시오. 첫 문단 길이만으로 S 비중을 판정하거나 고정 문장 길이·감정 억제·실패 서사를 요구하지 마십시오.\n\n[지원서 본문 텍스트]
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
작성 대화 맥락을 제외하고, 문항의 요구와 본문 주장의 기술적 근거를 독립적으로 평가하십시오.

[세션 격리 토큰 (Session Run ID)]: {run_id}
[초안 본문 해시 (Draft Hash Lock)]: {draft_hash}

[현업 테크 리드 레드팀 평가 원칙]
1. 칭찬 및 무비판적 만점 부여 절대 금지. 실전 시스템 관점에서 '왜 이 구현이 불합격인가'를 3단계 'So What?'으로 날카롭게 추궁할 것.
2. 고정 서사 강제 금지: 유형 선언, 버린 대안, 첫 실패, 저수준 조사, 감정의 강도를 점수 조건으로 삼지 마십시오. 문항과 본문이 주장한 판단의 근거를 평가하십시오.
3. 축 C 수행 범위와 결과: 본인의 역할·행동·확인된 결과와 한계가 연결되는지 평가하십시오. 특정 배포·자동화·정량 지표를 필수 결말로 요구하지 마십시오.
4. 축 H CS Safe Harbor & 축 J 근거 무결성: 지원자 본인만의 구체적 문제 현상, 재현 조건, 시스템 내부 동작 원리(OS/네트워크/DB/런타임/렌더링 등) 기반의 대체 불가능한 실전 팩트 서술 시 회사 고유명사 없어도 H축 5점 보장 (단, 단순 교과서 이론 나열 제외). 측정 근거 없는 가짜 수치 날조나 본문 내 서사 모순은 J축에서 단호히 감점하되, 사소한 오탈자 1~2개는 단순 교정 권고(INFO)로 처리하여 서사 모순 비약을 금지함.
5. 담당업무 우선순위(Key Responsibilities) 정합도: 공고의 담당업무는 상단 순서(Top-Heavy)가 기본 Core Mission입니다. 지원자가 상위 1~2순위 핵심 코어 업무(또는 Layer 2/3 시스템 치명도 직결 과업)를 외면하고 3순위 이하 곁다리 업무에만 치중한 경우 D축을 Max 3점으로 엄격히 캡핑하십시오.

{seniority_block}

[공식 부서 맥락 및 공고 스펙]
{json.dumps(merged_spec, ensure_ascii=False, indent=2)}

[현업 테크 리드 전용 루브릭 (references/rubric_tech.json - 문항과 주장에 따른 평가)]
{tech_rubric}

[서술 평가 범위]\n경험 서술은 배경 S를 짧게 하고 과제 T와 판단·행동 A를 중심에 두었는지 평가하십시오. 과도한 배경은 지적하되 T·A의 고민·원리·선택 이유를 배경으로 오인하지 마십시오. 첫 문단 길이만으로 S 비중을 판정하거나 고정 문장 길이·감정 억제·실패 서사를 요구하지 마십시오.\n\n[지원서 본문 텍스트]
{draft_content}

[출력 요구사항]
반드시 순수 JSON 포맷만을 출력하거나 tech_eval.json 파일에 저장하십시오:
{{
  "evaluator": "TECH",
  "questions": {{
    "1": {{
      "scores": {{"B": 5, "C": 5, "D": 5, "H": 5, "J": 5}},
      "critique": "문항과 본문 주장에 대한 기술적 소견",
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
(※ quotes 배열에는 반드시 본문에 실존하는 문장만 넣으십시오.)
"""
        tech_packet_path.write_text(tech_prompt, encoding="utf-8")

        print("\n" + "=" * 60)
        print(f"📋 [Step 5] 2인 독립 평가 패킷 생성 완료 (Session Run ID: {run_id})")
        print("=" * 60)
        print(f"👉 격리 세션 디렉토리: {packets_dir.parent}")
        print(f"👉 HR 평가 프롬프트 패킷: {hr_packet_path}")
        print(f"👉 Tech 평가 프롬프트 패킷: {tech_packet_path}")
        print(f"👉 세션 토큰 메타데이터: {token_path}")
        print("\n[다음 안내]: 서브에이전트 또는 평가 모델에 위 두 패킷을 각각 입력하여 hr_eval.json과 tech_eval.json을 획득하십시오.")
        print("그 후 아래 명령어로 최종 채점 리포트를 실행하십시오 (Draft Content Hash Lock 검증):")
        print(f"python3 {__file__} {args.draft} {args.spec} --hr-eval <hr_eval.json> --tech-eval <tech_eval.json> [--out <report.md>]")
        return

    # 두 평가 JSON이 모두 제공된 경우: Draft Content Hash Lock 및 grade.py 즉시 실행
    hr_eval_path = Path(args.hr_eval).resolve()
    tech_eval_path = Path(args.tech_eval).resolve()

    # Draft Content Hash Lock 검증 (초안 내용 변경 시 과거 평가 재사용 차단)
    verify_evaluation_integrity(hr_eval_path, tech_eval_path, draft_path, allow_mismatch=args.allow_stale)

    print("\n" + "=" * 60)
    print("📊 [Step 5] grade.py 결정론적 기계 채점 및 감사 시작")
    print("=" * 60)

    grade_script = SCRIPTS_DIR / "grade.py"
    grade_cmd = [
        sys.executable, str(grade_script),
        str(draft_path), str(hr_eval_path), str(tech_eval_path),
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
