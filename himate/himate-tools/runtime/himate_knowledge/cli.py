"""Small public commands for a single-file knowledge workflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

from .protocol import FRAMEWORK_LOCK, NodeError as CommandError, domain, envelope, relative_to_existing_root


COMMANDS = ("ingest", "source", "query", "search", "read", "patrol", "maintain", "panel",
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


def _linked(path):
    if not os.path.lexists(path):
        return False
    return (path.is_symlink()
            or bool(getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT))


def _has_data_layout(root):
    ledger = root / "governance/sources.lock.yaml"
    if not _linked(ledger.parent) and not _linked(ledger) and ledger.is_file():
        return True
    return all(not _linked(path) and path.is_dir() for path in (root / "docs-raw", root / "knowledge"))


def _knowledge_root(reference, tool_root, *, diagnostic=False):
    if reference is not None:
        if not reference.strip():
            raise CommandError("KNOWLEDGE_ROOT_UNAVAILABLE", "Select a knowledge data directory with --knowledge-root")
        candidates = (Path(os.path.abspath(reference)),)
    else:
        cwd = Path.cwd()
        # Old colocated development copies can still invoke their shared entrypoint.
        candidates = (cwd, *cwd.parents, tool_root)
    for candidate in candidates:
        diagnostic_root = reference is not None and diagnostic and os.path.lexists(candidate / "config.yml")
        if not candidate.is_dir() or not (_has_data_layout(candidate) or diagnostic_root):
            continue
        if any(_linked(part) for part in (candidate, *candidate.parents)):
            raise CommandError("KNOWLEDGE_ROOT_UNAVAILABLE", "Knowledge root must use an ordinary directory path", candidate)
        knowledge_root = candidate.resolve(strict=True)
        relative = relative_to_existing_root(knowledge_root, tool_root)
        if relative == Path("."):
            return tool_root
        if relative is not None or relative_to_existing_root(tool_root, knowledge_root) is not None:
            raise CommandError("KNOWLEDGE_ROOT_UNAVAILABLE", "Choose a knowledge data directory outside the installed tool", candidate)
        return knowledge_root
    raise CommandError("KNOWLEDGE_ROOT_UNAVAILABLE", "Select a knowledge data directory with --knowledge-root",
                       reference or "")


def _output_path(root, tool_root, reference, command):
    path = Path(os.path.abspath(reference))
    for part in (path, *path.parents):
        if _linked(part):
            raise CommandError("LINKED_OUTPUT", str(part))
    resolved = path.resolve()
    if tool_root != root and relative_to_existing_root(resolved, tool_root) is not None:
        raise CommandError("OUTPUT_INSIDE_TOOL", "Command output cannot write into the installed tool", path)
    relative = relative_to_existing_root(resolved, root) if root is not None else None
    if relative is not None:
        allowed = ((Path("artifacts/query"),) if command in {"query", "search", "read"}
                   else (Path(".build"), Path("artifacts")))
        if not any(relative != directory and relative.is_relative_to(directory) for directory in allowed):
            raise CommandError("OUTPUT_OUTSIDE_WORKSPACE", "Query reports belong in artifacts/query; other reports in .build or artifacts")
    return path


def _output(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute(args, root, tool_root, manifest_digest):
    request = _request(args)
    if args.command in {"query", "search", "read"} and (
            args.purpose is not None or "purpose" in request or "context" in request):
        raise CommandError("QUERY_PARAMETERS_REMOVED",
                           "purpose/context are removed; search by query and optional tags, then read the card's conditions")
    modules, rules = domain(tool_root, root, manifest_digest, args.rules_digest)
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
    elif command == "panel":
        if words:
            raise CommandError("INVALID_ARGUMENT", "Panel parameters belong in --input")
        data, phase = modules["panel"].run(root, action, request)
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


def main(argv=None, *, tool_root, manifest):
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = None
    try:
        args = parser().parse_intermixed_args(arguments)
        root = None
        if args.command != "install-command" or args.knowledge_root is not None:
            root = _knowledge_root(args.knowledge_root, tool_root, diagnostic=args.command == "doctor")
        output = _output_path(root, tool_root, args.output, args.command) if args.output else None
        if args.command == "doctor":
            if args.arguments or args.input or args.action:
                raise CommandError("INVALID_ACTION", "doctor accepts no business request")
            from .doctor import doctor
            value, code = doctor(tool_root, root, manifest)
        elif args.command == "install-command":
            from .command_install import install_command
            value, code = install_command(args, tool_root, root)
        else:
            value, code = execute(args, root, tool_root, manifest["assets"][FRAMEWORK_LOCK]["sha256"])
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
