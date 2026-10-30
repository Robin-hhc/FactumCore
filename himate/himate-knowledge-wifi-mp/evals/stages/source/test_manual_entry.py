"""Public manual calls need actual business inputs, not deployment registrations."""

import json
import subprocess

import pytest


@pytest.mark.parametrize("catalog", [None, "broken"])
def test_manual_scan_uses_runtime_without_installed_skills(harness, catalog):
    harness.write("docs-raw/specs/source.md", b"Manual first-run source.\n")
    incoming, outgoing = harness.base / "manual-in.json", harness.base / "manual-out.json"
    incoming.write_text(json.dumps({"operation_id": "manual", "workflow": {"attempt_id": "unused"}}), encoding="utf-8")
    assert not (harness.base / "installed").exists()
    command = [*harness.command("source"),
               "--input", str(incoming), "--output", str(outgoing), "--knowledge-root", str(harness.root),
               "--action", "scan"]
    if catalog:
        harness.catalog.write_text("not a valid catalog", encoding="utf-8")
        command += ["--catalog", str(harness.catalog)]
    process = subprocess.run(command, capture_output=True, check=False)
    response = json.loads(outgoing.read_bytes())
    assert process.returncode == 0, response
    assert response["rules_digest"] == harness.rules
    assert response["data"]["scan_ref"]
    assert not (harness.root / "logs/workflows").exists()
    assert not (harness.base / "installed").exists()


def test_manual_scan_still_rejects_changed_fixed_rules(harness):
    path = harness.root / "governance/contracts/knowledge.py"
    path.write_bytes(path.read_bytes() + b"\n# changed without updating the rule lock\n")
    incoming, outgoing = harness.base / "manual-in.json", harness.base / "manual-out.json"
    incoming.write_text(json.dumps({"operation_id": "manual"}), encoding="utf-8")
    process = subprocess.run([*harness.command("source"),
                              "--input", str(incoming), "--output", str(outgoing), "--knowledge-root", str(harness.root),
                              "--action", "scan"],
                             capture_output=True, check=False)
    response = json.loads(outgoing.read_bytes())
    assert process.returncode == 2, response
    assert response["diagnostics"][0]["code"] == "RULE_DIGEST_MISMATCH"
