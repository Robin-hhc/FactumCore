"""Public raw CLI from an arbitrary working directory, using synthetic documents."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
CLI = ROOT / "skills/common/knowledge/_shared/cli.py"


def invoke(tmp_path, *args):
    process = subprocess.run(
        [sys.executable, str(CLI), "document", *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert "Traceback" not in process.stderr
    return process.returncode, json.loads(process.stdout)


def test_public_capture_and_restore_survive_original_deletion(tmp_path):
    knowledge = tmp_path / "K"
    shutil.copytree(ROOT / "aiot-wifi-knowledge/governance", knowledge / "governance")
    raw = knowledge / "docs-raw/specs/example.md"
    raw.parent.mkdir(parents=True)
    raw.write_bytes("# Synthetic\nOnly a fixture.\n".encode())
    before = raw.read_bytes()
    code, capture = invoke(
        tmp_path,
        "capture",
        "--knowledge-root",
        str(knowledge),
        "--path",
        "docs-raw/specs/example.md",
        "--source-id",
        "fixture-doc",
    )
    assert code == 0, capture
    assert raw.read_bytes() == before
    raw.unlink()
    result = capture["result"]
    code, restored = invoke(
        tmp_path,
        "load-capture",
        "--knowledge-root",
        str(knowledge),
        "--bundle-ref",
        result["bundle_ref"],
        "--manifest-digest",
        result["manifest_digest"],
    )
    assert code == 0, restored
    assert restored["result"] == result
    assert not (knowledge / "governance/sources.lock.yaml").exists()
    assert not (knowledge / "knowledge").exists()


def test_remote_request_fails_structurally_without_fetch(tmp_path):
    code, output = invoke(
        tmp_path,
        "capture",
        "--knowledge-root",
        str(ROOT / "aiot-wifi-knowledge"),
        "--path",
        "https://invalid.example/never-fetch",
        "--source-id",
        "fixture-doc",
    )
    assert code == 2
    assert output["status"] == "invalid"
    assert output["diagnostics"][0]["code"]
