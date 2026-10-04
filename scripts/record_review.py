#!/usr/bin/env python3
"""Append a validated review snapshot to a local application ledger.

Execution records are caller-supplied evidence, not proof of agent isolation.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evaluation_contract import (ContractError, load_draft, parse_json, read_json,
                                 validate_spec, validate_evaluation, verify_manifest)
from grade import report_review, summarize_review

ROOT = Path(__file__).resolve().parent.parent


def append_review(ledger_path, application_key, entry):
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ContractError('원장을 다른 작업이 사용 중입니다. 기록 완료 여부를 확인한 후 재시도하십시오.')
    os.close(fd)
    temporary = None
    try:
        ledger = read_json(path) if path.exists() else {
            'schema_version': 1, 'application_key': application_key, 'runs': []}
        if (not isinstance(ledger, dict) or ledger.get('schema_version') != 1
                or not isinstance(ledger.get('runs'), list)):
            raise ContractError('지원하지 않는 기존 원장 형식입니다. 원본을 보존하고 별도 원장 또는 명시적 마이그레이션을 사용하십시오.')
        if ledger.get('application_key') != application_key:
            raise ContractError('다른 지원서키의 원장에 기록할 수 없습니다.')
        for previous in ledger['runs']:
            if not isinstance(previous, dict) or not previous.get('run_id'):
                raise ContractError('기존 원장 항목이 손상되었습니다. 원본을 보존하십시오.')
            if previous['run_id'] == entry['run_id']:
                before = {k: v for k, v in previous.items() if k != 'recorded_at'}
                after = {k: v for k, v in entry.items() if k != 'recorded_at'}
                if before != after:
                    raise ContractError('같은 run_id의 기록 내용이 다릅니다. 기존 평가를 덮어쓸 수 없습니다.')
                return False
        ledger['runs'].append(entry)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', delete=False) as out:
            temporary = Path(out.name)
            json.dump(ledger, out, ensure_ascii=False, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        return True
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
        lock.unlink()


def build_entry(args):
    paths = {name: Path(getattr(args, name)) for name in (
        'draft', 'spec', 'hr_eval', 'tech_eval', 'session_token', 'execution_log')}
    if args.context:
        paths['context'] = Path(args.context)
    originals = {name: path.read_bytes() for name, path in paths.items()}
    token = verify_manifest(paths['session_token'], paths['draft'], paths['spec'], paths.get('context'), ROOT)
    if token != parse_json(originals['session_token'].decode('utf-8')):
        raise ContractError('기록 중 세션 토큰이 변경되었습니다.')
    for name in ('draft', 'spec', *(['context'] if args.context else [])):
        if hashlib.sha256(originals[name]).hexdigest() != token['inputs'][name]['sha256']:
            raise ContractError(f'기록 중 입력이 변경되었습니다: {name}')
    with tempfile.TemporaryDirectory() as tmp:
        draft_path = Path(tmp) / 'draft.txt'
        draft_path.write_bytes(originals['draft'])
        draft = load_draft(draft_path)
    context = parse_json(originals['context'].decode('utf-8')) if args.context else {}
    if not isinstance(context, dict) or context.get('application_key', args.application_key) != args.application_key:
        raise ContractError('context의 지원서키와 기록 대상이 다릅니다.')
    spec = parse_json(originals['spec'].decode('utf-8'))
    validate_spec(spec, draft, require_axes=True)
    reviews = {role: validate_evaluation(parse_json(originals[name].decode('utf-8')), role, draft, spec, token, context)
               for role, name in (('HR', 'hr_eval'), ('TECH', 'tech_eval'))}
    weights = token.get('review_weights', {})
    if (set(weights) != {'HR', 'TECH'} or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in weights.values())):
        raise ContractError('유효한 사전 평가 가중치가 필요합니다.')
    execution = parse_json(originals['execution_log'].decode('utf-8'))
    if not isinstance(execution, dict) or execution.get('run_id') != token['run_id']:
        raise ContractError('평가 실행 기록의 run_id가 다릅니다.')
    calls = execution.get('evaluators')
    if not isinstance(calls, dict) or set(calls) != {'HR', 'TECH'}:
        raise ContractError('HR/TECH 실제 호출 기록이 필요합니다.')
    for role, call in calls.items():
        if (not isinstance(call, dict) or any(not isinstance(call.get(k), str) or not call[k].strip()
                for k in ('call_id', 'model', 'started_at'))
                or call.get('inherited_context') is not False
                or call.get('packet_sha256') != token['inputs'][role.lower() + '_packet']['sha256']):
            raise ContractError(f'{role} 호출 식별자·모델·시각·격리·패킷 기록을 확인하십시오.')
    if calls['HR']['call_id'] == calls['TECH']['call_id']:
        raise ContractError('HR/TECH 호출은 서로 다른 실행이어야 합니다.')
    verify_manifest(paths['session_token'], paths['draft'], paths['spec'], paths.get('context'), ROOT)
    if any(path.read_bytes() != originals[name] for name, path in paths.items()):
        raise ContractError('기록 중 입력/평가가 변경되었습니다. 새 입력으로 다시 기록하십시오.')
    return {
        'run_id': token['run_id'], 'version': args.version, 'evaluation_version': token['evaluation_version'],
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'session_token': token, 'execution_log': execution,
        'execution_evidence_note': '호스트가 제공한 호출 기록. 이 스크립트 자체는 에이전트 격리를 증명하지 않습니다.',
        'draft_text': originals['draft'].decode('utf-8'), 'spec': spec,
        'context': context, 'reviews': reviews,
        'aggregate_report': report_review(draft, spec, reviews, weights, context),
        'aggregate_summary': summarize_review(draft, spec, reviews, weights, context),
        'source_file_hashes': {name: hashlib.sha256(data).hexdigest() for name, data in originals.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('draft')
    parser.add_argument('spec')
    parser.add_argument('--context')
    for name in ('hr-eval', 'tech-eval', 'session-token', 'execution-log', 'application-key', 'version', 'ledger'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        if not args.application_key.strip() or not args.version.strip():
            raise ContractError('지원서키와 버전은 비어 있을 수 없습니다.')
        entry = build_entry(args)
        added = append_review(args.ledger, args.application_key, entry)
        print(f"{'RECORDED' if added else 'ALREADY_RECORDED'}: {entry['run_id']} → {args.ledger}")
        return 0
    except (ContractError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'NOT_RECORDED: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
