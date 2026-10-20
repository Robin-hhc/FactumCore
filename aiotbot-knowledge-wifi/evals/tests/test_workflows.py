"""Workflow source checks and optional pinned upstream-loader integration."""

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / "aiotbot-knowledge-wifi/evals/validate_design.py"
INSTALLER = (
    ROOT / "skills/common/knowledge/hs-workspace-explore/scripts/install_catalog.py"
)


def validator_module():
    spec = importlib.util.spec_from_file_location("workflow_validation", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_packages(root):
    module = validator_module()
    for skill in module.SKILLS:
        package = root / "skills/common/knowledge" / skill
        mapping = module.ARTIFACT_SCOPE[skill]
        files = {
            "SKILL.md": f"---\nname: {skill}\ndescription: isolated synthetic contract fixture\n---\n# fixture\n",
            "scripts/cli.py": "# fixture\n",
            "scripts/support.py": "# fixture\n",
            "tests/test_cli.py": "# fixture\n",
            "requirements.lock.txt": "# fixture\n",
            "requirements-dev.lock.txt": "# fixture\n",
            "artifacts/templates/result.md": "# Result\n",
            "artifacts/writing-guide.md": "# Writing\n",
            "artifacts/review-guide.md": "# Review\n",
        }
        contract = {
            "id": skill + "-result",
            "title": skill,
            "required": True,
            "template": "templates/result.md",
            "writing_guide": "writing-guide.md",
            "review_guide": "review-guide.md",
            "default_location": {"kind": "markdown_file"},
            "applies_to": {"node_ids": mapping[0]},
            "required_on": {"exit_ids": mapping[1]},
        }
        files["artifacts/result.yaml"] = yaml.safe_dump(contract)
        for relative, data in files.items():
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
    shutil.copytree(ROOT / "workflows", root / "workflows")
    return root


def test_templates_exist_with_real_user_gate_and_separate_handoffs():
    ingest = yaml.safe_load(
        (
            ROOT / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
        ).read_bytes()
    )
    governance = yaml.safe_load(
        (
            ROOT / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml"
        ).read_bytes()
    )
    production = {n["id"]: n for n in ingest["nodes"]}
    nodes = {n["id"]: n for n in governance["nodes"]}
    assert len(production) == 5
    assert production["governance_handoff"]["exits"][0]["target"] == "__end__"
    gate = nodes["final_view_user_gate"]
    assert (gate["type"], gate["owner"]) == ("gate", "user")
    assert gate["on_pass"] == "record_confirmation"
    assert gate["on_fail"] == "revise_candidate"
    assert "skill" not in gate
    assert "verify_merge" not in nodes and "maintain_knowledge" not in nodes
    assert nodes["publish_handoff"]["exits"][0]["target"] == "__end__"
    manual_nodes = (
        "prepare_confirmation",
        "final_view_user_gate",
        "record_confirmation",
    )
    assert not any(
        nodes[name].get("skill") == "hs-knowledge-local-check" for name in manual_nodes
    )


def test_design_validation_checks_package_contracts_and_owners(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    assert module.validate(source) == []
    contract_path = (
        source
        / "skills/common/knowledge/hs-knowledge-source-capture/artifacts/result.yaml"
    )
    contract = yaml.safe_load(contract_path.read_bytes())
    contract["default_location"]["path"] = "node-result.md"
    contract_path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert module.validate(source) == []  # a standard default path is legal
    workflow = source / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml"
    document = yaml.safe_load(workflow.read_bytes())
    next(n for n in document["nodes"] if n["id"] == "final_view_user_gate")["owner"] = (
        "coder"
    )
    workflow.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert any("user gate" in error.lower() for error in module.validate(source))


def test_missing_reference_or_wrong_artifact_exit_is_rejected(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-knowledge-apply/artifacts"
    (package / "review-guide.md").unlink()
    assert any("review_guide" in error for error in module.validate(source))
    (package / "review-guide.md").write_text("# Review\n", encoding="utf-8")
    contract = yaml.safe_load((package / "result.yaml").read_bytes())
    contract["required_on"]["exit_ids"] = ["made_up_success"]
    (package / "result.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert any("exit" in error.lower() for error in module.validate(source))


def test_cross_template_edge_and_apply_after_index_failure_rejected(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml"
    doc = yaml.safe_load(path.read_bytes())
    node = next(n for n in doc["nodes"] if n["id"] == "query_regression")
    next(e for e in node["exits"] if e["id"] == "blocked")["target"] = "apply_view"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert any("transition" in e.lower() for e in module.validate(source))


def test_real_pinned_openflow_loader(tmp_path):
    upstream = os.environ.get("FACTUM_OPENFLOW_SOURCE")
    if not upstream:
        pytest.skip(
            "set FACTUM_OPENFLOW_SOURCE to verified OpenFlow@1901a4 checkout for upstream integration"
        )
    source = fixture_packages(tmp_path / "fixture")
    destination = tmp_path / "installed"
    installed = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--source-root",
            str(source),
            "--destination",
            str(destination),
            "--python",
            sys.executable,
        ],
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stderr
    result = validator_module().validate_openflow(Path(upstream), destination)
    assert result["workflow_ids"] == ["hs-knowledge-ingest", "hs-knowledge-lint"]
    assert result["skill_count"] == 18
    assert result["contract_count"] == 18


def test_merge_wrapper_missing_input_is_incomplete(tmp_path):
    wrapper = ROOT / "aiotbot-knowledge-wifi/check.py"
    result = subprocess.run(
        [sys.executable, str(wrapper)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 3
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "blocked" and envelope["phase"] == "incomplete"


def wrapper_fixture(tmp_path):
    package = tmp_path / "trusted merge package"
    cli = package / "scripts/cli.py"
    cli.parent.mkdir(parents=True)
    cli.write_text(
        """import argparse,json
p=argparse.ArgumentParser()
for name in ('input','output','knowledge-root','rules-digest','catalog'): p.add_argument('--'+name,required=True)
a=p.parse_args(); request=json.load(open(a.input,encoding='utf-8'))
status=request['fixture_status']
result={'schema_version':'2.0','record_kind':'result','status':'ok','phase':status,
 'data':{'check_status':status,'mode':'merge','merge_check_ref':'logs/fixture.json',
 'knowledge_root':a.knowledge_root,'rules_digest':a.rules_digest},'diagnostics':[]}
with open(a.output,'w',encoding='utf-8') as f:json.dump(result,f)
""",
        encoding="utf-8",
    )
    files = {"scripts/cli.py": hashlib.sha256(cli.read_bytes()).hexdigest()}
    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "skills": {
                    "hs-knowledge-merge-check": {
                        "root": str(package),
                        "entry": "scripts/cli.py",
                        "python": sys.executable,
                        "package_digest": digest,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return catalog, cli


@pytest.mark.parametrize(
    ("status", "expected"), [("passed", 0), ("failed", 2), ("incomplete", 3)]
)
def test_wrapper_handles_results_without_treating_exit_zero_as_pass(
    tmp_path, status, expected
):
    catalog, _ = wrapper_fixture(tmp_path)
    request = tmp_path / "input.json"
    request.write_text(json.dumps({"fixture_status": status}), encoding="utf-8")
    output = tmp_path / "result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "aiotbot-knowledge-wifi/check.py"),
            "--catalog",
            str(catalog),
            "--input",
            str(request),
            "--output",
            str(output),
            "--rules-digest",
            "a" * 64,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    assert json.loads(result.stdout)["data"]["check_status"] == status
    assert json.loads(output.read_bytes())["data"]["knowledge_root"] == str(
        ROOT / "aiotbot-knowledge-wifi"
    )
    assert json.loads(output.read_bytes())["data"]["rules_digest"] == "a" * 64


def test_wrapper_rejects_changed_installed_code_before_execution(tmp_path):
    catalog, cli = wrapper_fixture(tmp_path)
    cli.write_text(
        "raise AssertionError('must never execute changed code')\n", encoding="utf-8"
    )
    request = tmp_path / "input.json"
    request.write_text('{"fixture_status":"passed"}', encoding="utf-8")
    output = tmp_path / "result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "aiotbot-knowledge-wifi/check.py"),
            "--catalog",
            str(catalog),
            "--input",
            str(request),
            "--output",
            str(output),
            "--rules-digest",
            "a" * 64,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert not output.exists()
    assert "differs" in json.loads(result.stdout)["diagnostics"][0]["message"]


def test_wrapper_refuses_an_existing_result_instead_of_reusing_it(tmp_path):
    catalog, _ = wrapper_fixture(tmp_path)
    request = tmp_path / "input.json"
    request.write_text('{"fixture_status":"incomplete"}', encoding="utf-8")
    output = tmp_path / "result.json"
    old = b'{"old":"not this invocation"}'
    output.write_bytes(old)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "aiotbot-knowledge-wifi/check.py"),
            "--catalog",
            str(catalog),
            "--input",
            str(request),
            "--output",
            str(output),
            "--rules-digest",
            "a" * 64,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert output.read_bytes() == old


def test_shell_wrapper_preserves_spaces_and_incomplete_exit(tmp_path):
    shell = os.environ.get("FACTUM_POSIX_SHELL")
    if not shell:
        pytest.skip("explicit FACTUM_POSIX_SHELL required to test POSIX wrapper")
    cwd = tmp_path / "working directory with spaces"
    cwd.mkdir()
    env = dict(os.environ, FACTUM_PYTHON=Path(sys.executable).as_posix())
    result = subprocess.run(
        [shell, (ROOT / "aiotbot-knowledge-wifi/check.sh").as_posix()],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert json.loads(result.stdout)["phase"] == "incomplete"
