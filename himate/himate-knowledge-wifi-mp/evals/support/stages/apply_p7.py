"""Actual public P7 CLIs over isolated raw/card bytes and local Git objects."""

import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest as pytest
import yaml

import importlib.util as _repository_importlib
from pathlib import Path as _RepositoryPath
_repository_spec = _repository_importlib.spec_from_file_location(
    "test_p7_actions_repository_runtime_fixture",
    _RepositoryPath(__file__).resolve().parents[5] / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py",
)
_repository_fixture = _repository_importlib.module_from_spec(_repository_spec)
_repository_spec.loader.exec_module(_repository_fixture)


ROOT = Path(__file__).resolve().parents[5]
HELPER_SPEC = importlib.util.spec_from_file_location("p7_action_helpers", Path(__file__).with_name("apply_helpers.py"))
HELPER = importlib.util.module_from_spec(HELPER_SPEC)
HELPER_SPEC.loader.exec_module(HELPER)


class PublicP7:
    def __init__(self, base):
        self.base, self.root = base, base / "k"
        self.root.mkdir()
        shutil.copytree(ROOT / "himate/himate-knowledge-wifi-mp/governance", self.root / "governance",
                        ignore=shutil.ignore_patterns("__pycache__"))
        _repository_fixture.copy_runtime(self.root)
        self.write("knowledge/index.md", b"# Knowledge\n")
        self.write(".isolated-knowledge-fixture", b"HIMATE_SYNTHETIC_FIXTURE_V2")
        self.rules_digest = HELPER.sha((self.root / "governance/framework.lock.yaml").read_bytes())
        self.calls = 0
        names = ("validation", "records", "knowledge", "source_resources", "indexing", "checks", "runtime",
                 "input_snapshot", "source_operations", "source_materials", "index_runtime", "query_runtime",
                 "query_regression", "submission", "ingest_execution", "maintenance")
        self.modules = {name: HELPER.load_contract(name) for name in names}
        self.rules = self.modules["validation"].load_rules(self.root, self.rules_digest)
        self.tool = {"skill": "hs-fixture", "package_digest": "0" * 64,
                     "requirements_digest": "0" * 64, "runtime": "fixture"}

    def write(self, ref, raw):
        target = self.root / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return ref

    def record(self, ref):
        return json.loads((self.root / ref).read_bytes())

    def context(self, operation):
        return self.modules["runtime"].OperationContext(self.root, {"operation_id": operation},
                modules=self.modules, rules=self.rules, tool=self.tool, rules_digest=self.rules_digest)

    def call(self, action, request, expected=0, skill="hs-knowledge-apply", catalog=None, environment=None):
        self.calls += 1
        incoming, outgoing = self.base / (str(self.calls) + ".in.json"), self.base / (str(self.calls) + ".out.json")
        incoming.write_bytes(HELPER.canonical(request))
        entry = [sys.executable, str(self.root / "knowledge.py"), skill.removeprefix("hs-knowledge-"), "--json"]
        command = [*entry,
                   "--input", str(incoming), "--output", str(outgoing), "--knowledge-root", str(self.root)]
        if action:
            command += ["--action", action]
        if catalog:
            command += ["--catalog", str(catalog)]
        completed = subprocess.run(command, capture_output=True, timeout=90, env=environment)
        response = json.loads(outgoing.read_bytes()) if outgoing.exists() else {}
        assert completed.returncode == expected, (response, completed.stderr.decode(errors="replace"))
        assert response.get("digest") == HELPER.sha(HELPER.canonical({key: value for key, value in response.items() if key != "digest"}))
        return response

    def content(self, operation="batch", *, omitted_heading=False, legacy_objects=True):
        original = b"Capture marker is an explicit synthetic rule.\nSecond line.\n"
        self.write("docs-raw/specs/raw.md", original)
        captured = self.call("capture", {"operation_id": operation + "-raw", "source_id": "raw",
                             "source_path": "docs-raw/specs/raw.md"}, skill="hs-knowledge-source")
        bundle = self.record(captured["data"]["bundle_ref"])
        if legacy_objects:
            # These cases deliberately exercise the legacy, already-formal
            # source protocol. New publication cases keep the capture staged.
            for entry in bundle.get("staged_objects", []):
                raw = Path(self.modules["runtime"].native_path(self.root / entry["stage_ref"])).read_bytes()
                assert len(raw) == entry["bytes"] and HELPER.sha(raw) == entry["sha256"]
                self.write(entry["final_ref"], raw)
        snapshot = bundle["snapshots"][0]
        template = (self.root / "governance/templates/rule.md").read_text(encoding="utf-8")
        for key, value in {"card_id": "batch-card", "title": "Batch card", "summary": "Capture marker",
                           "owner": "fixture", "evidence_ref": "e1", "source_id": "raw",
                           "snapshot_id": snapshot["snapshot_id"], "claim_id": "c1",
                           "claim_text": "Capture marker is an explicit synthetic rule."}.items():
            template = template.replace("{{" + key + "}}", value)
        _, front, body = template.split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["lifecycle"] = "stable"
        metadata["scope"] = {"applicability": "universal", "contexts": []}
        metadata["claims"][0]["usage"] = "current"
        metadata["sources"][0]["locator"] = {"kind": "lines", "start": 1, "end": 2}
        if omitted_heading:
            body = "\n".join(line for line in body.splitlines() if not line.startswith("## "))
        card = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        lock = yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"],
                               "snapshots": bundle["snapshots"]}, sort_keys=False).encode()
        ctx = self.context(operation)
        inputs = self.modules["input_snapshot"].capture_inputs(ctx, bundle=bundle, material={
            "current_files": [{"path": "docs-raw/specs/raw.md", "sha256": HELPER.sha(original)}]})
        view_ref = self.view(operation, {"knowledge/rules/batch-card.md": card,
                                         "governance/sources.lock.yaml": lock}, snapshots=bundle["snapshots"],
                             snapshot=inputs)
        return {"operation_id": operation, "view_ref": view_ref}

    def view(self, operation, writes, *, deletes=(), snapshots=(), snapshot=None):
        ctx = self.context(operation)
        entries = [{"path": ref, "bytes_b64": base64.b64encode(raw).decode(), "final_digest": HELPER.sha(raw),
                    "expected_old_digest": HELPER.sha((self.root / ref).read_bytes()) if (self.root / ref).exists() else None}
                   for ref, raw in writes.items()]
        removals = [{"path": ref, "expected_old_digest": HELPER.sha((self.root / ref).read_bytes())} for ref in deletes]
        view = ctx.seal({"review_mode": "manual_document", "batch_kind": "content", "writes": entries,
            "deletes": removals, "source_refs": list(snapshots),
            "baseline_digest": HELPER.sha(HELPER.canonical({"files": {
                row["path"]: row["expected_old_digest"] for row in entries + removals}})),
            "plan_ref": ctx.base + "/plan.json", "plan_digest": "0" * 64,
            "input_snapshot": snapshot or self.modules["input_snapshot"].capture_inputs(ctx),
            "target_queries": [{"id": "marker", "query": "capture marker", "required": ["batch-card"]}]}, "final_view")
        reference = ctx.base + "/view.json"
        ctx.save(reference, view)
        return reference

    def git(self, *arguments):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1")
        command = ["git", "-C", str(self.root), "-c", "core.hooksPath=" + os.devnull,
                   "-c", "commit.gpgsign=false", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                   *arguments]
        result = subprocess.run(command, capture_output=True, env=environment, timeout=30)
        assert result.returncode == 0, result.stderr
        return result.stdout.decode("utf-8").strip()
