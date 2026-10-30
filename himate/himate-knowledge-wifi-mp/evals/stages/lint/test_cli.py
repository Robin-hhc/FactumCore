"""Public failures cannot create or publish knowledge."""
import json
from pathlib import Path
import subprocess
import sys


def test_unavailable_rules_return_incomplete_without_creating_knowledge(tmp_path):
    cli = Path(__file__).resolve().parents[3] / "knowledge.py"
    output = tmp_path / "report.json"
    result = subprocess.run([sys.executable, str(cli), "lint", "--json", "--knowledge-root", str(tmp_path), "--rules-digest", "a" * 64, "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 2
    # An unavailable execution root is rejected by the public CLI before a
    # formal lint report exists; no content check or result file is published.
    assert json.loads(result.stdout)["status"] == "error"
    assert not (tmp_path / "knowledge").exists()
    assert not output.exists()
