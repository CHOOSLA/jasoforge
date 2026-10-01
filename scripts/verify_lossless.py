#!/usr/bin/env python3
"""
JasoForge SKILL.md Lossless Refactoring Verification Engine
===========================================================
Checks active operational invariants and syntax. User-retired writing rules are not invariants.
"""

import sys
from pathlib import Path

REQUIRED_INVARIANTS = [
    ("공고·문항 규격", "spec.json"),
    ("회사·직무 맥락", "context.json"),
    ("문항별 초안", "draft.json"),
    ("기계 규격 검사", "lint.py"),
    ("인용·평가 집계", "grade.py"),
    ("로컬 자립", "로컬 자립"),
    ("경험 원장", "경험"),
    ("노션 경로", "Notion"),
    ("변경 추적", "변경 로그"),
    ("세션 실행 격리", "Session_Isolation_And_Unique_Run_Dir_Contract"),
    ("초안 해시 잠금", "Draft_Content_Hash_Lock_Contract"),
    ("문항 분할", "Draft_Segmentation_Assertion_Contract"),
    ("의미와 증거 계약", "Semantic_Evidence_Contract"),
]

def verify_file(skill_path: Path) -> bool:
    if not skill_path.exists():
        print(f"❌ Error: {skill_path} does not exist.")
        return False

    content = skill_path.read_text(encoding="utf-8")
    missing = []

    print(f"🔍 [Tier 1: Document Invariants] Verifying {skill_path.name} against {len(REQUIRED_INVARIANTS)} core invariants...")
    
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
        print(f"🎉 ACTIVE INVARIANTS PASS: All {len(REQUIRED_INVARIANTS)} invariants are fully preserved!")
        return True

def verify_python_scripts(scripts_dir: Path) -> bool:
    import py_compile
    print(f"\n🔍 [Tier 2: Python Syntax Audit] Compiling all python scripts in {scripts_dir.name}...")
    py_files = sorted(list(scripts_dir.glob("*.py")))
    if not py_files:
        print("   ⚠️ No python files found.")
        return True
    
    all_passed = True
    for py_file in py_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
            print(f"   ✅ Syntax Valid: {py_file.name}")
        except py_compile.PyCompileError as e:
            print(f"   ❌ Syntax Error in {py_file.name}: {e}")
            all_passed = False
    return all_passed

def verify_json_schemas(root_dir: Path) -> bool:
    import json
    print(f"\n🔍 [Tier 3: JSON Integrity Audit] Validating JSON schemas in references/...")
    ref_dir = root_dir / "references"
    json_files = sorted(list(ref_dir.glob("*.json"))) if ref_dir.exists() else []
    
    all_passed = True
    for j_file in json_files:
        try:
            data = json.loads(j_file.read_text(encoding="utf-8"))
            print(f"   ✅ JSON Valid: {j_file.name} (keys: {len(data) if isinstance(data, dict) else len(data)})")
        except Exception as e:
            print(f"   ❌ Invalid JSON in {j_file.name}: {e}")
            all_passed = False
    return all_passed

if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent.parent
    target = root_dir / "SKILL.md"
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    
    t1 = verify_file(target)
    t2 = verify_python_scripts(root_dir / "scripts")
    t3 = verify_json_schemas(root_dir)

    overall_success = t1 and t2 and t3
    print("\n" + "=" * 60)
    if overall_success:
        print("🚀 [JasoForge Multi-Tier Static Verification Engine] ALL TIERS 100% PASSED!")
    else:
        print("💥 [JasoForge Multi-Tier Static Verification Engine] VERIFICATION FAILED!")
    print("=" * 60)
    sys.exit(0 if overall_success else 1)
