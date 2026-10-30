import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


_runtime_spec = importlib.util.spec_from_file_location(
    "explore_repository_runtime_fixture",
    Path(__file__).resolve().parents[5] / "himate-knowledge-wifi-mp/evals/contract_test_support.py",
)
_runtime_fixture = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(_runtime_fixture)


def fixture(tmp_path):
    root = Path(__file__).resolve().parents[5]
    shutil.copytree(
        root / "himate-knowledge-wifi-mp/governance",
        tmp_path / "himate-knowledge-wifi-mp/governance",
    )
    _runtime_fixture.copy_runtime(tmp_path / "himate-knowledge-wifi-mp")
    shutil.copyfile(root / "config.yml", tmp_path / "config.yml")
    (tmp_path / "AGENTS.md").write_text("Read project rules", encoding="utf-8")
    (tmp_path / "himate-knowledge-wifi-mp/AGENTS.md").write_text(
        "Read domain rules", encoding="utf-8"
    )
    (tmp_path / "main").mkdir()
    return hashlib.sha256(
        (
            tmp_path / "himate-knowledge-wifi-mp/governance/framework.lock.yaml"
        ).read_bytes()
    ).hexdigest()


def call(tmp_path, pin=None, workflow=None):
    request = tmp_path / "request.json"
    response = tmp_path / "response.json"
    request.write_text(
        json.dumps(
            {
                "operation_id": "explore",
                "target_path": str(tmp_path / "main"),
                **({"workflow": workflow} if workflow is not None else {}),
            }
        ),
        encoding="utf-8",
    )
    args = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "scripts/cli.py"),
        "--input",
        str(request),
        "--output",
        str(response),
    ]
    if pin:
        args += ["--rules-digest", pin]
    result = subprocess.run(args, cwd=tmp_path.parent, capture_output=True)
    return result, json.loads(response.read_bytes())


def test_path_only_loads_current_rules_without_registration(tmp_path):
    fixture(tmp_path)
    result, response = call(tmp_path)
    assert result.returncode == 0 and response["data"]["state"] == "context_loaded"
    assert response["data"]["context_ref"]


def test_pinned_rules_load_actual_entries_from_other_cwd(tmp_path):
    pin = fixture(tmp_path)
    result, response = call(tmp_path, pin)
    assert result.returncode == 0, response
    assert response["data"]["state"] == "context_loaded"
    context = json.loads(
        (
            tmp_path / "himate-knowledge-wifi-mp" / response["data"]["context_ref"]
        ).read_bytes()
    )
    assert len(context["entries"]) == 2 and all(
        row["sha256"] for row in context["entries"]
    )
    assert context["repos"] == {} and "real_business_repo_unknown" in context["gaps"]


def test_missing_agent_entry_never_claims_loaded(tmp_path):
    pin = fixture(tmp_path)
    (tmp_path / "AGENTS.md").unlink()
    result, response = call(tmp_path, pin)
    assert result.returncode == 3 and response["status"] == "blocked"


def test_workflow_metadata_does_not_publish_skill_handoff_manifest(tmp_path):
    pin = fixture(tmp_path)
    process, response = call(
        tmp_path,
        pin,
        {"run_id": "run1", "node_id": "bind_project", "attempt_id": "first"},
    )
    assert process.returncode == 0, response
    root = tmp_path / "himate-knowledge-wifi-mp"
    assert (root / response["data"]["context_ref"]).is_file()
    assert "artifact_manifest_ref" not in response["data"]
    assert not (root / "logs/workflows").exists()


def test_incomplete_workflow_does_not_block_manual_context(tmp_path):
    pin = fixture(tmp_path)
    result, response = call(tmp_path, pin, {"attempt_id": "first"})
    assert result.returncode == 0, response
    assert response["data"]["state"] == "context_loaded"


def test_explicit_wrong_rules_digest_is_still_rejected(tmp_path):
    fixture(tmp_path)
    result, response = call(tmp_path, "0" * 64)
    assert result.returncode == 2, response
    assert response["diagnostics"][0]["code"] == "RULES_DIGEST_MISMATCH"
