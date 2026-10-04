#!/usr/bin/env python3
"""
JasoForge Sovereign Skill Installer & Multi-Platform Deployer
============================================================
Zero-dependency, cross-platform installer for JasoForge.
Automatically detects active runtime environments and installs to:
  - Universal Agents: ~/.agents/skills/jaso-pipeline
  - Claude Code:      ~/.claude/skills/jaso-pipeline (only if Claude is present)
  - Gemini / AGY:     ~/.gemini/config/skills/jaso-pipeline (only if Gemini is present)

Usage:
  python3 installer.py [--target {auto,all,agents,claude,gemini}] [--symlink] [--dry-run]
"""

import os
import sys
import shutil
import argparse
import platform
import time
import subprocess
from pathlib import Path

VERSION = "5.0.0"
SKILL_NAME = "jaso-pipeline"

# ANSI Terminal Colors
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
GREEN = "\033[32m" if USE_COLOR else ""
CYAN = "\033[36m" if USE_COLOR else ""
YELLOW = "\033[33m" if USE_COLOR else ""
RED = "\033[31m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
DIM = "\033[2m" if USE_COLOR else ""
RESET = "\033[0m" if USE_COLOR else ""

def get_target_paths():
    home = Path.home()
    return {
        "Universal Agents": home / ".agents" / "skills" / SKILL_NAME,
        "Claude Code":      home / ".claude" / "skills" / SKILL_NAME,
        "Gemini CLI / AGY": home / ".gemini" / "config" / "skills" / SKILL_NAME,
    }

def is_runtime_present(target_name: str) -> bool:
    """Check if the target runtime actually exists on the system."""
    home = Path.home()
    if "Claude" in target_name:
        return (home / ".claude").exists() or shutil.which("claude") is not None
    elif "Gemini" in target_name:
        return (home / ".gemini").exists() or shutil.which("gemini") is not None or shutil.which("agy") is not None
    elif "Agents" in target_name:
        return (home / ".agents").exists()
    return False

def verify_source(source_dir: Path) -> bool:
    required_files = [
        source_dir / "SKILL.md",
        source_dir / "scripts" / "lint.py",
        source_dir / "scripts" / "grade.py",
        source_dir / "scripts" / "evaluation_contract.py",
        source_dir / "scripts" / "run_pipeline.py",
        source_dir / "scripts" / "record_review.py",
        source_dir / "references" / "workflow-storage.md",
        source_dir / "references" / "research-context.md",
        source_dir / "references" / "diagnostic-report.md",
        source_dir / "references" / "migration.md",
        source_dir / "references" / "rubric_hr.json",
        source_dir / "references" / "question-flows.md",
        source_dir / "references" / "rubric_tech.json",
    ]
    for rf in required_files:
        if not rf.exists():
            print(f"{RED}error:{RESET} required file missing in source: {rf}")
            return False
    return True

def install_target(source_dir: Path, target_path: Path, use_symlink: bool = False, dry_run: bool = False):
    # Self-target defense
    if source_dir.resolve() == target_path.resolve():
        return "source"

    if dry_run:
        return "dry-run"

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean existing target
    if target_path.is_symlink() or target_path.exists():
        if target_path.is_symlink() or target_path.is_file():
            target_path.unlink()
        elif target_path.is_dir():
            shutil.rmtree(target_path)

    if use_symlink:
        try:
            target_path.symlink_to(source_dir.resolve(), target_is_directory=True)
            return "symlinked"
        except Exception:
            pass

    # Copy clean files
    shutil.copytree(
        source_dir,
        target_path,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git*", ".DS_Store", "scratch", "dist")
    )
    return "copied"

def run_self_test(target_path: Path) -> bool:
    lint_script = target_path / "scripts" / "lint.py"
    if not lint_script.exists():
        return False
    
    try:
        res = subprocess.run(
            [sys.executable, str(lint_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        return "사용법" in res.stdout or "lint.py" in res.stdout or "사용법" in res.stderr
    except Exception:
        return False

def main():
    start_time = time.time()
    parser = argparse.ArgumentParser(description="JasoForge Sovereign Multi-Target Installer")
    parser.add_argument(
        "--target",
        choices=["auto", "all", "agents", "claude", "gemini"],
        default="auto",
        help="Target runtime environment (default: auto)"
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Create symbolic links instead of copying files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate installation without modifying disk"
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Source directory containing JasoForge skill files"
    )

    args = parser.parse_args()

    # Clean, professional header (inspired by uv/cargo/skills.sh)
    sys_info = f"{platform.system().lower()}-{platform.machine().lower()}"
    print(f"{BOLD}jasoforge {VERSION}{RESET} ({sys_info}, python {platform.python_version()})")

    source_dir = Path(args.source) if args.source else Path(__file__).resolve().parent
    if not verify_source(source_dir):
        sys.exit(1)

    all_targets = get_target_paths()

    # Determine targets to install
    selected_targets = []
    skipped_targets = []

    if args.target == "auto":
        for name, path in all_targets.items():
            if is_runtime_present(name):
                selected_targets.append((name, path))
            else:
                skipped_targets.append(name)
        if not selected_targets:
            selected_targets = [("Universal Agents", all_targets["Universal Agents"])]
    elif args.target == "all":
        selected_targets = list(all_targets.items())
    else:
        # map short name
        name_map = {
            "agents": "Universal Agents",
            "claude": "Claude Code",
            "gemini": "Gemini CLI / AGY"
        }
        t_name = name_map.get(args.target, args.target)
        selected_targets = [(t_name, all_targets[t_name])]

    print(f"\n{BOLD}Resolving runtime environments...{RESET}")
    for name, path in selected_targets:
        is_src = source_dir.resolve() == path.resolve()
        status_suffix = f" {DIM}[active source]{RESET}" if is_src else ""
        print(f"  {GREEN}✓{RESET} {name:<18} {DIM}{path}{RESET}{status_suffix}")

    for name in skipped_targets:
        print(f"  {DIM}- {name:<18} (runtime not detected, skipped){RESET}")

    print(f"\n{BOLD}Verifying skill artifacts...{RESET}")
    artifacts = [
        ("Deterministic Lint Engine", "scripts/lint.py"),
        ("Review Contract Aggregator", "scripts/grade.py"),
        ("Review Packet Builder", "scripts/run_pipeline.py"),
        ("Evidence Review Rubrics", "references/rubric_tech.json"),
        ("Validated Review Ledger", "scripts/record_review.py"),
        ("Agent Workflow", "SKILL.md"),
    ]
    for label, rel_path in artifacts:
        f_exists = (source_dir / rel_path).exists()
        symbol = f"{GREEN}✓{RESET}" if f_exists else f"{RED}✗{RESET}"
        print(f"  {symbol} {label:<26} {DIM}({rel_path}){RESET}")

    success_count = 0
    skipped_source_count = 0

    for name, path in selected_targets:
        status = install_target(source_dir, path, use_symlink=args.symlink, dry_run=args.dry_run)
        if status == "source":
            skipped_source_count += 1
        else:
            if not args.dry_run:
                run_self_test(path)
            success_count += 1

    elapsed_ms = int((time.time() - start_time) * 1000)
    summary_parts = []
    if success_count > 0:
        summary_parts.append(f"{success_count} would install" if args.dry_run else f"{success_count} installed")
    if skipped_source_count > 0:
        summary_parts.append(f"{skipped_source_count} source preserved")

    summary_str = ", ".join(summary_parts) if summary_parts else "up to date"
    print(f"\n{GREEN}Completed in {elapsed_ms}ms{RESET} ({summary_str}).")
    print(f"\n{BOLD}Next steps:{RESET}")
    print(f"  {CYAN}•{RESET} Run deterministic linter: {DIM}python3 {selected_targets[0][1]}/scripts/lint.py <draft.txt> <spec.json>{RESET}")
    print(f"  {CYAN}•{RESET} Invoke inside AI Agent:   {DIM}/jaso-pipeline <draft.txt|url>{RESET}\n")

if __name__ == "__main__":
    main()
