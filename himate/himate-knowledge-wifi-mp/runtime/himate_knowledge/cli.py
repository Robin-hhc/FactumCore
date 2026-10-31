"""Small public commands for a single-file knowledge workflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .protocol import NodeError as CommandError, domain, envelope, sha


COMMANDS = ("ingest", "source", "query", "search", "read", "patrol", "maintain",
            "review", "lint", "apply", "status", "doctor", "install-command")


class CommandParser(argparse.ArgumentParser):
    def error(self, message):
        raise CommandError("INVALID_ARGUMENT", message)


def parser():
    result = CommandParser(description=__doc__)
    result.add_argument("command", choices=COMMANDS)
    result.add_argument("arguments", nargs="*")
    for name in ("action", "input", "output", "knowledge-root", "rules-digest",
                 "source", "path", "receipt", "bin-dir"):
        result.add_argument("--" + name)
    # Recognize the removed option only to explain the new contract, including
    # the old flag without a value; never silently broaden an old query.
    result.add_argument("--purpose", nargs="?", const="", help=argparse.SUPPRESS)
    result.add_argument("--top-k", type=int)
    result.add_argument("--json", action="store_true")
    result.add_argument("--add-path", action="store_true")
    result.add_argument("--include-deprecated", action="store_true", default=None)
    return result


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CommandError("DUPLICATE_FIELD", key)
        result[key] = value
    return result


def _request(args):
    if args.input:
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
        value = json.loads(text, object_pairs_hook=_unique,
                           parse_constant=lambda word: (_ for _ in ()).throw(ValueError(word)))
        if not isinstance(value, dict):
            raise CommandError("INVALID_INPUT", "The request must be a JSON object")
    else:
        value = {}
    for name in ("source", "path", "top_k", "include_deprecated"):
        item = getattr(args, name)
        if item is not None:
            if name in value and value[name] != item:
                raise CommandError("ARGUMENT_CONFLICT", name)
            value[name] = item
    return value


def _output_path(root, reference, command):
    path = Path(os.path.abspath(reference))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise CommandError("LINKED_OUTPUT", str(part))
    if path.is_relative_to(root):
        relative = path.relative_to(root)
        allowed = ((Path("artifacts/query"),) if command in {"query", "search", "read"}
                   else (Path(".build"), Path("artifacts")))
        if not any(relative != directory and relative.is_relative_to(directory) for directory in allowed):
            raise CommandError("OUTPUT_OUTSIDE_WORKSPACE", "Query reports belong in artifacts/query; other reports in .build or artifacts")
    return path


def _output(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute(args, root):
    request = _request(args)
    if args.command in {"query", "search", "read"} and (
            args.purpose is not None or "purpose" in request or "context" in request):
        raise CommandError("QUERY_PARAMETERS_REMOVED",
                           "purpose/context are removed; search by query and optional tags, then read the card's conditions")
    modules, rules = domain(root, args.rules_digest or sha((root / "governance/framework.lock.yaml").read_bytes()))
    ingest, library = modules["ingest"], modules["library"]
    words = list(args.arguments)
    action = args.action or (words.pop(0) if words and args.command not in {"search", "read", "query"} else None)
    command = args.command
    if command == "ingest":
        if words:
            raise CommandError("INVALID_ARGUMENT", "Use ingest scan, check or commit")
        if action == "scan":
            data, phase = ingest.scan(root, request)
        elif action == "check":
            data, phase = ingest.check(root, request, rules)
        elif action == "commit":
            data, phase = ingest.commit(root, request)
        else:
            raise CommandError("INVALID_ACTION", "Use ingest scan, check or commit")
    elif command == "source":
        if words:
            raise CommandError("INVALID_ARGUMENT", "Source parameters belong in --input")
        data, phase = library.sources(root, action or "list", request)
    elif command in {"query", "search", "read"}:
        if command == "query" and words and words[0] in {"search", "read"}:
            action = words.pop(0)
        if command == "read" or action == "read":
            if words:
                if len(words) != 1:
                    raise CommandError("INVALID_ARGUMENT", "Use read CARD_ID")
                request["card_id"] = words[0]
            data, phase = library.query(root, request, read=True)
        else:
            if words:
                request["query"] = " ".join(words)
            data, phase = library.query(root, request)
    elif command == "patrol":
        if words:
            raise CommandError("INVALID_ARGUMENT", "Use patrol sync, plan, reindex or complete")
        data, phase = library.patrol(root, action, request)
    elif command == "lint":
        data, phase = ingest.check(root, {**request, "formal": True}, rules)
    elif command == "maintain":
        if action == "reindex":
            data, phase = library.patrol(root, "reindex", request)
        elif action in (None, "audit", "references", "audit-references"):
            data, phase = library.audit(root)
        else:
            raise CommandError("INVALID_ACTION", "Use maintain audit or reindex")
    elif command == "review":
        data, phase = ingest.check(root, request, rules)
    elif command == "apply":
        data, phase = ingest.commit(root, request)
    elif command == "status":
        task = root / ".build/task.json"
        latest = root / "artifacts/ingest/latest.json"
        if not latest.is_file():
            # Existing roots can retain their last receipt without migration.
            latest = root / "logs/ingest/latest.json"
        data = ingest.read_json(task if task.is_file() else latest) if task.is_file() or latest.is_file() else {}
        phase = "prepared" if task.is_file() else "completed" if latest.is_file() else "idle"
    else:
        raise CommandError("INVALID_COMMAND", command)
    code = 1 if phase == "failed" else 0
    return envelope("failed" if code else "ok", phase, data), code


def emit(value, as_json):
    if as_json:
        print(json.dumps(value, ensure_ascii=False))
    else:
        print(value["status"] + ": " + value["phase"])
        print(json.dumps(value.get("data", {}), ensure_ascii=False, indent=2))
        for item in value.get("diagnostics", []):
            print(str(item.get("code", "")) + ": " + str(item.get("message", "")))


def main(argv=None, *, knowledge_root=None, manifest=None):
    root = Path(knowledge_root).resolve(strict=True)
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = None
    try:
        args = parser().parse_intermixed_args(arguments)
        if args.knowledge_root:
            target = Path(args.knowledge_root).absolute()
            if target.resolve(strict=True) != root:
                entry = target / "knowledge.py"
                if not entry.is_file():
                    raise CommandError("KNOWLEDGE_ROOT_UNAVAILABLE", "The selected root has no CLI")
                return subprocess.call([sys.executable, "-B", str(entry), *arguments])
        output = _output_path(root, args.output, args.command) if args.output else None
        if args.command == "doctor":
            if args.arguments or args.input or args.action:
                raise CommandError("INVALID_ACTION", "doctor accepts no business request")
            from .doctor import doctor
            value, code = doctor(root, manifest)
        elif args.command == "install-command":
            from .command_install import install_command
            value, code = install_command(args, root)
        else:
            value, code = execute(args, root)
        if output is not None:
            _output(output, value)
        emit(value, args.json)
        return code
    except Exception as error:
        diagnostic = {"code": getattr(error, "code", "INVALID_INPUT"), "message": str(error)}
        if getattr(error, "path", ""):
            diagnostic["path"] = str(error.path)
        value = envelope("error", "invalid", diagnostics=[diagnostic])
        emit(value, args.json if args else "--json" in arguments)
        return 2
