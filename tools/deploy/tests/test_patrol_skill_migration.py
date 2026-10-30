"""Review rename and per-node patrol instructions upgrade as one distribution."""

from pathlib import Path
import shutil

import pytest
import yaml

from test_deploy import DOMAIN, all_target_bytes, cli, invoke, put, tree


PATROL = {
    "sync": ("sync_workspace", ["synced", "skipped"]),
    "plan": ("plan_patrol", ["needs_ingest", "needs_index", "unchanged", "blocked"]),
    "reindex": ("refresh_index", ["indexed"]),
    "complete": ("complete_patrol", ["completed", "pending"]),
}


def rename_package(packages, old, new):
    former, package = packages / old, packages / new
    assert former.resolve().is_relative_to(packages.resolve())
    assert package.resolve().is_relative_to(packages.resolve()) and not package.exists()
    former.rename(package)
    put(package, "SKILL.md", f"---\nname: {new}\ndescription: synthetic instruction\n---\n")
    return package


def declaration(package, identity, nodes, exits):
    value = yaml.safe_load((package / "artifacts/result.yaml").read_bytes())
    value.update(id=identity, required=True, applies_to={"node_ids": nodes},
                 required_on={"exit_ids": exits}, default_location={"kind": "markdown_file"})
    data = yaml.safe_dump(value).encode()
    put(package, "artifacts/result.yaml", data)
    return data


def combined_release(source):
    packages = source / "skills/common/knowledge"
    for index, name in enumerate(("source", "change-plan", "view-materialize", "lint", "record", "apply")):
        rename_package(packages, "hs-knowledge-new-" + str(index), "hs-knowledge-" + name)
    maintain = packages / "hs-knowledge-maintain"
    shutil.copytree(packages / "hs-knowledge-query", maintain)
    put(maintain, "SKILL.md", "---\nname: hs-knowledge-maintain\n---\nAll patrol tasks.\n")
    result = declaration(packages / "hs-knowledge-lint", "hs-knowledge-lint-result", ["lint_view"],
                         ["passed", "needs_material", "needs_plan", "needs_revision"])
    declaration(maintain, "hs-knowledge-maintain-result", [row[0] for row in PATROL.values()],
                [exit_id for _, exits in PATROL.values() for exit_id in exits])
    audit = yaml.safe_load((maintain / "artifacts/result.yaml").read_bytes())
    audit.update(id="hs-knowledge-code-reference-audit", applies_to={"node_ids": []}, required_on={"exit_ids": []})
    put(maintain, "artifacts/audit-result.yaml", yaml.safe_dump(audit))
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        path = source / "workflows/common/knowledge" / name / "workflow.yaml"
        workflow = yaml.safe_load(path.read_bytes())
        workflow["nodes"] = [{"id": "lint_view", "type": "skill", "skill": "hs-knowledge-lint"}]
        if name.endswith("lint"):
            workflow["entry"] = {"skill": "hs-knowledge-maintain"}
            workflow["nodes"] += [{"id": node_id, "type": "skill", "skill": "hs-knowledge-maintain"}
                                  for node_id, _ in PATROL.values()]
        path.write_text(yaml.safe_dump(workflow), encoding="utf-8")
    return result


def split_release(source):
    packages = source / "skills/common/knowledge"
    rename_package(packages, "hs-knowledge-lint", "hs-knowledge-review")
    maintain = packages / "hs-knowledge-maintain"
    for action, (node_id, exits) in PATROL.items():
        name = "hs-knowledge-patrol-" + action
        package = packages / name
        shutil.copytree(maintain / "references/results", package / "references/results")
        shutil.copytree(maintain / "artifacts", package / "artifacts")
        (package / "artifacts/audit-result.yaml").unlink()
        put(package, "SKILL.md", f"---\nname: {name}\n---\nknowledge patrol {action}\n")
        declaration(package, name + "-result", [node_id], exits)
    declaration(maintain, "hs-knowledge-maintain-result", [], [])
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        path = source / "workflows/common/knowledge" / name / "workflow.yaml"
        workflow = yaml.safe_load(path.read_bytes())
        workflow["nodes"][0]["skill"] = "hs-knowledge-review"
        if name.endswith("lint"):
            workflow["entry"] = {"skill": "hs-knowledge-patrol-sync"}
            by_node = {node: "hs-knowledge-patrol-" + action for action, (node, _) in PATROL.items()}
            for node in workflow["nodes"][1:]:
                node["skill"] = by_node[node["id"]]
        path.write_text(yaml.safe_dump(workflow), encoding="utf-8")


@pytest.mark.parametrize("fail", [False, True])
def test_review_rename_and_four_patrol_packages_upgrade_or_rollback_together(
    backend, monkeypatch, capsys, source, targets, fail,
):
    original = combined_release(source)
    assert cli(source, targets)[0] == 0
    knowledge = targets["project_root"] / DOMAIN
    business = {"logs/patrol/keep/report.json": b"original patrol history\n",
                "docs-raw/sources/dbox.local.yml": b"private directory configuration\n"}
    for name, data in business.items():
        put(knowledge, name, data)
    before = all_target_bytes(targets)
    split_release(source)
    selected = targets["skills_root"] / "hs-knowledge-review/artifacts/result.yaml"
    injected = False
    if fail:
        real_write = backend._write_atomic

        def interrupted(path, data, *args):
            nonlocal injected
            real_write(path, data, *args)
            if path == selected and not injected:
                injected = True
                assert not (targets["skills_root"] / "hs-knowledge-lint").exists()
                raise OSError("Synthetic stop after retiring the old lint Skill")

        monkeypatch.setattr(backend, "_write_atomic", interrupted)
    code, report = invoke(backend, capsys, source, targets)
    if fail:
        assert injected and (code, report["status"], report["rolled_back"]) == (3, "failed", True)
        assert all_target_bytes(targets) == before
        return
    assert (code, report["status"]) == (0, "deployed")
    assert len(report["packages"]["skills"]) == 13
    assert selected.read_bytes() == original
    assert not (targets["skills_root"] / "hs-knowledge-lint").exists()
    assert (targets["workflows_root"] / "hs-knowledge-lint/workflow.yaml").is_file()
    for action, (node_id, exits) in PATROL.items():
        package = targets["skills_root"] / ("hs-knowledge-patrol-" + action)
        contract = yaml.safe_load((package / "artifacts/result.yaml").read_bytes())
        assert contract["applies_to"]["node_ids"] == [node_id]
        assert contract["required_on"]["exit_ids"] == exits
        assert (package / "artifacts/templates/result.md").read_bytes() == (package / "references/results/templates/result.md").read_bytes()
    for name, data in business.items():
        assert (knowledge / name).read_bytes() == data
    repeated = cli(source, targets)
    assert repeated[0] == 0
    assert repeated[1]["write_count"] == repeated[1]["delete_count"] == repeated[1]["remove_directory_count"] == 0


def test_unreceipted_old_lint_skill_is_retired_without_removing_lint_workflow(source, targets):
    combined_release(source)
    split_release(source)
    put(targets["skills_root"], "hs-knowledge-lint/SKILL.md", "Old deployed instruction\n")
    unrelated = put(targets["skills_root"], "hs-other-tool/SKILL.md", "Unrelated user capability\n")
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert not (targets["skills_root"] / "hs-knowledge-lint").exists()
    assert (targets["workflows_root"] / "hs-knowledge-lint/workflow.yaml").is_file()
    assert unrelated.read_text() == "Unrelated user capability\n"


def test_concurrent_edit_to_retiring_lint_skill_is_preserved(
    backend, monkeypatch, capsys, source, targets,
):
    combined_release(source)
    assert cli(source, targets)[0] == 0
    selected = targets["skills_root"] / "hs-knowledge-lint/SKILL.md"
    original = selected.read_bytes()
    before = all_target_bytes(targets)
    split_release(source)
    real_remove = backend._remove_file
    injected = False

    def raced(path, expected_before):
        nonlocal injected
        if Path(path) == selected and not injected:
            injected = True
            selected.write_bytes(b"concurrent owner correction\n")
        return real_remove(path, expected_before)

    monkeypatch.setattr(backend, "_remove_file", raced)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed") and injected
    assert selected.read_bytes() == b"concurrent owner correction\n"
    before["skills_root"]["hs-knowledge-lint/SKILL.md"] = selected.read_bytes()
    assert all_target_bytes(targets) == before
    assert str(selected) in report["rollback_conflicts"]
    assert original in tree(Path(report["backup_directory"])).values()
