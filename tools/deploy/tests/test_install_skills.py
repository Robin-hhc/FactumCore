"""One isolated smoke for Skill copying and the selected pip environment."""

import importlib.util
from pathlib import Path


def test_copy_skills_and_install_with_selected_python(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "skill_deploy", Path(__file__).resolve().parents[1] / "deploy.py"
    )
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    source = tmp_path / "source"
    package = source / "skills/common/knowledge/hs-knowledge-example"
    (package / "references").mkdir(parents=True)
    (package / "SKILL.md").write_text("current instructions", encoding="utf-8")
    (package / "references/guide.md").write_text("business reference", encoding="utf-8")
    lock = source / "himate/himate-knowledge-wifi-mp/runtime/requirements.lock.txt"
    lock.parent.mkdir(parents=True)
    lock.write_text("PyYAML==6.0.3\n", encoding="utf-8")
    target = tmp_path / "installed skills"
    (target / package.name).mkdir(parents=True)
    (target / package.name / "SKILL.md").write_text("old", encoding="utf-8")
    unrelated = target / "user-package/SKILL.md"
    unrelated.parent.mkdir()
    unrelated.write_text("keep", encoding="utf-8")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(backend.subprocess, "run", run)
    selected_python = str(tmp_path / "chosen-env/python.exe")
    assert backend.main([
        "--source-root", str(source), "--skills-root", str(target),
        "--python", selected_python,
    ]) == 0
    assert (target / package.name / "SKILL.md").read_text(encoding="utf-8") == "current instructions"
    assert (target / package.name / "references/guide.md").read_text(encoding="utf-8") == "business reference"
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert set(path.name for path in target.iterdir()) == {package.name, "user-package"}
    assert calls == [([selected_python, "-m", "pip", "install", "-r", str(lock)], {"check": True})]
