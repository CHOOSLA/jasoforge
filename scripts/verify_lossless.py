#!/usr/bin/env python3
"""
JasoForge SKILL.md Lossless Refactoring Verification Engine
===========================================================
Ensures that no constitutional rules, evaluation rubrics, probing frameworks,
or grading standards are lost during refactoring.
"""

import sys
from pathlib import Path

REQUIRED_INVARIANTS = [
    # 1. 10-Axis Rubric Constitution (A to J)
    ("A축 지면 최적화", "A. 상황 설명 비중"),
    ("A축 30% 이하 규칙", "30%"),
    ("B축 성공 경로 잠금", "B. 서사 유형별 잠금 앵커"),
    ("B축 Type_A 의사결정형", "Type_A"),
    ("B축 Type_B 심층디버깅", "Type_B"),
    ("B축 Type_C 시스템조망형", "Type_C"),
    ("B축 조각모음 나열 독소", "조각모음"),
    ("C축 상용 프로덕션 vs 샌드박스", "C. 완수 과정 & 리스크 책임"),
    ("C축 프로덕션 실전성", "상용 프로덕션"),
    ("D축 도메인 엣지케이스 직격", "D. 부서 엣지 케이스"),
    ("D축 금융 멱등성 불변식", "멱등성"),
    ("E축 질문 본질 의도 & 플로우", "E. 질문 본질 의도 & 플로우 일치"),
    ("F축 작성방법 전수 충족", "F. 작성방법 항목 전수 충족"),
    ("G축 글자수 규격 90% 이상", "G. 글자수 규격 준수"),
    ("H축 치환 불가성", "H. 고유성"),
    ("I축 가치관 행동화 및 지속성", "I. 요구 추상화 레벨 & 가치관 지속성"),
    ("J축 팩트 무결성", "J. 근거 무결성 & 서사 일관성"),

    # 2. Nonlinear Probing Framework (4 Reverse Questions)
    ("4대 역질문 프레임워크", "4대 역질문"),
    ("역질문 1: 첫 번째 헛스윙", "첫 번째 헛스윙"),
    ("역질문 2: 결정적 터닝포인트", "결정적 터닝포인트"),
    ("역질문 3: 엔지니어링 집요함", "엔지니어링 집요함"),
    ("역질문 4: 현실적 트레이드오프", "현실적 트레이드오프"),

    # 3. Scene 4 Core Elements
    ("장면 필수 4요소", "장면 필수 4요소"),
    ("장면 요소 1: 제약 조건", "제약 조건"),
    ("장면 요소 2: 버린 대안", "버린 대안"),
    ("장면 요소 3: 양자택일 판단", "양자택일"),
    ("장면 요소 4: 결과 및 리스크 책임", "관찰된 결과 & 리스크 완수 책임"),

    # 4. Dual-Agent Blind Evaluation Protocol
    ("컨텍스트 완전 격리", "컨텍스트 완전 격리"),
    ("HR 평가자 40%", "HR 인사담당자"),
    ("테크 리드 평가자 60%", "현업 테크 리드"),
    ("1~5점 앵커 정수 채점", "1~5점"),
    ("환각 인용 롤백 엔진", "롤백"),
    ("실전 킬러 꼬리질문 3선", "킬러 꼬리질문"),

    # 5. Deterministic Lint Rules (lint.py)
    ("기계 린트 결정적 검사", "lint.py"),
    ("키워드 충족도 0건 FAIL", "0건 FAIL"),
    ("고유명사 매크로 밀도", "고유명사 매크로 밀도"),
    ("10대 상투적 클리셰 탐지", "상투적 클리셰"),
    ("블라인드 금지어 검출", "블라인드 금지어"),
    ("문장 길이 분포 및 리듬", "문장 길이 분포"),

    # 6. Senior Red-Team Critique
    ("시니어 레드팀 3단계 추궁", "So What"),
    ("Engineering Narrative v7.0", "Engineering Narrative v7.0"),
    ("Show Don't Tell 원칙", "Show Don't Tell"),

    # 7. Dual Storage Architecture (Local-First Sovereign & Optional Notion)
    ("로컬 자립 모드", "로컬 자립"),
    ("spec.json 명세", "spec.json"),
    ("score_ledger 점수 원장", "score_ledger"),

    # 8. Smart Ingestion & Asset Lookup Architecture
    ("스마트 입력 감지 관문", "Smart Ingestion Gateway"),
    ("노션 원장 선행 조회", "Asset Lookup-First"),
    ("Audit-First 직행 플로우", "Audit-First"),

    # 9. Prosecutor-Judge Architecture & Dynamic Context Binding
    ("2단계 검사-판사 아키텍처", "Prosecutor-Judge Architecture"),
    ("동적 컨텍스트 바인딩", "동적 컨텍스트 바인딩"),
    ("5대 동적 매핑 매트릭스", "Dynamic Context Binding Matrix"),
    ("동적 페르소나 주입기", "동적 페르소나 주입기"),
]

def verify_file(skill_path: Path) -> bool:
    if not skill_path.exists():
        print(f"❌ Error: {skill_path} does not exist.")
        return False

    content = skill_path.read_text(encoding="utf-8")
    missing = []

    print(f"🔍 Verifying {skill_path.name} against {len(REQUIRED_INVARIANTS)} core invariants...")
    
    for label, keyword in REQUIRED_INVARIANTS:
        if keyword not in content:
            missing.append((label, keyword))
            print(f"   ❌ Missing: [{label}] -> '{keyword}'")
        else:
            print(f"   ✅ Verified: [{label}]")

    print("-" * 60)
    if missing:
        print(f"🚨 FAILED: {len(missing)} invariant(s) missing out of {len(REQUIRED_INVARIANTS)}!")
        for label, keyword in missing:
            print(f"   - {label} ('{keyword}')")
        return False
    else:
        print(f"🎉 100% LOSSLESS PASS: All {len(REQUIRED_INVARIANTS)} invariants are fully preserved!")
        return True

if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "SKILL.md"
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    
    success = verify_file(target)
    sys.exit(0 if success else 1)
