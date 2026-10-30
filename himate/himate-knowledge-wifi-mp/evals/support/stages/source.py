"""Synthetic domain copied from current pinned contracts; no production originals."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml


_runtime_spec = importlib.util.spec_from_file_location(
    "source_repository_fixture",
    Path(__file__).resolve().parents[5] / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py",
)
_runtime_fixture = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(_runtime_fixture)


def hashed(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()




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
                    / "himate/himate-knowledge-wifi-mp/governance"
                ),
            )
        )
        shutil.copytree(
            source,
            self.root / "governance",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        _runtime_fixture.copy_runtime(self.root)
        (self.root / ".synthetic-test-root").write_text(
            "isolated mechanism fixture", encoding="utf-8"
        )
        # New full scans include one configured local directory. Missing-root
        # tests explicitly remove this fixture-owned, empty source mapping.
        external = base / "empty-dbox"
        external.mkdir()
        self.write("docs-raw/sources/dbox.local.yml", yaml.safe_dump({
            "schema_version": "1.0", "path": str(external),
        }, sort_keys=False).encode())
        self.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
        self.rules = hashed((self.root / "governance/framework.lock.yaml").read_bytes())
        self.packages = _runtime_fixture.ROOT / "skills/common/knowledge"
        entries = {}
        self.catalog = base / "catalog.json"
        self.catalog.write_bytes(
            canonical({"schema_version": "2.0", "skills": entries})
        )
        self.sequence = 0

    def command(self, slug):
        return _runtime_fixture.stage_command(slug, self.root)

    def write(self, ref, data):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return ref

    def record(self, ref):
        return json.loads((self.root / ref).read_text(encoding="utf-8"))

    def bundle_path(self, bundle, ref):
        """Physical bytes of this explicitly supplied bundle, never a glob."""
        matches = [row for row in bundle.get("staged_objects", []) if row["final_ref"] == ref]
        return self.root / (matches[0]["stage_ref"] if matches else ref)

    def publish_bundle(self, bundle):
        """Establish synthetic formal-history fixtures; not a P6 success claim."""
        for row in bundle.get("staged_objects", []):
            raw = self.bundle_path(bundle, row["final_ref"]).read_bytes()
            assert hashed(raw) == row["sha256"] and len(raw) == row["bytes"]
            self.write(row["final_ref"], raw)

    def run(self, slug, request, action=None, expected=0):
        self.sequence += 1
        incoming, outgoing = (
            self.base / f"in-{self.sequence}.json",
            self.base / f"out-{self.sequence}.json",
        )
        incoming.write_bytes(canonical(request))
        argv = [
            *_runtime_fixture.stage_command(slug, self.root),
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
        process = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", check=False)
        assert "Traceback" not in process.stderr, process.stderr
        assert outgoing.exists() or process.stdout, (process.returncode, process.stdout, process.stderr)
        response = json.loads(outgoing.read_text(encoding="utf-8") if outgoing.exists() else process.stdout)
        assert process.returncode == expected, response
        return response

    def capture(self, operation="op", text=b"# Source\nSynthetic evidence.\n"):
        self.write("docs-raw/specs/source.md", text)
        response = self.run(
            "source",
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
