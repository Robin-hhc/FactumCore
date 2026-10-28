"""Thin adapter over digest-pinned pure domain checks."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def main():
    from support import domain, sha
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-root", required=True)
    parser.add_argument("--rules-digest")
    parser.add_argument("--input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--catalog")  # transport compatibility; intentionally unused
    parser.add_argument("--action", default="lint", choices=("lint", "run", "check", "review", "record-review", "code-check", "code-recheck", "verify-evidence"))
    args = parser.parse_args()
    report = None
    output_safe = False
    try:
        root = Path(args.knowledge_root).resolve(strict=True)
        if args.rules_digest is None:
            args.rules_digest = sha((root / "governance/framework.lock.yaml").read_bytes())
        output = Path(args.output).resolve()
        if output.exists():
            raise ValueError("A fresh report path is required")
        if output.is_relative_to(root) and output.relative_to(root).parts[0] not in {".build", "logs", "artifacts"}:
            raise ValueError("Report cannot overwrite domain source or governed data")
        if output.is_symlink() or any(parent.is_symlink() for parent in output.parents):
            raise ValueError("Linked report paths are not permitted")
        output_safe = True
        modules, rules = domain(root, args.rules_digest)
        v, checks = modules["validation"], modules["checks"]
        request = v.read_json(Path(args.input)) if args.input else {}
        if args.action in {"review", "record-review", "code-check", "code-recheck", "verify-evidence"}:
            from review import context, run, special_action
            ctx = context(root, request, args, modules, rules)
            if args.action == "review":
                report = run(ctx)
                report["data"] = {"report_ref": str(output), "check_status": report["status"],
                                  "full_scope": True, **report["review"]}
                report["digest"] = v.digest_payload(report)
                code = checks.exit_code(report)
            else:
                report, code = special_action(ctx, args.action)
            raw = v.canonical_bytes(report)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as stream:
                stream.write(raw)
            print(raw.decode("utf-8"))
            return code
        mode = request.get("mode", "candidate" if request.get("view_ref") else "formal")
        if mode not in {"formal", "candidate"}:
            raise ValueError("Use formal or candidate mode")
        candidate = None
        identity = {"root": str(root)}
        if mode == "candidate":
            candidate = v.read_json(v.safe_path(root, request["view_ref"], [".build", "logs"]))
            modules["records"].verify(candidate)
            identity = {"view_digest": candidate["digest"], "operation_id": candidate["operation_id"]}
        view = checks.prepare_view(root, candidate, mode=mode, identity=identity)
        report = checks.run(view, rules, inputs=request.get("inputs", request.get("check_inputs")), scope=request.get("scope"))
        checks.validate_report(report, expected_rules=args.rules_digest)
        # Supplemental transport fields are included in the sealed report.
        report["data"] = {"report_ref": str(output), "check_status": report["status"], "full_scope": report["scope"]["kind"] == "full"}
        report["digest"] = v.digest_payload(report)
        raw = v.canonical_bytes(report)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(raw)
        print(raw.decode("utf-8"))
        return checks.exit_code(report)
    except Exception as exc:
        if args.action in {"review", "record-review", "code-check", "code-recheck", "verify-evidence"}:
            from support import canonical, digest, tool_identity
            blocked = getattr(exc, "blocked", False)
            error = {"schema_version": "2.0", "record_kind": "result",
                     "status": "blocked" if blocked else "error",
                     "phase": "blocked" if blocked else "invalid",
                     "data": dict(getattr(exc, "data", {}) or {}),
                     "diagnostics": [{"code": getattr(exc, "code", "LINT_UNAVAILABLE"),
                                      "message": getattr(exc, "message", str(exc)),
                                      "path": str(getattr(exc, "path", ""))}],
                     "rules_digest": args.rules_digest,
                     "tool_identity": tool_identity(Path(__file__).resolve().parents[1])}
            error["digest"] = digest(error)
            if output_safe and not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as stream:
                    stream.write(canonical(error))
            print(json.dumps(error, ensure_ascii=True))
            return 2
        error = {"report_version": "1.0", "status": "incomplete", "phase": "incomplete", "exit_code": 2,
                 "complete": False, "rules_digest": args.rules_digest, "checks": [], "findings": [{"code": "LINT_UNAVAILABLE", "severity": "error", "reason": str(exc)}]}
        print(json.dumps(error, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
