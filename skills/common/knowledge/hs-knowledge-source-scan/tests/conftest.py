"""Synthetic domain copied from current pinned contracts; no production originals."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


def hashed(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def package_hash(package):
    files = {}
    for path in sorted(package.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(package)
        if "__pycache__" in rel.parts or "tests" in rel.parts:
            continue
        if (
            rel.as_posix() == "SKILL.md"
            or rel.parts[0] in {"scripts", "references", "artifacts"}
            or len(rel.parts) == 1
            and path.name.startswith("requirements")
            and path.suffix == ".txt"
        ):
            files[rel.as_posix()] = hashed(path.read_bytes())
    return hashed(canonical(files))


class Harness:
    def __init__(self, base):
        self.base = base
        self.root = base / "synthetic-knowledge"
        self.root.mkdir()
        source = Path(
            os.environ.get(
                "AIOT_DOMAIN_FIXTURE",
                str(
                    Path(__file__).resolve().parents[5]
                    / "himate-knowledge-wifi-mp/governance"
                ),
            )
        )
        shutil.copytree(
            source,
            self.root / "governance",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (self.root / ".synthetic-test-root").write_text(
            "isolated mechanism fixture", encoding="utf-8"
        )
        self.rules = hashed((self.root / "governance/framework.lock.yaml").read_bytes())
        self.packages = Path(__file__).resolve().parents[2]
        entries = {}
        for package in self.packages.glob("hs-knowledge-*"):
            if (package / "scripts/cli.py").exists():
                entries[package.name] = {
                    "root": str(package),
                    "entry": "scripts/cli.py",
                    "python": sys.executable,
                    "package_digest": package_hash(package),
                }
        self.catalog = base / "catalog.json"
        self.catalog.write_bytes(
            canonical({"schema_version": "2.0", "skills": entries})
        )
        self.sequence = 0

    def write(self, ref, data):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return ref

    def record(self, ref):
        return json.loads((self.root / ref).read_text(encoding="utf-8"))

    def run(self, slug, request, action=None, expected=0):
        self.sequence += 1
        incoming, outgoing = (
            self.base / f"in-{self.sequence}.json",
            self.base / f"out-{self.sequence}.json",
        )
        incoming.write_bytes(canonical(request))
        cli = self.packages / ("hs-knowledge-" + slug) / "scripts/cli.py"
        argv = [
            sys.executable,
            str(cli),
            "--input",
            str(incoming),
            "--output",
            str(outgoing),
            "--knowledge-root",
            str(self.root),
            "--rules-digest",
            self.rules,
            "--catalog",
            str(self.catalog),
        ]
        if action:
            argv += ["--action", action]
        process = subprocess.run(argv, capture_output=True, text=True, check=False)
        assert "Traceback" not in process.stderr, process.stderr
        response = json.loads(outgoing.read_text(encoding="utf-8"))
        assert process.returncode == expected, response
        return response

    def capture(self, operation="op", text=b"# Source\nSynthetic evidence.\n"):
        self.write("docs-raw/specs/source.md", text)
        response = self.run(
            "source-prepare",
            {
                "operation_id": operation,
                "source_path": "docs-raw/specs/source.md",
                "source_id": "synthetic",
            },
         action="capture")
        return response["data"]["bundle_ref"], self.record(
            response["data"]["bundle_ref"]
        )

    def card(self, identity, bundle, *, lifecycle="draft", relation=None, claim=None):
        snapshot = bundle["snapshots"][0]
        metadata = {
            "schema_version": "2.0",
            "id": identity,
            "profile": "rule",
            "title": identity,
            "summary": "Synthetic fixture only",
            "lifecycle": lifecycle,
            "review_mode": "manual_document",
            "owner": "synthetic",
            "scope": {"applicability": "unknown", "contexts": []},
            "aliases": [],
            "sources": [
                {
                    "evidence_ref": "e1",
                    "source_id": snapshot["source_id"],
                    "snapshot_id": snapshot["snapshot_id"],
                    "locator": {"kind": "lines", "start": 1, "end": 2},
                }
            ],
            "claims": [
                {
                    "id": claim or identity + "-claim",
                    "text_ref": "#statement",
                    "evidence_kind": "design",
                    "source_refs": ["e1"],
                    "context_ids": [],
                    "usage": "guidance",
                    "verification_requirements": [],
                }
            ],
            "relations": relation or [],
        }
        profiles = yaml.safe_load(
            (self.root / "governance/schemas/profiles.yaml").read_text(encoding="utf-8")
        )
        body = '<a id="statement"></a>\nSynthetic fixture statement.\n'
        body += "".join(
            "\n## " + title + "\nSynthetic fixture.\n"
            for title in profiles["profiles"]["rule"]["required_sections"]
        )
        return (
            "---\n"
            + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
            + "---\n"
            + body
        ).encode()

    def plan(self, operation="op"):
        ref, bundle = self.capture(operation)
        candidate = self.write(".build/candidates/new.md", self.card("new", bundle))
        planned = self.run(
            "view-materialize",
            {
                "operation_id": operation,
                "bundle_ref": ref,
                "decisions": [
                    {
                        "candidate_id": "candidate",
                        "decision": "create",
                        "reason": "Synthetic mechanism test",
                        "card_inputs": [candidate],
                    }
                ],
            },
        )
        self.materialized = planned["data"]
        return planned["data"]["plan_ref"], bundle

    def view(self, operation="op"):
        _, bundle = self.plan(operation)
        return self.materialized["view_ref"], bundle


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)
