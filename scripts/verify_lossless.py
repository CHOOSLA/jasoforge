#!/usr/bin/env python3
"""Legacy command name: static file validation, not a proof of lossless behavior."""
import ast
import re
import sys
from pathlib import Path
from evaluation_contract import read_json, ContractError


def verify(root, target):
    errors = []
    content = target.read_text(encoding='utf-8')
    if not content.startswith('---\n') or '\n---\n' not in content[4:]:
        errors.append('SKILL frontmatter is missing')
    for link in re.findall(r'\]\(([^)]+)\)', content):
        if not link.startswith(('https://', 'http://', '#')) and not (target.parent / link.split('#')[0]).is_file():
            errors.append(f'Missing linked reference: {link}')
    scripts = sorted((root / 'scripts').glob('*.py'))
    for path in scripts:
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f'{path.name}: {exc}')
    refs = sorted((root / 'references').glob('*.json'))
    for path in refs:
        try:
            read_json(path)
        except (ContractError, OSError, ValueError) as exc:
            errors.append(f'{path.name}: {exc}')
    for error in errors:
        print(f'ERROR: {error}')
    print(f'Static validation: {len(scripts)} Python files, {len(refs)} JSON files, SKILL links; {len(errors)} errors.')
    print('This checks syntax and references only. Run behavioral tests separately; writing quality is not proven.')
    return not errors


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'SKILL.md'
    sys.exit(0 if verify(root, target) else 1)
