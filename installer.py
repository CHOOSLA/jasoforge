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
import subprocess
from pathlib import Path

VERSION = "3.1.0"
SKILL_NAME = "jaso-pipeline"
BANNER = rf"""
       _                 ______                  
      | |               |  ____|                 
      | | __ _ ___  ___ | |__ ___  _ __ __ _  ___ 
  _   | |/ _` / __|/ _ \|  __/ _ \| '__/ _` |/ _ \
 | |__| | (_| \__ \ (_) | | | (_) | | | (_| |  __/
  \____/ \__,_|___/\___/|_|  \___/|_|  \__, |\___|
                                        __/ |     
      Deterministic Resume Vetting     |___/  v{VERSION}
"""

def get_target_paths():
    home = Path.home()
    return {
        "agents": home / ".agents" / "skills" / SKILL_NAME,
        "claude": home / ".claude" / "skills" / SKILL_NAME,
        "gemini": home / ".gemini" / "config" / "skills" / SKILL_NAME,
    }

def is_runtime_present(target_name: str) -> bool:
    """Check if the target runtime actually exists on the system to avoid ghost directories."""
    home = Path.home()
    if target_name == "claude":
        return (home / ".claude").exists() or shutil.which("claude") is not None
    elif target_name == "gemini":
        return (home / ".gemini").exists() or shutil.which("gemini") is not None or shutil.which("agy") is not None
    elif target_name == "agents":
        return (home / ".agents").exists()
    return False

def verify_source(source_dir: Path) -> bool:
    required_files = [
        source_dir / "SKILL.md",
        source_dir / "scripts" / "lint.py",
        source_dir / "scripts" / "grade.py",
        source_dir / "scripts" / "run_pipeline.py",
        source_dir / "references" / "rubric_tech.json",
    ]
    for rf in required_files:
        if not rf.exists():
            print(f"❌ Error: Required file missing in source: {rf}")
            return False
    return True

def install_target(source_dir: Path, target_path: Path, use_symlink: bool = False, dry_run: bool = False):
    print(f"\n📦 Deploying to [{target_path.parent.name}]: {target_path}")

    # Self-target defense
    if source_dir.resolve() == target_path.resolve():
        print(f"   ℹ️ Target is the active source directory ({target_path}). Skipping self-copy.")
        return True

    if dry_run:
        print("   [DRY-RUN] Would create parent and link/copy files.")
        return True

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean existing target
    if target_path.is_symlink() or target_path.exists():
        if target_path.is_symlink() or target_path.is_file():
            target_path.unlink()
        elif target_path.is_dir():
            shutil.rmtree(target_path)
        print(f"   🧹 Removed previous installation at {target_path}")

    if use_symlink:
        try:
            target_path.symlink_to(source_dir.resolve(), target_is_directory=True)
            print(f"   🔗 Symlinked -> {source_dir.resolve()}")
            return True
        except Exception as e:
            print(f"   ⚠️ Symlink failed ({e}), falling back to direct copy...")

    # Copy clean files
    shutil.copytree(
        source_dir,
        target_path,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git*", ".DS_Store", "scratch", "dist")
    )
    print(f"   ✅ Copied clean distribution to {target_path}")
    return True

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
    except Exception as e:
        print(f"   ⚠️ Self-test error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="JasoForge Sovereign Multi-Target Installer")
    parser.add_argument(
        "--target",
        choices=["auto", "all", "agents", "claude", "gemini"],
        default="auto",
        help="Target runtime environment (default: auto - smart detection of installed runtimes)"
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Create symbolic links instead of copying files (useful for active development)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate installation without making filesystem changes"
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Source directory containing JasoForge skill files"
    )

    args = parser.parse_args()

    print(BANNER)
    print(f"🖥️  OS: {platform.system()} ({platform.machine()}) | Python: {platform.python_version()}")

    source_dir = Path(args.source) if args.source else Path(__file__).resolve().parent
    if not verify_source(source_dir):
        sys.exit(1)

    all_targets = get_target_paths()

    # Determine targets to install
    if args.target == "auto":
        selected_targets = []
        for name, path in all_targets.items():
            if is_runtime_present(name):
                selected_targets.append((name, path))
            else:
                print(f"⏭️  Skipping [{name}]: runtime environment not detected (preventing ghost directory)")
        
        # Fallback if no specific runtime detected: install to universal agents path
        if not selected_targets:
            print("ℹ️  No specific runtime detected. Defaulting to Universal Agents location (~/.agents).")
            selected_targets = [("agents", all_targets["agents"])]
    elif args.target == "all":
        selected_targets = list(all_targets.items())
    else:
        selected_targets = [(args.target, all_targets[args.target])]

    success_count = 0
    for name, path in selected_targets:
        if install_target(source_dir, path, use_symlink=args.symlink, dry_run=args.dry_run):
            if not args.dry_run:
                if run_self_test(path):
                    print(f"   ✨ Self-test passed for [{name}]")
                else:
                    print(f"   ⚠️ Self-test warning for [{name}]")
            success_count += 1

    print("\n" + "="*60)
    print(f"🎉 Installation completed! Successfully deployed to {success_count} target(s).")
    print("🚀 Quick Test:")
    print("   python3 ~/.agents/skills/jaso-pipeline/scripts/lint.py --help")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
