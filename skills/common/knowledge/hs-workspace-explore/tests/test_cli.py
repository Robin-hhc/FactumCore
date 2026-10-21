import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def fixture(tmp_path):
    root = Path(__file__).resolve().parents[5]
    shutil.copytree(
        root / "aiotbot-knowledge-wifi-mp/governance",
        tmp_path / "aiotbot-knowledge-wifi-mp/governance",
    )
    shutil.copyfile(root / "config.yml", tmp_path / "config.yml")
    (tmp_path / "AGENTS.md").write_text("Read project rules", encoding="utf-8")
    (tmp_path / "aiotbot-knowledge-wifi-mp/AGENTS.md").write_text(
        "Read domain rules", encoding="utf-8"
    )
    (tmp_path / "main").mkdir()
    return hashlib.sha256(
        (
            tmp_path / "aiotbot-knowledge-wifi-mp/governance/framework.lock.yaml"
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


def test_path_only_resolves_but_does_not_self_trust(tmp_path):
    fixture(tmp_path)
    result, response = call(tmp_path)
    assert result.returncode == 0 and response["data"]["state"] == "resolved"
    assert "context_ref" not in response["data"]


def test_pinned_rules_load_actual_entries_from_other_cwd(tmp_path):
    pin = fixture(tmp_path)
    result, response = call(tmp_path, pin)
    assert result.returncode == 0, response
    assert response["data"]["state"] == "context_loaded"
    context = json.loads(
        (
            tmp_path / "aiotbot-knowledge-wifi-mp" / response["data"]["context_ref"]
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


def test_actual_workflow_artifact_hashes_the_loaded_context(tmp_path):
    pin = fixture(tmp_path)
    process, response = call(
        tmp_path,
        pin,
        {"run_id": "run1", "node_id": "bind_project", "attempt_id": "first"},
    )
    assert process.returncode == 0, response
    root = tmp_path / "aiotbot-knowledge-wifi-mp"
    manifest = json.loads(
        (root / response["data"]["artifact_manifest_ref"])
        .with_suffix(".json")
        .read_bytes()
    )
    ref = response["data"]["context_ref"]
    assert (
        manifest["artifact_digests"][ref]
        == hashlib.sha256((root / ref).read_bytes()).hexdigest()
    )


def test_incomplete_workflow_never_creates_context(tmp_path):
    pin = fixture(tmp_path)
    result, response = call(tmp_path, pin, {"attempt_id": "first"})
    assert result.returncode == 2, response
    assert not (tmp_path / "aiotbot-knowledge-wifi-mp/.build").exists()
