"""Freeze the complete proposed official write set before any review."""

import base64
import re
from pathlib import PurePosixPath
from urllib.parse import quote

import yaml

from support import NodeError, digest, safe, sha, write_bytes


def execute(context):
    request = context.request
    plan = context.call(
        "hs-knowledge-change-plan",
        {"operation_id": context.operation, "plan_ref": request["plan_ref"]},
        "verify",
    )["data"]["plan"]
    if not plan["writes"]:
        return {
            "plan_ref": request["plan_ref"],
            "dispositions": plan["decisions"],
            "review_requirements": plan.get("review_requirements", {}),
            **{key: plan[key] for key in ("v3_required", "semantic_plan_ref", "semantic_plan_digest", "scan_ref", "material_ref", "target_queries") if key in plan},
        }, "deferred"
    writes = list(plan["writes"])
    navigation = {}
    referenced_snapshots = set()
    for write in writes:
        data = base64.b64decode(write["bytes_b64"], validate=True)
        if sha(data) != write["final_digest"]:
            raise NodeError(
                "FINAL_BYTES_CHANGED", "Planned Card bytes do not match digest"
            )
        card = context.modules["knowledge"].parse_card(
            data, write["path"], context.rules
        )
        metadata = card["metadata"]
        referenced_snapshots.update(
            source["snapshot_id"] for source in metadata["sources"]
        )
        index_ref = str(PurePosixPath(write["path"]).parent / "index.md")
        if index_ref not in navigation:
            path = safe(context.root, index_ref)
            navigation[index_ref] = (
                path.read_text(encoding="utf-8") if path.exists() else "# Knowledge\n"
            )
        marker = "<!-- card:" + sha(metadata["id"].encode()) + " -->"
        lines = navigation[index_ref].splitlines()
        matches = [i for i, line in enumerate(lines) if marker in line]
        if len(matches) > 1:
            raise NodeError(
                "NAVIGATION_CONFLICT", "Duplicate navigation markers", index_ref
            )
        title = re.sub(
            r"([\\`*_{}\[\]<>])", r"\\\1", metadata["title"].replace("\n", " ")
        )
        link = quote(PurePosixPath(write["path"]).name, safe="")
        entry = "- [" + title + "](" + link + ") " + marker
        if metadata["lifecycle"] == "deprecated":
            entry += " (deprecated)"
        if matches:
            lines[matches[0]] = entry
        else:
            lines += ["", entry]
        navigation[index_ref] = "\n".join(lines) + "\n"
    extra = {
        **{k: v.encode() for k, v in navigation.items()},
        "governance/sources.lock.yaml": yaml.safe_dump(
            plan["source_lock"], allow_unicode=True, sort_keys=False
        ).encode(),
    }
    for ref, data in extra.items():
        writes.append(
            {
                "path": ref,
                "expected_old_digest": plan["baseline"][ref],
                "final_digest": sha(data),
                "bytes_b64": base64.b64encode(data).decode(),
            }
        )
    baseline = {w["path"]: w["expected_old_digest"] for w in writes}
    for ref, expected in baseline.items():
        path = safe(context.root, ref)
        if (sha(path.read_bytes()) if path.exists() else None) != expected:
            raise NodeError("BASELINE_CHANGED", "Final-view baseline changed", ref)
    sources = sorted(
        (
            snapshot
            for snapshot in plan["source_lock"]["snapshots"]
            if snapshot["snapshot_id"] in referenced_snapshots
        ),
        key=lambda s: s["snapshot_id"],
    )
    view = context.seal(
        {
            "writes": sorted(writes, key=lambda w: w["path"]),
            "deletes": plan["deletes"],
            "review_mode": plan["review_mode"],
            "plan_ref": request["plan_ref"],
            "plan_digest": plan["digest"],
            "source_refs": sources,
            "source_set_digest": digest(sources),
            "bundle_ref": plan["bundle_ref"],
            "context_ref": plan.get("context_ref"),
            "baseline_digest": digest({"files": baseline}),
            "dispositions": plan["decisions"],
            "review_requirements": plan.get("review_requirements", {}),
            **{key: plan[key] for key in ("v3_required", "semantic_plan_ref", "semantic_plan_digest", "scan_ref", "material_ref", "target_queries") if key in plan},
        },
        "final_view",
    )
    for write in writes:
        write_bytes(
            context.root,
            context.base + "/final-view/" + write["path"],
            base64.b64decode(write["bytes_b64"], validate=True),
        )
    ref = context.save(context.base + "/final-view.json", view)
    return {
        "view_ref": ref,
        "view_digest": view["digest"],
        "review_mode": view["review_mode"],
    }, "ready"
