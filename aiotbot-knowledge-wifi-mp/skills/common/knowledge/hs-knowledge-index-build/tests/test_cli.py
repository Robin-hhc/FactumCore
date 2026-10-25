import json
from pathlib import Path
import subprocess
import sys
import shutil


def test_unrecognized_action_does_not_create_index(tmp_path):
    root = Path(__file__).resolve().parents[6]
    import hashlib

    domain = tmp_path / "domain"
    shutil.copytree(root / "aiotbot-knowledge-wifi-mp/governance", domain / "governance")
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
