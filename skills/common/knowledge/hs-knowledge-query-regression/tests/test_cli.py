import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil


def test_empty_case_set_never_activates(tmp_path):
    root = Path(__file__).resolve().parents[5]
    domain = tmp_path / "domain"
    shutil.copytree(root / "aiotbot-knowledge-wifi-mp/governance", domain / "governance")
    request = tmp_path / "request.json"
    response = tmp_path / "response.json"
    request.write_text(
        json.dumps({"operation_id": "regression-empty", "cases": []}), encoding="utf-8"
    )
    call = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/cli.py"),
            "--input",
            str(request),
            "--output",
            str(response),
            "--knowledge-root",
            str(domain),
            "--rules-digest",
            hashlib.sha256(
                (domain / "governance/framework.lock.yaml").read_bytes()
            ).hexdigest(),
        ],
        capture_output=True,
    )
    assert call.returncode == 2
    assert (
        json.loads(response.read_bytes())["diagnostics"][0]["code"]
        == "REGRESSION_CASES_REQUIRED"
    )


def test_cases_without_expected_behavior_never_activate(tmp_path):
    root = Path(__file__).resolve().parents[5]
    domain = tmp_path / "domain"
    shutil.copytree(root / "aiotbot-knowledge-wifi-mp/governance", domain / "governance")
    request, response = tmp_path / "request.json", tmp_path / "response.json"
    request.write_text(
        json.dumps(
            {
                "operation_id": "regression-vacuous",
                "generation_ref": "missing",
                "cases": [{"id": "empty-oracle", "query": "needle"}],
            }
        ),
        encoding="utf-8",
    )
    call = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/cli.py"),
            "--input",
            str(request),
            "--output",
            str(response),
            "--knowledge-root",
            str(domain),
            "--rules-digest",
            hashlib.sha256(
                (domain / "governance/framework.lock.yaml").read_bytes()
            ).hexdigest(),
        ],
        capture_output=True,
    )
    assert call.returncode == 2
    assert (
        json.loads(response.read_bytes())["diagnostics"][0]["code"]
        == "REGRESSION_ASSERTION_REQUIRED"
    )
