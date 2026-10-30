import json
from pathlib import Path
import subprocess
import sys
import shutil

import importlib.util as _repository_importlib
from pathlib import Path as _RepositoryPath
_repository_spec = _repository_importlib.spec_from_file_location(
    "test_index_cli_repository_runtime_fixture",
    _RepositoryPath(__file__).resolve().parents[5] / "himate-knowledge-wifi-mp/evals/contract_test_support.py",
)
_repository_fixture = _repository_importlib.module_from_spec(_repository_spec)
_repository_spec.loader.exec_module(_repository_fixture)


def test_unrecognized_action_does_not_create_index(tmp_path):
    root = Path(__file__).resolve().parents[5]
    import hashlib

    domain = tmp_path / "domain"
    shutil.copytree(root / "himate-knowledge-wifi-mp/governance", domain / "governance")
    _repository_fixture.copy_runtime(domain)
    (domain / "artifacts").mkdir()
    request = tmp_path / "request.json"
    response = tmp_path / "response.json"
    request.write_text(
        json.dumps({"operation_id": "invalid-index-action"}), encoding="utf-8"
    )
    before = set((domain / "artifacts").rglob("index.sqlite"))
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
            "--action",
            "not-a-real-action",
        ],
        capture_output=True,
        check=False,
    )
    assert call.returncode == 2
    assert json.loads(response.read_bytes())["status"] == "error"
    assert set((domain / "artifacts").rglob("index.sqlite")) == before
