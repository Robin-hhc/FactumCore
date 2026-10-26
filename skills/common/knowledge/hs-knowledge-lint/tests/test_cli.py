"""Public failures cannot create or publish knowledge."""
import json
from pathlib import Path
import subprocess
import sys


def test_unavailable_rules_return_incomplete_without_creating_knowledge(tmp_path):
    cli = Path(__file__).resolve().parents[1] / "scripts/cli.py"
    output = tmp_path / "report.json"
    result = subprocess.run([sys.executable, str(cli), "--knowledge-root", str(tmp_path), "--rules-digest", "a" * 64, "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "incomplete"
    assert not (tmp_path / "knowledge").exists()
    assert not output.exists()
