#!/usr/bin/env python3
"""작성 모델과 다른 공급사 모델로 HR과 TECH 평가 패킷을 실행한다.

같은 계열 평가자는 자기 계열이 쓴 글을 더 좋게 보는 경향이 있다. 이 실행기는 사용자 지침, 메모리,
스킬이 보이지 않는 새 환경에서 패킷 하나만 넘기고, 응답을 기존 평가 계약으로 검증해 저장하며
evaluation_execution.json에 호출 기록을 남긴다. 다른 공급사를 쓸 수 없으면 종료 코드 3으로 알리고,
호스트는 기존처럼 같은 모델의 독립 서브에이전트로 평가한다.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from evaluation_contract import ContractError, load_draft, read_json, validate_evaluation

UNAVAILABLE = 3
HOST_FAMILY = {"claude": "anthropic", "codex": "openai", "gemini": "google", "agy": "google"}
PRESET_FAMILY = {"codex": "openai"}
PREAMBLE = """[실행 방식]
너는 아래 패킷 하나만 받은 독립 평가자다. 작성자와의 대화, 사용자 지침, 메모리, 스킬, 작성 프로필은 이 평가에 없고 찾지도 않는다.
파일을 읽거나 쓰지 말고 명령도 실행하지 않는다. 필요한 자료는 모두 패킷 안에 있다.
패킷의 검토 계약과 출력 JSON 구조를 따르고 최종 답변으로 JSON 객체 하나만 출력한다. 코드 블록 표시나 설명 문장은 붙이지 않는다.
evaluator, run_id, draft_hash, packet_hash는 실행기가 채우므로 틀에 적힌 값을 그대로 둔다.

[패킷]
"""
ISOLATION = {
    "codex": "새 HOME과 CODEX_HOME에서 실행. 사용자 지침, 설정, 스킬 없음. 읽기 전용 샌드박스, 세션 저장 안 함",
    "command": "사용자 지정 명령. 격리 범위는 그 명령의 설정을 따름",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def codex_auth_path():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "auth.json"


def available(provider):
    if provider == "codex":
        return bool(shutil.which("codex")) and codex_auth_path().is_file()
    return False


def resolve_provider(args):
    host_family = HOST_FAMILY[args.host]
    if args.provider == "command":
        if not args.command:
            raise ContractError("--provider command에는 --command가 필요합니다.")
        return "command"
    if args.provider == "auto":
        return next((name for name, family in PRESET_FAMILY.items() if family != host_family and available(name)), None)
    if PRESET_FAMILY[args.provider] == host_family:
        raise ContractError(f"{args.provider}는 작성 모델과 같은 계열입니다. 같은 계열은 기존 독립 서브에이전트로 평가합니다.")
    return args.provider if available(args.provider) else None


def link_auth(real, codex_home):
    """로그인 파일을 복사하지 않고 원래 파일을 가리키는 링크로 건다.

    Codex는 갱신 토큰을 한 번 쓰면 폐기한다. 복사본이 갱신하면 원래 로그인이 끊기므로
    갱신이 일어나도 원래 파일에 쓰이게 한다.
    """
    codex_home.mkdir(parents=True, exist_ok=True)
    link = codex_home / "auth.json"
    link.symlink_to(real)
    return link, sha256(real.read_bytes())


def restore_auth(link, real, original_hash):
    """실행 중 링크가 새 파일로 바뀌었으면 새 토큰을 원래 위치로 돌려놓는다."""
    if link.is_symlink():
        return "linked"
    if not link.exists():
        return "missing"
    if not real.exists() or sha256(real.read_bytes()) != original_hash:
        return "conflict"
    staged = real.with_name(real.name + ".jaso-restore")
    shutil.copyfile(link, staged)
    os.chmod(staged, 0o600)
    os.replace(staged, real)
    return "restored"


def run_codex(prompt, args, workdir):
    real = codex_auth_path()
    with tempfile.TemporaryDirectory(prefix="jaso-eval-home-") as tmp:
        home = Path(tmp)
        link, original = link_auth(real, home / ".codex")
        last = home / "last_message.txt"
        command = [shutil.which("codex"), "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
                   "-C", str(workdir), "-c", f'model_reasoning_effort="{args.effort}"', "-o", str(last)]
        if args.model:
            command += ["-m", args.model]
        env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
        try:
            run = subprocess.run(command + ["-"], input=prompt, env=env, capture_output=True, text=True,
                                 encoding="utf-8", timeout=args.timeout)
        finally:
            state = restore_auth(link, real, original)
        if state == "conflict":
            print("경고: 평가 중 Codex 로그인 파일이 양쪽에서 바뀌었습니다. codex를 직접 한 번 실행해 로그인을 확인하십시오.", file=sys.stderr)
        if run.returncode != 0:
            raise RuntimeError(f"codex 실행 실패, 종료 코드 {run.returncode}: {run.stderr.strip()[-500:]}")
        session = re.search(r"session id:\s*(\S+)", run.stderr)
        model = re.search(r"^model:\s*(\S+)", run.stderr, re.M)
        text = last.read_text(encoding="utf-8") if last.exists() else ""
        return (text, f"codex-{session.group(1)}" if session else f"codex-{uuid.uuid4()}",
                model.group(1) if model else (args.model or "unavailable"))


def run_command(prompt, args, workdir):
    run = subprocess.run(shlex.split(args.command), input=prompt, cwd=workdir, capture_output=True, text=True,
                         encoding="utf-8", timeout=args.timeout)
    if run.returncode != 0:
        raise RuntimeError(f"평가 명령 실패, 종료 코드 {run.returncode}: {run.stderr.strip()[-500:]}")
    return run.stdout, f"command-{uuid.uuid4()}", args.model or "unavailable"


RUNNERS = {"codex": run_codex, "command": run_command}


def extract_json(text):
    body = text.strip()
    fenced = re.fullmatch(r"```[A-Za-z]*\s*\n(.*?)\n?```", body, re.S)
    if fenced:
        body = fenced.group(1)
    start = body.find("{")
    if start < 0:
        raise ValueError("응답에 JSON 객체가 없습니다.")
    data, _ = json.JSONDecoder().raw_decode(body[start:])
    if not isinstance(data, dict):
        raise ValueError("응답 최상위가 JSON 객체가 아닙니다.")
    return data


def load_run(packets_dir):
    token = read_json(packets_dir / "session_token.json")
    inputs = token["inputs"]
    for name in ("draft", "spec", "context"):
        if name in inputs and sha256(Path(inputs[name]["path"]).read_bytes()) != inputs[name]["sha256"]:
            raise ContractError(f"패킷을 만든 뒤 {name} 파일이 바뀌었습니다. run_pipeline.py로 패킷을 다시 만드십시오.")
    draft = load_draft(Path(inputs["draft"]["path"]))
    spec = read_json(Path(inputs["spec"]["path"]))
    context = read_json(Path(inputs["context"]["path"])) if "context" in inputs else {}
    return token, draft, spec, context


def evaluate(role, provider, args, run, packets_dir, out_dir):
    token, draft, spec, context = run
    packet = (packets_dir / f"{role.lower()}_prompt_packet.txt").read_bytes()
    packet_hash = sha256(packet)
    if packet_hash != token["inputs"][f"{role.lower()}_packet"]["sha256"]:
        raise ContractError(f"{role} 패킷이 세션 토큰과 다릅니다. 패킷을 다시 만드십시오.")
    prompt, note, text, last_error = PREAMBLE + packet.decode("utf-8"), "", "", ""
    for attempt in range(1, args.retries + 2):
        started = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory(prefix="jaso-eval-work-") as work:
            text, call_id, model = RUNNERS[provider](prompt + note, args, Path(work))
        try:
            result = extract_json(text)
            result.update(evaluator=role, run_id=token["run_id"], draft_hash=token["inputs"]["draft"]["sha256"],
                          packet_hash=packet_hash)
            validate_evaluation(result, role, draft, spec, token, context)
        except (ValueError, ContractError) as exc:
            last_error = str(exc)
            note = f"\n\n[이전 출력 거부 사유]\n{last_error}\n같은 계약을 지켜 JSON 객체 하나만 다시 출력한다.\n"
            continue
        call = {"call_id": call_id, "model": model, "started_at": started, "inherited_context": False,
                "packet_sha256": packet_hash, "provider": provider, "isolation": ISOLATION[provider], "attempts": attempt}
        return result, call
    raw = out_dir / f"{role.lower()}_eval.raw.txt"
    raw.write_text(text, encoding="utf-8")
    raise ContractError(f"{role} 응답이 평가 계약을 통과하지 못했습니다: {last_error} 마지막 응답은 {raw}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packets_dir", nargs="?", help="run_pipeline.py가 만든 packets 폴더")
    parser.add_argument("--host", required=True, choices=sorted(HOST_FAMILY), help="지금 원고를 쓰고 있는 호스트")
    parser.add_argument("--provider", default="auto", choices=["auto", *PRESET_FAMILY, "command"])
    parser.add_argument("--command", help="command 공급자: 표준 입력으로 프롬프트를 받고 표준 출력에 최종 답을 내는 명령")
    parser.add_argument("--roles", default="HR,TECH")
    parser.add_argument("--model", help="평가 모델. command 공급자에서는 기록할 모델 이름")
    parser.add_argument("--effort", default="medium", help="Codex 추론 강도")
    parser.add_argument("--out-dir", help="기본값은 packets 폴더의 상위 실행 폴더")
    parser.add_argument("--execution-log", help="기본값은 out-dir/evaluation_execution.json")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--retries", type=int, default=1, help="계약 검증에 실패한 응답을 다시 받을 횟수")
    parser.add_argument("--check", action="store_true", help="실행하지 않고 쓸 수 있는 공급자만 확인")
    args = parser.parse_args()
    try:
        if args.timeout <= 0 or args.retries < 0:
            raise ContractError("--timeout은 양수, --retries는 0 이상이어야 합니다.")
        provider = resolve_provider(args)
        if provider is None:
            print("다른 공급사 평가자를 쓸 수 없습니다. 같은 모델의 독립 서브에이전트로 평가하고 리포트에 같은 계열 평가임을 밝히십시오.")
            return UNAVAILABLE
        if args.check:
            print(f"사용 가능한 다른 공급사 평가자: {provider}")
            return 0
        if not args.packets_dir:
            raise ContractError("packets 폴더를 지정하십시오.")
        roles = [role.strip().upper() for role in args.roles.split(",") if role.strip()]
        if not roles or set(roles) - {"HR", "TECH"} or len(set(roles)) != len(roles):
            raise ContractError("--roles는 HR, TECH 중에서 겹치지 않게 지정합니다.")
        packets_dir = Path(args.packets_dir).resolve()
        run = load_run(packets_dir)
        out_dir = Path(args.out_dir).resolve() if args.out_dir else packets_dir.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        log_path = Path(args.execution_log).resolve() if args.execution_log else out_dir / "evaluation_execution.json"
        log = read_json(log_path) if log_path.exists() else {}
        if log.get("run_id") != run[0]["run_id"]:
            log = {"run_id": run[0]["run_id"], "evaluators": {}}
        failed = []
        # 역할은 차례로 실행한다. 동시에 띄우면 로그인 갱신이 겹칠 수 있다.
        for role in roles:
            try:
                result, call = evaluate(role, provider, args, run, packets_dir, out_dir)
            except (ContractError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
                failed.append(role)
                print(f"{role}: 실패. {exc}")
                continue
            path = out_dir / f"{role.lower()}_eval.json"
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            log.setdefault("evaluators", {})[role] = call
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{role}: {provider} {call['model']}로 평가, 시도 {call['attempts']}회 → {path}")
        if failed:
            print(f"실패한 역할 {', '.join(failed)}는 같은 모델의 독립 서브에이전트로 다시 평가하고 호출 기록을 {log_path}에 맞춰 넣으십시오.")
            return 2
        print(f"호출 기록: {log_path}")
        return 0
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(f"외부 평가를 실행하지 못했습니다: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
