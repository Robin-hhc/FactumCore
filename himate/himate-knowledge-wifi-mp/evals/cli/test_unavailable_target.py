"""An unavailable target never receives error-report directories."""

import json
import subprocess
import sys

import pytest

from support.contracts import KNOWLEDGE_ROOT


@pytest.mark.parametrize("existing_directory", [False, True])
def test_unavailable_target_cannot_be_created_or_populated_by_diagnostics(tmp_path, existing_directory):
    target = tmp_path / "selected-knowledge"
    if existing_directory:
        target.mkdir()
        (target / "preserved.txt").write_bytes(b"unrelated existing content")
    before = {p.relative_to(target).as_posix(): p.read_bytes()
              for p in target.rglob("*") if p.is_file()} if target.exists() else None
    result = subprocess.run([
        sys.executable, str(KNOWLEDGE_ROOT / "knowledge.py"), "ingest", "scan", "--json",
        "--knowledge-root", str(target), "--source", "docs-raw/specs/a.md",
        "--output", str(target / ".build/response.json"),
    ], capture_output=True, timeout=30)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "error"
    assert b"Traceback" not in result.stderr
    if before is None:
        assert not target.exists()
    else:
        assert {p.relative_to(target).as_posix(): p.read_bytes()
                for p in target.rglob("*") if p.is_file()} == before
        assert not (target / ".build").exists()
