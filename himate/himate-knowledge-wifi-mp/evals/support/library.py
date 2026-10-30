"""Synthetic code-backed card library used by contract checks."""
import hashlib
import json
from pathlib import Path
import yaml
from support import contracts as _helper
checks = _helper.module("checks")
records = _helper.module("records")
resources = _helper.module("source_resources")
validation = _helper.module("validation")

def library(tmp_path, *, lifecycle="stable", review_mode="manual_document", kind="code"):
    """Synthetic rules are explicitly loaded from the development checkout."""
    root = tmp_path / "knowledge-root"
    (root / "governance").mkdir(parents=True)
    (root / "knowledge").mkdir()
    raw = b"int ready(void) { return 1; }\n"
    source = {"evidence_ref": "entry", "source_id": "source", "snapshot_id": "v1",
              "locator": {"kind": "lines", "start": 1, "end": 1}}
    lock = {"schema_version": "2.0", "resources": [
        {"source_id": "source", "kind": kind, "path": "src/ready.c"}],
        "snapshots": [{"source_id": "source", "snapshot_id": "v1",
                       "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                       "recovery": {"method": "evidence_object", "path": "logs/evidence/old.bin"}}]}
    (root / "governance/sources.lock.yaml").write_text(yaml.safe_dump(lock), encoding="utf-8")
    metadata = {"schema_version": "2.0", "id": "ready-card", "profile": "flow", "title": "Ready",
                "summary": "Documented ready flow", "lifecycle": lifecycle, "review_mode": review_mode,
                "owner": "fixture", "scope": {"applicability": "unknown", "contexts": []}, "aliases": [],
                "sources": [source], "claims": [{"id": "ready-claim", "text_ref": "#ready-claim",
                    "evidence_kind": "design", "source_refs": ["entry"], "context_ids": [],
                    "usage": "guidance", "verification_requirements": []}], "relations": []}
    body = "# Ready\n\n<a id=\"ready-claim\"></a>\nDocumented ready flow.\n"
    for heading in ("起终点", "步骤", "调用与消息", "异常", "条件", "证据"):
        body += "\n## " + heading + "\n\nDocumented scope.\n"
    card_bytes = ("---\n" + yaml.safe_dump(metadata) + "---\n" + body).encode("utf-8")
    (root / "knowledge/ready.md").write_bytes(card_bytes)
    (root / "knowledge/index.md").write_text("# Knowledge\n\n[Ready](ready.md)\n", encoding="utf-8")
    governance = Path(__file__).parents[2] / "governance"
    rules = {"knowledge_root": root, "rules_digest": "0" * 64,
             "profiles": yaml.safe_load((governance / "schemas/profiles.yaml").read_bytes()),
             "registries": yaml.safe_load((governance / "schemas/registries.yaml").read_bytes()),
             "schemas": {key: json.loads((governance / "schemas" / (name + ".schema.json")).read_bytes())
                         for key, name in (("card", "frontmatter"), ("sources", "sources"),
                                           ("workspace", "workspace"), ("record", "records"))}}
    return root, raw, source, lock, rules
