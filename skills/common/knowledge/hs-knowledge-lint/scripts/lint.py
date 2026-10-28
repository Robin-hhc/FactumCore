"""Thin adapter over digest-pinned pure domain checks."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    from support import domain, sha, reserve_output, finish_output
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-root", required=True)
    parser.add_argument("--rules-digest")
    parser.add_argument("--input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--catalog")  # transport compatibility; intentionally unused
    parser.add_argument("--action", default="lint", choices=("lint", "run", "check"))
    args = parser.parse_args()
    output_stream = None
    output = Path(args.output).absolute()
    try:
        try:
            output_stream = reserve_output(args.output, args.knowledge_root, (".build", "logs", "artifacts"))
        except (OSError, ValueError) as exc:
            sys.stderr.write(str(exc) + "\n")
            raise
        root = Path(args.knowledge_root).resolve(strict=True)
        if args.rules_digest is None:
            args.rules_digest = sha((root / "governance/framework.lock.yaml").read_bytes())
        modules, rules = domain(root, args.rules_digest)
        v, checks = modules["validation"], modules["checks"]
        request = v.read_json(Path(args.input)) if args.input else {}
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
        finish_output(output_stream, raw)
        output_stream = None
        print(raw.decode("utf-8"))
        return checks.exit_code(report)
    except Exception as exc:
        if output_stream is not None and not output_stream.closed:
            owner = os.fstat(output_stream.fileno())
            output_stream.close()
            try:
                current = output.lstat()
                if (current.st_dev, current.st_ino) == (owner.st_dev, owner.st_ino):
                    output.unlink()
            except OSError:
                pass
        error = {"report_version": "1.0", "status": "incomplete", "phase": "incomplete", "exit_code": 2,
                 "complete": False, "rules_digest": args.rules_digest, "checks": [], "findings": [{"code": "LINT_UNAVAILABLE", "severity": "error", "reason": str(exc)}]}
        print(json.dumps(error, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
