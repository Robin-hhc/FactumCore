"""Public empty-library build/activate; old journals never provide card proof."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sealed(value):
    result = {k: v for k, v in value.items() if k != "digest"}
    return {**result, "digest": hashlib.sha256(canonical(result)).hexdigest()}


class EmptyIndex:
    def __init__(self, base):
        self.base, self.root = base, base / "knowledge-root"
        self.root.mkdir()
        source = Path(__file__).resolve().parents[6] / "aiotbot-knowledge-wifi-mp/governance"
        shutil.copytree(source, self.root / "governance", ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "knowledge").mkdir()
        (self.root / "knowledge/index.md").write_bytes(b"# Empty knowledge\n")
        self.rules = hashlib.sha256((self.root / "governance/framework.lock.yaml").read_bytes()).hexdigest()
        self.number = 0

    def journal(self, operation="legacy", **changes):
        value = sealed({"schema_version": "2.0", "record_kind": "transaction_journal", "operation_id": operation,
            "rules_digest": "a" * 64, "tool_identity": {"skill": "hs-fixture", "package_digest": "0" * 64,
            "runtime": "fixture", "requirements_digest": "0" * 64}, "status": "committed", "entries": [],
            "view_ref": ".build/operations/legacy/view.json", "view_digest": "1" * 64,
            "proof_ref": "logs/operations/legacy/proof.json", "proof_digest": "2" * 64, **changes})
        path = self.root / "logs/operations" / operation / "journal.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(value))
        return path

    def call(self, action, request, expected=0, skill="hs-knowledge-index-build"):
        self.number += 1
        incoming, outgoing = self.base / (str(self.number) + ".in.json"), self.base / (str(self.number) + ".out.json")
        incoming.write_bytes(canonical(request))
        command = [sys.executable, str(Path(__file__).parents[2] / skill / "scripts/cli.py"),
            "--input", str(incoming), "--output", str(outgoing), "--knowledge-root", str(self.root),
            "--rules-digest", self.rules]
        if action:
            command += ["--action", action]
        result = subprocess.run(command, capture_output=True, timeout=60)
        response = json.loads(outgoing.read_bytes())
        assert result.returncode == expected, (response, result.stderr)
        return response


@pytest.mark.parametrize("status", ["committed", "rolled_back"])
def test_public_empty_index_and_activation_allow_only_unrelated_old_terminal_journal(tmp_path, status):
    trial = EmptyIndex(tmp_path)
    old = trial.journal(status=status)
    before = old.read_bytes()
    built = trial.call("build", {"operation_id": "index", "channel": "local"})
    manifest = json.loads((trial.root / built["data"]["generation_ref"]).read_bytes())
    assert manifest["documents"] == {} and manifest["qualifications"] == {}
    activated = trial.call("activate", {"operation_id": "activate", "generation_ref": built["data"]["generation_ref"], "expected_active": None})
    assert activated["data"]["activated"] is True
    assert old.read_bytes() == before


@pytest.mark.parametrize("kind", ["prepared", "recovery_required", "bad-seal", "bad-op", "bad-schema", "bad-kind", "bad-rules", "bad-shape", "same-operation"])
def test_public_index_writer_barrier_rejects_unverified_or_own_old_journals(tmp_path, kind):
    trial = EmptyIndex(tmp_path)
    built = trial.call("build", {"operation_id": "before", "channel": "local"})
    changes = {"status": kind} if kind in {"prepared", "recovery_required"} else {}
    changes.update({"operation_id": "wrong"} if kind == "bad-op" else {})
    changes.update({"schema_version": "3.0"} if kind == "bad-schema" else {})
    changes.update({"record_kind": "apply_result"} if kind == "bad-kind" else {})
    changes.update({"rules_digest": "unknown"} if kind == "bad-rules" else {})
    changes.update({"entries": {}} if kind == "bad-shape" else {})
    old = trial.journal(**changes)
    if kind == "bad-seal":
        value = json.loads(old.read_bytes())
        value["digest"] = "0" * 64
        old.write_bytes(canonical(value))
    before = old.read_bytes()
    operation = "legacy" if kind == "same-operation" else "index"
    for action, request in [("build", {"operation_id": operation}),
                            ("activate", {"operation_id": operation, "generation_ref": built["data"]["generation_ref"], "expected_active": None})]:
        result = trial.call(action, request, expected=3)
        assert result["diagnostics"][0]["code"] == "TRANSACTION_PENDING"
        assert not (trial.root / "artifacts/indexes/local/active.json").exists()
        assert old.read_bytes() == before


def test_old_terminal_journal_never_qualifies_an_unaccepted_current_card(tmp_path):
    trial = EmptyIndex(tmp_path)
    source = trial.root / "docs-raw/specs/fixture.txt"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"Explicit fixture design statement.\n")
    captured = trial.call(None, {"operation_id": "raw", "source_id": "fixture", "source_path": "docs-raw/specs/fixture.txt"},
                         skill="hs-knowledge-source-capture")
    bundle = json.loads((trial.root / captured["data"]["bundle_ref"]).read_bytes())
    snapshot = bundle["snapshots"][0]
    (trial.root / "governance/sources.lock.yaml").write_text(yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"],
        "snapshots": bundle["snapshots"]}), encoding="utf-8")
    template = (trial.root / "governance/templates/rule.md").read_text(encoding="utf-8")
    for key, value in {"card_id": "unaccepted", "title": "Unaccepted fixture", "summary": "No approval exists", "owner": "fixture",
                       "evidence_ref": "e1", "source_id": "fixture", "snapshot_id": snapshot["snapshot_id"], "claim_id": "c1",
                       "claim_text": "Explicit fixture design statement."}.items():
        template = template.replace("{{" + key + "}}", value)
    target = trial.root / "knowledge/rules/unaccepted.md"
    target.parent.mkdir()
    target.write_text(template.replace("lifecycle: draft", "lifecycle: stable"), encoding="utf-8")
    (target.parent / "index.md").write_text("# Rules\n[Unaccepted](unaccepted.md)\n", encoding="utf-8")
    old = trial.journal()
    before = old.read_bytes()
    result = trial.call("build", {"operation_id": "unaccepted-index"}, expected=3)
    assert result["diagnostics"][0]["code"] == "CARD_PROOF_MISSING"
    assert not list((trial.root / "artifacts").rglob("index.sqlite"))
    assert old.read_bytes() == before
