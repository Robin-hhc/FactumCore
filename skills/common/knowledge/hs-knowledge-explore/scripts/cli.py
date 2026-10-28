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
    digest,
    identifier,
    read_json,
    safe,
    tool_identity,
    validate_runtime,
)
from node import execute  # noqa: E402 - reject cached bytecode before imports

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("input", "output"):
        parser.add_argument("--" + key, required=True)
    for key in ("knowledge-root", "rules-digest", "catalog", "registry", "action"):
        parser.add_argument("--" + key)
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
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
        request = read_json(args.input)
        identifier(request.get("operation_id", "binding"))
        data, phase = execute(request, args, package)
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
    output = Path(args.output).absolute()
    if args.knowledge_root:
        root = Path(args.knowledge_root).resolve()
        if root.exists() and output.is_relative_to(root):
            safe(root, output.relative_to(root).as_posix(), [".build", "logs"])
    output.parent.mkdir(parents=True, exist_ok=True)
    result["digest"] = digest(
        {key: value for key, value in result.items() if key != "digest"}
    )
    output.write_bytes(canonical(result))
    sys.exit(code)
