"""Navigation repairs known stale scaffolding while preserving project prose."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


DOMAIN = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("navigation_contracts", DOMAIN / "evals/contract_test_support.py")
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)
production = SUPPORT.module("production")


def write(root, ref, text):
    path = root / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_navigation_repairs_legacy_state_in_candidate_without_mutating_formal_files(tmp_path):
    leaf = write(tmp_path, "knowledge/concepts/flows/index.md",
                 "# Flows\n\n当前没有已落位的正式业务卡。项目补充说明保留。\n\n业务维护者的自定义说明。\n")
    root = write(tmp_path, "knowledge/index.md", "# Knowledge\n\n当前正式业务卡为空。根页补充说明保留。\n")
    before = {path: path.read_bytes() for path in (leaf, root)}
    candidate = production._navigation(SimpleNamespace(root=tmp_path), [], {
        "flow": {"path": "knowledge/concepts/flows/flow.md", "metadata": {"title": "Flow", "lifecycle": "stable"}}})
    leaf_text = candidate["knowledge/concepts/flows/index.md"].decode()
    assert not any(line.startswith("当前没有已落位的正式业务卡。") for line in leaf_text.splitlines())
    assert "项目补充说明保留。" in leaf_text and "业务维护者的自定义说明。" in leaf_text
    assert "[Flow](flow.md)" in leaf_text
    root_text = candidate["knowledge/index.md"].decode()
    assert not any(line.startswith("当前正式业务卡为空。") for line in root_text.splitlines())
    assert "根页补充说明保留。" in root_text
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_navigation_preserves_custom_and_quoted_status_text(tmp_path):
    leaf_text = '# Rules\n\n项目说明引用“当前没有已落位的正式业务卡。”作为历史示例。\n[Existing](existing.md)\n'
    write(tmp_path, "knowledge/rules/index.md", leaf_text)
    write(tmp_path, "knowledge/index.md", "# Custom root\n\n项目自管根导航。\n")
    candidate = production._navigation(SimpleNamespace(root=tmp_path), [], {
        "rule": {"path": "knowledge/rules/rule.md", "metadata": {"title": "Rule", "lifecycle": "stable"}}})
    assert candidate["knowledge/rules/index.md"].decode().startswith(leaf_text)
    assert "knowledge/index.md" not in candidate


def test_distributed_navigation_does_not_assert_an_empty_runtime_library():
    paths = list((DOMAIN / "knowledge").rglob("index.md"))
    assert len(paths) >= 8
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "当前正式业务卡为空。" not in text, path
        assert "当前没有已落位的正式业务卡。" not in text, path
    for relative, stale in (("knowledge/AGENTS.md", "正式业务卡仍为空"),
                            ("governance/AGENTS.md", "当前是空登记"),
                            ("governance/index.md", "当前为空")):
        assert stale not in (DOMAIN / relative).read_text(encoding="utf-8"), relative
