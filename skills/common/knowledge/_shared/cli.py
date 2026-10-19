"""Public JSON CLI. Only implemented commands are registered."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _shared import __version__, contracts, receipts, scope


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise contracts.ContractError("INVALID_ARGUMENTS", message)


def parser():
    root = Parser(description=__doc__)
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True, parser_class=Parser)
    contract = commands.add_parser("contract")
    verbs = contract.add_subparsers(dest="action", required=True, parser_class=Parser)
    validate = verbs.add_parser("validate")
    validate.add_argument("--knowledge-root", type=Path, required=True)
    validate.add_argument(
        "--kind", choices=["workspace", "card", "sources", "record"], required=True
    )
    validate.add_argument("--input", type=Path, required=True)
    project = commands.add_parser("project")
    operations = project.add_subparsers(dest="action", required=True, parser_class=Parser)
    resolve = operations.add_parser("resolve")
    resolve.add_argument("--path", required=True)
    resolve.add_argument("--registry", type=Path, required=True)
    resolve.add_argument("--base")
    resolve.add_argument("--load-context", action="store_true")
    resolve.add_argument("--authorization-epoch", default="local")
    document = commands.add_parser("document")
    documents = document.add_subparsers(dest="action", required=True, parser_class=Parser)
    capture = documents.add_parser("capture")
    capture.add_argument("--knowledge-root", type=Path, required=True)
    capture.add_argument("--path", required=True)
    capture.add_argument("--source-id", required=True)
    capture.add_argument("--declared-version", default="unknown")
    capture.add_argument("--attachment", action="append", default=[])
    restore = documents.add_parser("load-capture")
    restore.add_argument("--knowledge-root", type=Path, required=True)
    restore.add_argument("--bundle-ref", required=True)
    restore.add_argument("--manifest-digest", required=True)
    return root


def execute(args):
    if args.command == "document":
        from _shared.sources import capture_document, load_capture

        if args.action == "capture":
            result = capture_document(
                args.knowledge_root,
                args.path,
                source_id=args.source_id,
                declared_version=args.declared_version,
                attachments=args.attachment,
            )
        else:
            result = load_capture(args.knowledge_root, args.bundle_ref, args.manifest_digest)
        return receipts.envelope("ok", result=result)
    if args.command == "contract":
        input_bytes = args.input.read_bytes()
        before = receipts.digest_bytes(input_bytes)
        document = contracts.load_document_bytes(input_bytes, args.input)
        diagnostics = contracts.validate_document(args.kind, document, args.knowledge_root)
        if receipts.digest_file(args.input) != before:
            raise contracts.ContractError("INPUT_CHANGED", "Input changed during validation")
        unknown = (
            scope.unknown_targets(document) if args.kind == "workspace" and not diagnostics else []
        )
        # This CLI checks declarations, never semantic evidence or deployment readiness.
        result = {
            "validation": "shape_and_configuration",
            "business_ready": False,
            "unknown_targets": unknown,
        }
        return receipts.envelope(
            "invalid" if diagnostics else "ok",
            result=result,
            diagnostics=diagnostics,
            input_digests={str(args.input): before},
        )
    from _shared.workspace import resolve_project

    result = resolve_project(
        args.path,
        args.registry,
        base_path=args.base,
        load_context=args.load_context,
        authorization_epoch=args.authorization_epoch,
    )
    return receipts.envelope("ok", result=result)


def main(argv=None):
    # Pipes on Windows can inherit a legacy code page even for UTF-8 input files.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        output = execute(parser().parse_args(argv))
        code = 0 if output["status"] == "ok" else 2
    except ValueError as exc:
        output = receipts.envelope(
            "invalid",
            diagnostics=[
                {
                    "code": getattr(exc, "code", "INVALID_INPUT"),
                    "message": str(exc),
                    "path": str(getattr(exc, "path", "")),
                }
            ],
        )
        code = 2
    except (OSError, UnicodeError, KeyError, TypeError, RecursionError) as exc:
        output = receipts.envelope(
            "error",
            diagnostics=[
                {
                    "code": "TOOL_ERROR",
                    "message": str(exc),
                    "path": "",
                }
            ],
        )
        code = 3
    print(json.dumps(output, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
