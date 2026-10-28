import argparse
from pathlib import Path
import sys
import tempfile
import secrets

sys.dont_write_bytecode = True
sys.pycache_prefix = str(
    Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16))
)
from support import (  # noqa: E402 - bootstrap must precede package imports
    canonical,
    NodeError,
    digest,
    identifier,
    read_json,
    reserve_output,
    finish_output,
    safe,
    tool_identity,
    validate_runtime,
)
from node import execute, resolve  # noqa: E402 - reject cached bytecode before imports

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("input", "output"):
        parser.add_argument("--" + key, required=True)
    for key in ("knowledge-root", "rules-digest", "catalog", "registry", "action"):
        parser.add_argument("--" + key)
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    try:
        request = read_json(args.input)
        identifier(request.get("operation_id", "binding"))
        resolved = resolve(request, args.registry)
        actual_root = resolved[2]
        if args.knowledge_root and Path(args.knowledge_root).resolve() != actual_root:
            raise NodeError(
                "KNOWLEDGE_ROOT_MISMATCH",
                "Explicit knowledge root differs from the actual workspace mapping",
            )
        args.knowledge_root = str(actual_root)
        output_stream = reserve_output(args.output, args.knowledge_root)
    except Exception as exc:
        blocked = getattr(exc, "blocked", False)
        result = {
            "schema_version": "2.0", "record_kind": "result",
            "status": "blocked" if blocked else "error",
            "phase": "blocked" if blocked else "invalid", "data": {},
            "diagnostics": [{"code": getattr(exc, "code", "INVALID_INPUT"), "message": str(exc)}],
            "tool_identity": tool_identity(package), "rules_digest": args.rules_digest,
        }
        result["digest"] = digest(result)
        sys.stderr.write(str(exc) + "\n")
        print(canonical(result).decode("utf-8"))
        sys.exit(3 if blocked else 2)
    result = {
        "schema_version": "2.0",
        "record_kind": "result",
        "status": "error",
        "phase": "invalid",
        "data": {},
        "diagnostics": [],
        "tool_identity": tool_identity(package),
        "rules_digest": args.rules_digest,
    }
    code = 2
    try:
        validate_runtime(package)
        data, phase = execute(request, args, package, resolved=resolved)
        result.update(status="ok", data=data, phase=phase)
        if phase == "context_loaded":
            args.knowledge_root = data["knowledge_root"]
            context_record = read_json(
                safe(Path(args.knowledge_root), data["context_ref"])
            )
            args.rules_digest = context_record["rules_digest"]
            result["rules_digest"] = args.rules_digest
        code = 0
    except Exception as exc:
        blocked = getattr(exc, "blocked", False)
        result.update(
            status="blocked" if blocked else "error",
            phase="blocked" if blocked else "invalid",
            diagnostics=[
                {"code": getattr(exc, "code", "INVALID_INPUT"), "message": str(exc)}
            ],
        )
        code = 3 if blocked else 2
    result["digest"] = digest(
        {key: value for key, value in result.items() if key != "digest"}
    )
    try:
        finish_output(output_stream, canonical(result))
    except (OSError, ValueError) as exc:
        sys.stderr.write("Output could not be saved: " + str(exc) + "\n")
        sys.exit(2)
    sys.exit(code)
