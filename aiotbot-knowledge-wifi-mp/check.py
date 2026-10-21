"""Thin explicit merge-check entry. Pure documents do not invoke this wrapper.

Usage: python check.py --catalog ABS --input ABS --output ABS --rules-digest SHA
The catalog is an explicitly trusted, private installation file. This wrapper
does not discover executables beside the workspace or install dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def read_object(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict) or path.read_bytes() != raw:
        raise ValueError("Changed or invalid JSON object")
    return value, raw


def package_digest(package):
    files = {}
    for path in (package, *package.rglob("*")):
        if (
            path.is_symlink()
            or getattr(path.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("Linked installed package")
        if not path.is_file():
            continue
        relative = path.relative_to(package)
        if "__pycache__" in relative.parts or "tests" in relative.parts:
            continue
        if (
            relative.as_posix() == "SKILL.md"
            or relative.parts[0] in {"scripts", "references", "artifacts"}
            or (
                len(relative.parts) == 1
                and path.name.startswith("requirements")
                and path.name.endswith(".txt")
            )
        ):
            files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(canonical(files)).hexdigest()


def absolute(value, *, exists=True):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Explicit absolute paths are required")
    for part in (path, *path.parents):
        if part.is_symlink() or (
            part.exists()
            and getattr(part.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("Linked catalog, runtime or file path")
    return path.resolve(strict=exists)


def incomplete(message, *, invalid=False):
    envelope = {
        "schema_version": "2.0",
        "record_kind": "result",
        "status": "error" if invalid else "blocked",
        "phase": "incomplete",
        "data": {},
        "diagnostics": [{"code": "MERGE_CHECK_INCOMPLETE", "message": message}],
        "tool_identity": {"wrapper": "check.py"},
        "rules_digest": None,
    }
    print(json.dumps(envelope))
    return 2 if invalid else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--rules-digest")
    args = parser.parse_args()
    if not all((args.catalog, args.input, args.output, args.rules_digest)):
        return incomplete(
            "Explicit catalog, input, output and pinned rules digest are required; no real check ran."
        )
    try:
        if not re.fullmatch(r"[0-9a-f]{64}", args.rules_digest):
            raise ValueError("Invalid pinned rules digest")
        catalog_path = absolute(args.catalog)
        input_path = absolute(args.input)
        output_path = absolute(args.output, exists=False)
        if output_path in {catalog_path, input_path}:
            raise ValueError("Output must not overwrite input or catalog")
        if output_path.exists():
            raise ValueError(
                "Use a fresh job output path; existing evidence cannot stand in for this invocation"
            )
        knowledge = Path(__file__).resolve().parent
        if output_path.is_relative_to(knowledge) and output_path.relative_to(
            knowledge
        ).parts[0] not in {"logs", ".build", "artifacts"}:
            raise ValueError("Output cannot alter domain source/knowledge")
        catalog, catalog_bytes = read_object(catalog_path)
        if catalog.get("schema_version") != "2.0":
            raise ValueError("Catalog schema 2.0 required")
        entry = catalog.get("skills", {}).get("hs-knowledge-merge-check")
        if not isinstance(entry, dict) or entry.get("entry") != "scripts/cli.py":
            return incomplete(
                "Installed hs-knowledge-merge-check public CLI is unavailable."
            )
        package = absolute(entry["root"])
        python = absolute(entry["python"])
        cli = package / "scripts/cli.py"
        if (
            not cli.is_file()
            or not python.is_file()
            or package_digest(package) != entry.get("package_digest")
        ):
            raise ValueError("Installed package differs from trusted catalog")
        _, input_bytes = read_object(input_path)
        # The public CLI owns code identity, review mode, Claim evidence and all
        # domain checks. No rule engine or fake merge decision lives here.
        result = subprocess.run(
            [
                str(python),
                str(cli),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--knowledge-root",
                str(knowledge),
                "--rules-digest",
                args.rules_digest,
                "--catalog",
                str(catalog_path),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if (
            catalog_path.read_bytes() != catalog_bytes
            or input_path.read_bytes() != input_bytes
            or package_digest(package) != entry["package_digest"]
        ):
            raise ValueError(
                "Catalog, request or installed code changed during merge check"
            )
        if not output_path.is_file():
            return incomplete(
                "Public merge-check produced no result; no success is inferred."
            )
        envelope, _ = read_object(output_path)
        if (
            envelope.get("schema_version") != "2.0"
            or envelope.get("record_kind") != "result"
        ):
            raise ValueError("Invalid public ResultEnvelope")
        print(json.dumps(envelope, ensure_ascii=True))
        if result.returncode:
            return result.returncode if result.returncode in {2, 3} else 2
        if envelope.get("status") != "ok":
            return 3
        check_status = envelope.get("data", {}).get("check_status")
        if check_status == "failed":
            return 2
        if (
            check_status != "passed"
            or envelope.get("phase") != "passed"
            or envelope.get("data", {}).get("mode") != "merge"
        ):
            return 3
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        return incomplete(str(exc), invalid=True)


if __name__ == "__main__":
    raise SystemExit(main())
