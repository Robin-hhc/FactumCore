"""Set up, read, publish and maintain a HiMate knowledge base."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

from .protocol import FRAMEWORK_LOCK, NodeError as CommandError, domain, envelope, relative_to_existing_root


HELP_FLAGS = {"-h", "--help", "-help"}
LIBRARY_ACTIONS = ("overview", "cards", "graph", "search", "read")
RAW_ACTIONS = {
    "list": "raw-list",
    "path": "raw-path",
    "save": "raw-save",
    "mkdir": "raw-mkdir",
    "rmdir": "raw-rmdir",
    "categories": "intake-categories",
    "preflight": "intake-preflight",
    "save-package": "intake-save",
}
INGEST_ALIASES = {"review": "check", "apply": "commit", "status": "status"}
COMMAND_GROUPS = (
    ("Set up the execution environment", ("doctor", "setup", "install-command")),
    ("Find and read knowledge", ("search", "read", "library")),
    ("Manage raw materials and evidence", ("raw", "source")),
    ("Publish knowledge", ("ingest",)),
    ("Maintain the knowledge base", ("maintain", "patrol")),
    ("Compatibility commands", ("query", "panel", "review", "lint", "apply", "status")),
)
COMMAND_HELP = {
    "ingest": ("{scan,check,commit,status}", "Ingest sources into the knowledge base.\n\n"
               "  scan    Find source changes and prepare work.\n"
               "  check   Validate the proposed cards and their evidence.\n"
               "  commit  Publish the checked changes.\n"
               "  status  Show the current ingest task or latest receipt."),
    "source": ("[ACTION]", "Manage or read registered sources.\n\n"
               "Actions: list (default), register, resolve, extract, renew, release, cleanup, configure."),
    "query": ("[TEXT | search TEXT | read CARD_ID]", "Search the knowledge base or read a card."),
    "search": ("[TEXT]", "Search knowledge cards by text and optional tags."),
    "read": ("[CARD_ID]", "Read a full knowledge card."),
    "patrol": ("{sync,plan,reindex,complete}", "Plan and track knowledge maintenance."),
    "maintain": ("[{audit,lint,reindex}]", "Maintain the knowledge base.\n\n"
                 "  audit    Audit source references. This is the default.\n"
                 "  lint     Validate the formal knowledge cards.\n"
                 "  reindex  Update the published index. Use --full to rebuild it from scratch."),
    "library": ("{" + ",".join(LIBRARY_ACTIONS) + "}", "Browse and read the published knowledge view.\n\n"
                "Pass view_revision in the JSON input to pin the published snapshot."),
    "raw": ("ACTION", "Manage files in the raw materials directory.\n\n"
            "Directory: list, path, save, mkdir, rmdir.\n"
            "Upload intake: categories, preflight, save-package."),
    "panel": ("ACTION", "Read the published view or manage raw materials.\n\n"
              "Published view: overview, cards, search, read, graph.\n"
              "Raw materials: raw-list, raw-path, raw-save, raw-mkdir, raw-rmdir.\n"
              "Upload intake: intake-categories, intake-preflight, intake-save."),
    "review": ("", "Validate the proposed cards and their evidence."),
    "lint": ("", "Validate published knowledge cards."),
    "apply": ("", "Publish the checked changes."),
    "status": ("", "Show the current ingest task or latest receipt."),
    "doctor": ("[--environment-only [--bin-dir DIR | --dependencies-only]]",
               "Check the runtime, dependencies, configuration and rules.\n\n"
               "Use --environment-only to check dependencies and the launcher without a knowledge root."),
    "setup": ("[--bin-dir DIR | --dependencies-only] [--json | --jsonl]",
              "Install missing dependencies and set up the knowledge launcher.\n\n"
              "Use --dependencies-only to leave the launcher and PATH untouched.\n"
              "Use --json for the final result or --jsonl for progress events and the final result."),
    "install-command": ("[--bin-dir DIR] [--add-path]", "Install the knowledge command launcher."),
}
EXTRACT_HELP = (
    "--input FILE.json",
    "Convert a registered document into local reading materials.\n\n"
    'JSON example: {"source_id":"doc-example","page_range":[10,15],"page_preview":false}\n'
    "PDF page_range uses inclusive physical pages. Use page_start and page_end as an alternative.\n"
    "Use page_preview=false for text and document images without rendered page views.\n"
    'Optional parser settings belong in the top-level parser object, for example {"pipeline":"standard"}.',
)


class CommandParser(argparse.ArgumentParser):
    def error(self, message):
        raise CommandError("INVALID_ARGUMENT", message)


def parser(version):
    commands = "\n\n".join(
        heading + ":\n" + "\n".join(f"  {name:<17} {COMMAND_HELP[name][1].splitlines()[0]}" for name in names)
        for heading, names in COMMAND_GROUPS
    )
    result = CommandParser(prog="knowledge", description=__doc__, add_help=False,
                           formatter_class=argparse.RawDescriptionHelpFormatter,
                           epilog=f"{commands}\n\nUse 'knowledge help COMMAND' for command help.")
    result.add_argument("command", choices=COMMAND_HELP, metavar="COMMAND")
    result.add_argument("arguments", nargs="*", metavar="ARG")
    result.add_argument("-h", "--help", "-help", action="help", help="show this help message and exit")
    result.add_argument("--version", action="version", version=f"%(prog)s {version}")
    for name in ("action", "input", "output", "knowledge-root", "rules-digest",
                 "source", "path", "receipt", "bin-dir"):
        result.add_argument("--" + name)
    # Recognize the removed option only to explain the new contract, including
    # the old flag without a value; never silently broaden an old query.
    result.add_argument("--purpose", nargs="?", const="", help=argparse.SUPPRESS)
    result.add_argument("--top-k", type=int)
    output_modes = result.add_mutually_exclusive_group()
    output_modes.add_argument("--json", action="store_true")
    output_modes.add_argument("--jsonl", action="store_true", help="stream setup progress as JSON lines")
    result.add_argument("--environment-only", action="store_true", help="check the environment without a knowledge root")
    result.add_argument("--dependencies-only", action="store_true", help="skip launcher checks and registration")
    result.add_argument("--add-path", action="store_true")
    result.add_argument("--include-deprecated", action="store_true", default=None)
    result.add_argument("--full", action="store_true", default=None, help="rebuild the index from scratch with reindex")
    return result


def show_help(arguments, command_parser):
    if not arguments or arguments == ["help"]:
        command_parser.print_help()
        return True
    if len(arguments) == 2 and arguments[0] == "help":
        command = arguments[1]
        if command not in COMMAND_HELP:
            raise CommandError("INVALID_ARGUMENT", f"Unknown command for help: {command}")
    else:
        command = arguments[0]
        end_of_options = arguments.index("--") if "--" in arguments else len(arguments)
        if command not in COMMAND_HELP or HELP_FLAGS.isdisjoint(arguments[1:end_of_options]):
            return False
    syntax, details = COMMAND_HELP[command]
    if command == "source" and arguments[:2] == ["source", "extract"]:
        command = "source extract"
        syntax, details = EXTRACT_HELP
    usage = " ".join(filter(None, ("%(prog)s", syntax, "[options]")))
    argparse.ArgumentParser(
        prog=f"knowledge {command}", usage=usage, description=details,
        epilog="See 'knowledge --help' for shared options such as --knowledge-root, --input and --json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    ).print_help()
    return True


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
    for name in ("source", "path", "top_k", "include_deprecated", "full"):
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
    if command in INGEST_ALIASES:
        command, action, words = "ingest", INGEST_ALIASES[command], []
    if command == "ingest":
        if words:
            raise CommandError("INVALID_ARGUMENT", "Use ingest scan, check, commit or status")
        if action == "scan":
            data, phase = ingest.scan(root, request)
        elif action == "check":
            data, phase = ingest.check(root, request, rules)
        elif action == "commit":
            data, phase = ingest.commit(root, request)
        elif action == "status":
            task = root / ".build/task.json"
            latest = root / "artifacts/ingest/latest.json"
            if not latest.is_file():
                # Existing roots can retain their last receipt without migration.
                latest = root / "logs/ingest/latest.json"
            data = ingest.read_json(task if task.is_file() else latest) if task.is_file() or latest.is_file() else {}
            phase = "prepared" if task.is_file() else "completed" if latest.is_file() else "idle"
        else:
            raise CommandError("INVALID_ACTION", "Use ingest scan, check, commit or status")
    elif command == "source":
        if words:
            raise CommandError("INVALID_ARGUMENT", "Source parameters belong in --input")
        data, phase = library.sources(root, action or "list", request)
    elif command in {"panel", "library", "raw"}:
        if words:
            raise CommandError("INVALID_ARGUMENT", f"{command.capitalize()} parameters belong in --input")
        if command == "library" and action not in LIBRARY_ACTIONS:
            raise CommandError("INVALID_ACTION", "Unknown library action. Run knowledge help library")
        if command == "raw":
            if action not in RAW_ACTIONS:
                raise CommandError("INVALID_ACTION", "Unknown raw action. Run knowledge help raw")
            action = RAW_ACTIONS[action]
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
    elif command == "lint" or (command == "maintain" and action == "lint"):
        if command == "maintain" and words:
            raise CommandError("INVALID_ARGUMENT", "Maintain lint parameters belong in --input")
        data, phase = ingest.check(root, {**request, "formal": True}, rules)
    elif command == "maintain":
        if action == "reindex":
            data, phase = library.patrol(root, "reindex", request)
        elif action in (None, "audit", "references", "audit-references"):
            data, phase = library.audit(root)
        else:
            raise CommandError("INVALID_ACTION", "Use maintain audit, lint or reindex")
    else:
        raise CommandError("INVALID_COMMAND", command)
    code = 1 if phase == "failed" or command == "ingest" and phase == "blocked" else 0
    return envelope("failed" if code else "ok", phase, data), code


def emit(value, as_json, *, failed):
    if as_json:
        print(json.dumps(value, ensure_ascii=False))
    else:
        stream = sys.stderr if failed else sys.stdout
        print(value["status"] + ": " + value["phase"], file=stream)
        print(json.dumps(value.get("data", {}), ensure_ascii=False, indent=2), file=stream)
        for item in value.get("diagnostics", []):
            print(str(item.get("code", "")) + ": " + str(item.get("message", "")), file=stream)


def main(argv=None, *, tool_root, manifest):
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = None
    try:
        command_parser = parser(manifest["version"])
        if show_help(arguments, command_parser):
            return 0
        args = command_parser.parse_intermixed_args(arguments)
        if args.full:
            action = args.action or next(iter(args.arguments), None)
            if args.command not in {"maintain", "patrol"} or action != "reindex":
                raise CommandError("INVALID_ARGUMENT", "--full is for maintain reindex or patrol reindex")
        if args.environment_only and args.command != "doctor":
            raise CommandError("INVALID_ARGUMENT", "--environment-only is for doctor")
        if args.jsonl and args.command != "setup":
            raise CommandError("INVALID_ARGUMENT", "--jsonl is for setup")
        if args.dependencies_only and not (args.environment_only or args.command == "setup"):
            raise CommandError("INVALID_ARGUMENT", "--dependencies-only is for setup or doctor --environment-only")
        if args.dependencies_only and args.bin_dir is not None:
            raise CommandError("INVALID_ARGUMENT", "--dependencies-only cannot be combined with --bin-dir")
        if args.environment_only or args.command == "setup":
            if args.arguments or args.add_path or any(option is not None for option in (
                    args.action, args.input, args.output, args.knowledge_root, args.rules_digest,
                    args.source, args.path, args.receipt, args.purpose, args.top_k, args.include_deprecated)):
                raise CommandError("INVALID_ACTION", "This environment command accepts no knowledge request")
            from .environment import run_environment
            action = "check" if args.environment_only else "install"
            output_mode = "jsonl" if args.jsonl else "json" if args.json else "text"
            return run_environment(tool_root, manifest, action, bin_dir=args.bin_dir, output=output_mode,
                                   dependencies_only=args.dependencies_only)
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
        emit(value, args.json, failed=bool(code))
        return code
    except Exception as error:
        diagnostic = {"code": getattr(error, "code", "INVALID_INPUT"), "message": str(error)}
        if getattr(error, "path", ""):
            diagnostic["path"] = str(error.path)
        value = envelope("error", "invalid", diagnostics=[diagnostic])
        emit(value, (args.json or args.jsonl) if args else bool({"--json", "--jsonl"}.intersection(arguments)), failed=True)
        return 2
