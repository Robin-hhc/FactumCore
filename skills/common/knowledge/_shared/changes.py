"""Explicit document plans and exact final views. No semantic synthesis or Git actions."""

import difflib
import json
import os
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import yaml

from . import contracts, receipts, sources

DECISIONS = {"create", "update", "merge", "split", "deprecate", "defer", "no_change"}
PROFILE_PATHS = {
    "entity": "concepts/entities",
    "flow": "concepts/flows",
    "protocol": "concepts/protocols",
    "rule": "rules",
    "command": "commands",
    "runbook": "runbooks",
    "glossary": "glossaries",
}


class ChangeError(ValueError):
    def __init__(self, code, message, path=""):
        self.code, self.message, self.path = code, message, str(path)
        super().__init__(f"{code}: {message}")


def fail(code, message, path=""):
    raise ChangeError(code, message, path)


def safe_path(root, relative):
    """Portable paths, including Windows aliases, checked on every use."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        fail("UNSAFE_PATH", "Expected a portable relative path", relative)
    parts = PurePosixPath(relative).parts
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
    if (
        PurePosixPath(relative).is_absolute()
        or not parts
        or relative != "/".join(parts)
        or any(
            part in {".", ".."}
            or part.endswith((".", " "))
            or ":" in part
            or re.search(r'[<>"|?*\x00-\x1f]', part)
            or part.split(".")[0].lower() in reserved
            for part in parts
        )
    ):
        fail("UNSAFE_PATH", "Unsafe or aliased relative path", relative)
    root = Path(root).resolve(strict=True)
    path = root.joinpath(*parts)
    # Reject links entirely for write artifacts, even when presently inside K.
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.is_symlink() or parent.is_junction():
            fail("UNSAFE_PATH", "Linked operation/target path is not supported", relative)
    if not path.resolve().is_relative_to(root):
        fail("UNSAFE_PATH", "Path escapes knowledge root", relative)
    return path


def atomic_write(root, relative, data):
    path = safe_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path = safe_path(root, relative)
    temporary = path.with_name(".write-" + uuid.uuid4().hex)
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if safe_path(root, relative) != path:
            fail("INPUT_CHANGED", "Write path changed", relative)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def json_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def read_json(root, relative):
    return contracts.load_document_bytes(safe_path(root, relative).read_bytes(), relative)


def file_digest(root, relative):
    path = safe_path(root, relative)
    return receipts.digest_file(path) if path.exists() else None


def operation_dir(operation_id):
    if not isinstance(operation_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", operation_id
    ):
        fail("UNSAFE_PATH", "Operation ID must be a simple identifier")
    return f".build/{operation_id}"


def fingerprints(root):
    contracts.load_bundle(root)
    return {
        "contract_digest": receipts.digest_file(safe_path(root, "governance/framework.lock.yaml")),
        "tool_digest": receipts.digest_json(
            {p.name: receipts.digest_file(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
        ),
    }


def check_baseline(root, baseline):
    for path, expected in baseline.items():
        if file_digest(root, path) != expected:
            fail("BASELINE_CHANGED", "Relevant file changed after planning", path)


def source_lock(root):
    path = safe_path(root, "governance/sources.lock.yaml")
    value = (
        contracts.load_document_bytes(path.read_bytes())
        if path.exists()
        else {
            "schema_version": "1.0",
            "resources": [],
            "snapshots": [],
        }
    )
    errors = contracts.validate_document("sources", value, root)
    if errors:
        fail("INVALID_SOURCE_LOCK", str(errors))
    for items, key in [(value["resources"], "source_id"), (value["snapshots"], "snapshot_id")]:
        if len({x[key] for x in items}) != len(items):
            fail("DUPLICATE_SOURCE_ID", "Source lock identity is not unique")
    return value


def merged_sources(root, capture):
    value = source_lock(root)
    for collection, key in [("resources", "source_id"), ("snapshots", "snapshot_id")]:
        existing = {item[key]: item for item in value[collection]}
        for item in capture[collection]:
            if item[key] in existing:
                previous = existing[item[key]]
                # Recovery locations/acquisition time may differ for identical original bytes.
                compare = (
                    "source_id",
                    "object_digest",
                    "bytes",
                    "mime",
                    "encoding",
                    "declared_version",
                )
                raw_relocation = (
                    collection == "resources"
                    and item["kind"] == "raw_document"
                    and all(
                        item[k] == previous[k]
                        for k in ("source_id", "kind", "authority_domain", "resolver")
                    )
                )
                if (collection == "resources" and item != previous and not raw_relocation) or (
                    collection == "snapshots" and any(item[k] != previous[k] for k in compare)
                ):
                    fail(
                        "SOURCE_ID_CONFLICT",
                        "Existing source identity has different content",
                        item[key],
                    )
                if raw_relocation:
                    # The logical source persists; each immutable snapshot keeps its own locator.
                    previous["resource_id"] = item["resource_id"]
            else:
                value[collection].append(item)
                existing[item[key]] = item
    return value


def create_plan(
    knowledge_root,
    *,
    operation_id,
    bundle_ref,
    manifest_digest,
    decision,
    rationale,
    target_path=None,
    candidate=None,
    related_card_ids=None,
):
    root = Path(knowledge_root).resolve(strict=True)
    directory = operation_dir(operation_id)
    if decision not in DECISIONS or not isinstance(rationale, str) or not rationale.strip():
        fail("INVALID_PLAN", "Explicit decision and rationale are required")
    capture = sources.load_capture(root, bundle_ref, manifest_digest)
    related_card_ids = related_card_ids or []
    request = {
        "schema_version": "1.0",
        "operation_id": operation_id,
        "decision": decision,
        "rationale": rationale,
        "bundle_ref": bundle_ref,
        "manifest_digest": manifest_digest,
        "target_path": target_path,
        "candidate_digest": receipts.digest_bytes(candidate) if candidate else None,
        "related_card_ids": related_card_ids,
    }
    plan_path = f"{directory}/plan.json"
    if safe_path(root, plan_path).exists():
        prior = read_json(root, plan_path)
        if prior["request"] != request:
            fail("OPERATION_CONFLICT", "An operation cannot be repurposed; use a new ID")
        return prior
    baseline = {}
    if decision in {"create", "update"}:
        if not candidate:
            fail("CANDIDATE_REQUIRED", "Agent must supply explicit Card Markdown")
        from .cards import parse_card

        lock = merged_sources(root, capture)
        parsed = parse_card(candidate, root, source_snapshots=lock["snapshots"])
        metadata = parsed["metadata"]
        if (
            not metadata["sources"]
            or any(not claim["source_ids"] for claim in metadata["claims"])
            or not set(metadata["sources"]) & {s["snapshot_id"] for s in capture["snapshots"]}
        ):
            fail(
                "EVIDENCE_REQUIRED",
                "Every claim needs bound evidence; choose defer when evidence is missing",
            )
        if metadata["review_mode"] != "manual_document":
            fail("WRONG_REVIEW_MODE", "This pipeline supports manual_document only")
        prefix = f"knowledge/{PROFILE_PATHS[metadata['profile']]}/"
        if (
            not isinstance(target_path, str)
            or not target_path.startswith(prefix)
            or not target_path.endswith(".md")
            or Path(target_path).name.lower() in {"index.md", "agents.md"}
        ):
            fail(
                "UNSAFE_PATH",
                "Card path must match its profile and cannot be a control file",
                target_path,
            )
        safe_path(root, target_path)
        existing = file_digest(root, target_path)
        if decision == "create" and existing is not None:
            fail("TARGET_EXISTS", "Create cannot overwrite an existing card", target_path)
        if decision == "update":
            if existing is None:
                fail("TARGET_MISSING", "Update requires an existing card", target_path)
            old = parse_card(
                safe_path(root, target_path).read_bytes(), root, source_snapshots=lock["snapshots"]
            )
            if old["metadata"]["id"] != metadata["id"]:
                fail("CARD_ID_CHANGED", "Update must retain the logical card identity")
        for path in [
            target_path,
            str(PurePosixPath(target_path).parent / "index.md"),
            "governance/sources.lock.yaml",
        ]:
            baseline[path] = file_digest(root, path)
    result = {
        "schema_version": "1.0",
        "operation_id": operation_id,
        "decision": decision,
        "rationale": rationale,
        "related_card_ids": related_card_ids,
        "request": request,
        "baseline": baseline,
        "fingerprints": fingerprints(root),
        "phase": "planned",
    }
    staging = ".build/.plan-" + uuid.uuid4().hex
    try:
        if candidate and decision in {"create", "update"}:
            atomic_write(root, f"{staging}/candidates/card.md", candidate)
        atomic_write(root, f"{staging}/plan.json", json_bytes(result))
        try:
            os.rename(safe_path(root, staging), safe_path(root, directory))
        except OSError:
            if not safe_path(root, plan_path).exists():
                raise
            prior = read_json(root, plan_path)
            if prior["request"] != request:
                fail("OPERATION_CONFLICT", "Concurrent operation has a different request")
            return prior
        return result
    finally:
        staged = safe_path(root, staging)
        if staged.exists():
            # Only this newly generated UUID directory; never a published operation.
            shutil.rmtree(staged)


def load_plan(root, operation_id):
    directory = operation_dir(operation_id)
    plan = read_json(root, f"{directory}/plan.json")
    if plan["operation_id"] != operation_id or plan["request"]["operation_id"] != operation_id:
        fail("OPERATION_CONFLICT", "Operation identity mismatch")
    if plan["decision"] != plan["request"]["decision"]:
        fail("PLAN_CHANGED", "Decision differs from the explicit request")
    return plan


def materialize(knowledge_root, operation_id):
    root = Path(knowledge_root).resolve(strict=True)
    directory = operation_dir(operation_id)
    plan = load_plan(root, operation_id)
    if plan["decision"] not in {"create", "update"}:
        phase = {"defer": "deferred", "no_change": "no_change"}.get(
            plan["decision"], "planned_only"
        )
        return {
            "operation_id": operation_id,
            "phase": phase,
            "decision": plan["decision"],
            "rationale": plan["rationale"],
            "apply_supported": False,
        }
    check_baseline(root, plan["baseline"])
    if plan["fingerprints"] != fingerprints(root):
        fail("PLAN_STALE", "Tool or contract changed; create a new plan")
    request = plan["request"]
    capture = sources.load_capture(root, request["bundle_ref"], request["manifest_digest"])
    candidate = safe_path(root, f"{directory}/candidates/card.md").read_bytes()
    if receipts.digest_bytes(candidate) != request["candidate_digest"]:
        fail("CANDIDATE_CHANGED", "Candidate differs from the explicit request")
    from .cards import parse_card

    lock = merged_sources(root, capture)
    parsed = parse_card(candidate, root, source_snapshots=lock["snapshots"])
    metadata = parsed["metadata"]
    metadata["lifecycle"] = "stable"
    stable = (
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        + "---\n"
        + parsed["body"]
    ).encode("utf-8")
    target = request["target_path"]
    index = str(PurePosixPath(target).parent / "index.md")
    index_bytes = (
        safe_path(root, index).read_bytes() if safe_path(root, index).exists() else b"# Knowledge\n"
    )
    marker = f"<!-- card:{receipts.digest_bytes(metadata['id'].encode())} -->"
    title = re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", metadata["title"].replace("\n", " "))
    entry = f"- [{title}]({quote(PurePosixPath(target).name, safe='')}) {marker}"
    lines = index_bytes.decode("utf-8").splitlines()
    matches = [i for i, line in enumerate(lines) if marker in line]
    if len(matches) > 1:
        fail("NAVIGATION_CONFLICT", "Navigation has duplicate card markers")
    if matches:
        lines[matches[0]] = entry
        index_bytes = ("\n".join(lines) + "\n").encode()
    else:
        index_bytes = index_bytes.rstrip() + ("\n\n" + entry + "\n").encode()
    outputs = {
        target: stable,
        index: index_bytes,
        "governance/sources.lock.yaml": yaml.safe_dump(
            lock, allow_unicode=True, sort_keys=False
        ).encode(),
    }
    digests = {path: receipts.digest_bytes(data) for path, data in outputs.items()}
    result = {
        "schema_version": "1.0",
        "operation_id": operation_id,
        "phase": "awaiting_confirmation",
        "review_mode": "manual_document",
        "decision": plan["decision"],
        "target_file_digests": digests,
        "baseline": plan["baseline"],
        "baseline_digest": receipts.digest_json(plan["baseline"]),
        "final_view_digest": receipts.digest_json(digests),
        "source_set_digest": receipts.digest_json(lock),
        "source_snapshot_refs": metadata["sources"],
        "scope_digest": receipts.digest_json(metadata["scope"]),
        "card_ids": [metadata["id"]],
        "claim_ids": [c["id"] for c in metadata["claims"]],
        "fingerprints": fingerprints(root),
        "plan_digest": receipts.digest_json(plan),
    }
    changeset_path = f"{directory}/changeset.json"
    if safe_path(root, changeset_path).exists():
        if read_json(root, changeset_path) != result:
            fail("OPERATION_CONFLICT", "Existing materialized operation differs")
        checked_view(root, operation_id)
        return result
    review = [
        "# 人工文档确认包",
        "",
        "合成或真实属性由来源决定；本工具不认证来源语义。",
        f"Operation: {operation_id}",
        f"Decision: {plan['decision']}",
        f"Reason: {plan['rationale']}",
        f"Final view: {result['final_view_digest']}",
        "",
        "本分支不运行代码 lint。请逐项复核来源、范围、Claim 身份及以下确切最终内容。",
        "二进制附件仅保存原字节，未声明提取或理解；未知范围不扩展到任意芯片或代码当前事实。",
    ]
    for path, data in outputs.items():
        atomic_write(root, f"{directory}/final-view/{path}", data)
        old = (
            safe_path(root, path).read_bytes().decode("utf-8")
            if safe_path(root, path).exists()
            else ""
        )
        diff = "".join(
            difflib.unified_diff(
                old.splitlines(True),
                data.decode("utf-8").splitlines(True),
                fromfile=path + " (baseline)",
                tofile=path + " (final)",
            )
        )
        review += ["", f"## {path}", f"SHA256: {digests[path]}", "```diff", diff, "```"]
    atomic_write(root, f"{directory}/review-package.md", "\n".join(review).encode())
    atomic_write(root, changeset_path, json_bytes(result))
    return result


def checked_view(root, operation_id):
    directory = operation_dir(operation_id)
    value = read_json(root, f"{directory}/changeset.json")
    plan = load_plan(root, operation_id)
    if value["operation_id"] != operation_id or value["plan_digest"] != receipts.digest_json(plan):
        fail("REVIEW_STALE", "Plan/operation changed")
    if value["fingerprints"] != fingerprints(root):
        fail("REVIEW_STALE", "Tool or contract changed")
    if value["baseline_digest"] != receipts.digest_json(value["baseline"]):
        fail("REVIEW_STALE", "Baseline binding differs")
    if value["baseline"] != plan["baseline"]:
        fail("REVIEW_STALE", "Baseline differs from the plan")
    request = plan["request"]
    sources.load_capture(root, request["bundle_ref"], request["manifest_digest"])
    expected = {
        request["target_path"],
        str(PurePosixPath(request["target_path"]).parent / "index.md"),
        "governance/sources.lock.yaml",
    }
    if set(value["target_file_digests"]) != expected:
        fail("REVIEW_STALE", "Unexpected final target list")
    for path, digest in value["target_file_digests"].items():
        if file_digest(root, f"{directory}/final-view/{path}") != digest:
            fail("REVIEW_STALE", "Final view bytes changed", path)
    if value["final_view_digest"] != receipts.digest_json(value["target_file_digests"]):
        fail("REVIEW_STALE", "Final view binding differs")
    if set(value["baseline"]) != expected:
        fail("REVIEW_STALE", "Unexpected baseline target list")
    from .cards import parse_card

    lock = contracts.load_document_bytes(
        safe_path(root, f"{directory}/final-view/governance/sources.lock.yaml").read_bytes()
    )
    if (
        contracts.validate_document("sources", lock, root)
        or receipts.digest_json(lock) != value["source_set_digest"]
    ):
        fail("REVIEW_STALE", "Source-set binding differs")
    parsed = parse_card(
        safe_path(root, f"{directory}/final-view/{request['target_path']}").read_bytes(),
        root,
        source_snapshots=lock["snapshots"],
    )
    meta = parsed["metadata"]
    if (
        meta["lifecycle"] != "stable"
        or meta["review_mode"] != "manual_document"
        or not request["target_path"].startswith(f"knowledge/{PROFILE_PATHS[meta['profile']]}/")
        or receipts.digest_json(meta["scope"]) != value["scope_digest"]
        or meta["sources"] != value["source_snapshot_refs"]
        or [meta["id"]] != value["card_ids"]
        or [c["id"] for c in meta["claims"]] != value["claim_ids"]
    ):
        fail("REVIEW_STALE", "Card identity, lifecycle, source or scope binding differs")
    return value


def confirm_document(*args, **kwargs):
    from .confirmations import confirm_document as confirm

    return confirm(*args, **kwargs)


def validate_review(*args, **kwargs):
    from .confirmations import validate_review as validate

    return validate(*args, **kwargs)


def narrow_document(*args, **kwargs):
    from .confirmations import narrow_document as narrow

    return narrow(*args, **kwargs)
