"""Read saved execution facts without approving or advancing an operation."""

import json

from support import fixed_bytes, identifier, safe

STAGES = (
    ("scan", ".build/operations/{op}/source-inventory.json"),
    ("materials", ".build/operations/{op}/material.json"),
    ("record_prepared", ".build/operations/{op}/ingest-record.yaml"),
    ("record_formal", "logs/ingest/{op}.yaml"),
    ("transaction", "logs/operations/{op}/journal.json"),
    ("apply", "logs/operations/{op}/apply-result.json"),
    ("submission_handoff", "logs/operations/{op}/publish-handoff.json"),
)


def status(context):
    target = context.request.get("target_operation_id")
    operations = {identifier(target)} if target else set()
    if not target:
        for directory in (".build/operations", "logs/operations"):
            root = safe(context.root, directory)
            if root.exists():
                operations.update(identifier(p.name) for p in root.iterdir() if p.is_dir())
    result = []
    for op in sorted(operations):
        facts, gaps = [], []
        for stage, pattern in STAGES:
            ref = pattern.format(op=op)
            if not safe(context.root, ref).is_file():
                continue
            try:
                value = json.loads(fixed_bytes(context.root, ref, [".build/operations", "logs/operations", "logs/ingest"]))
                context.modules["records"].verify(value)
                facts.append({"stage": stage, "ref": ref, "digest": value["digest"],
                              "status": value.get("status"), "phase": value.get("phase"),
                              "progress": value.get("progress"), "batch_kind": value.get("batch_kind")})
            except (OSError, ValueError, context.modules["validation"].ContractError) as exc:
                gaps.append({"stage": stage, "ref": ref, "reason": str(exc)})
        result.append({"operation_id": op, "facts": facts, "gaps": gaps,
                       "git_submission": "not_verified", "ci": "not_verified", "merge": "not_verified"})
    return {"operations": result, "knowledge_root": str(context.root)}, "status"
