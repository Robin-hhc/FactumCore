"""Check design baselines, SDD references and task dependencies without touching business files."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDD = ROOT / "docs-llm-wiki/sdd/knowledge-v1"


def validate():
    trace = json.loads((SDD / "traceability.json").read_text(encoding="utf-8"))
    baseline = json.loads((SDD / "baseline.json").read_text(encoding="utf-8"))
    for source in baseline["sources"]:
        content = (ROOT / source["path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != source["sha256"]:
            raise ValueError(
                "Approved design changed; record its impact and refresh SDD explicitly"
            )
    requirements = {r["id"] for r in trace["requirements"]}
    modules = {m["id"] for m in trace["modules"]}
    acceptance = {a["id"] for a in trace["acceptance"]}
    tasks = {t["id"]: t for t in trace["tasks"]}
    assert len(requirements) == 18 and len(modules) == 9 and len(acceptance) == 34
    assert len(tasks) == 28 and len(trace["files"]) == 149
    assert len({f["path"] for f in trace["files"]}) == 149
    assert sum(f["kind"] == "P" for f in trace["files"]) == 3
    edges = set()
    for task in tasks.values():
        assert (SDD / task["ticket_path"]).is_file()
        assert set(task["requirements"]) <= requirements
        assert set(task["acceptance_ids"]) <= acceptance
        assert set(task["modules"]) <= modules
        assert set(task["blocked_by"]) <= set(tasks)
        edges.update((dependency, task["id"]) for dependency in task["blocked_by"])
        for ref in task.get("record_refs", []):
            assert (SDD / ref).is_file(), ref
    assert edges == {tuple(pair) for pair in trace["dag_edges"]}
    resolved = set()
    while len(resolved) < len(tasks):
        ready = {
            tid
            for tid, t in tasks.items()
            if tid not in resolved and set(t["blocked_by"]) <= resolved
        }
        if not ready:
            raise ValueError("Task dependency cycle")
        resolved.update(ready)
    for file in trace["files"]:
        assert file["primary_module"] in modules
        assert set(file["requirement_ids"]) <= requirements
        assert set(file["acceptance_ids"]) <= acceptance
        assert set(file["task_ids"]) <= set(tasks)
        assert file["kind"] == "P" or file["task_ids"]
    for item in trace["acceptance"]:
        assert item["task_ids"] and set(item["task_ids"]) <= set(tasks)
    for module in modules:
        for document in ("spec.md", "design.md", "tasks.md"):
            assert (SDD / "modules" / module / document).is_file()
    return {
        "status": "ok",
        "requirements": 18,
        "modules": 9,
        "tasks": 28,
        "files": 149,
        "acceptance": 34,
        "dag_edges": len(edges),
        "future_paths": 3,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=True))
