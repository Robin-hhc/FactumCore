"""Deterministic, read-only checking shared by lint and a trusted CI runner."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

from . import knowledge, records, source_resources, validation as v

CHECKS = (
    ("view.inputs", "view"), ("format.cards", "format"),
    ("source.references", "source"), ("relation.graph", "relation"),
    ("records.coverage", "records"), ("index.build", "index"),
)
STATUSES = {"passed", "failed", "incomplete", "not_applicable"}


def _record_resolver(cards, rules, inputs, root, identity):
    """Fixed data-only current/archive/Git resolver; never a JSON callback."""
    current = {key: card for card in cards.values() for key in (card["metadata"]["id"], card["path"])}
    declared = inputs.get("historical_card_objects", {})
    if not isinstance(declared, dict):
        raise v.ContractError("RECORD_HISTORY_UNAVAILABLE", "historical_card_objects must map fingerprints to absolute files")
    objects, git_cache = {}, []
    history = {"loaded": False, "complete": False}
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_") or key == "GIT_TEST_ASSUME_DIFFERENT_OWNER"}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_PAGER="cat")
    workspace = None

    def git(arguments, repository=None):
        location = workspace if repository is None else repository
        command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "-c", "core.pager=cat", "-c", "log.showSignature=false", "-c", "protocol.allow=never", "-c", "safe.directory=" + location.as_posix(), "-C", str(location), *arguments]
        result = subprocess.run(command, capture_output=True, timeout=30, env=environment)
        if result.returncode:
            raise v.ContractError("RECORD_HISTORY_UNAVAILABLE", "Required exact Git history is unavailable")
        return result.stdout

    def parse(raw, path, expected=None):
        actual = v.sha256_bytes(raw)
        if expected is not None and actual != expected:
            raise v.ContractError("HISTORICAL_CARD_CHANGED", "Historical card body fingerprint differs", path)
        return knowledge.parse_card(raw, path, rules)

    def archive_objects(path):
        for expected, filename in declared.items():
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected) or not isinstance(filename, str) or not Path(filename).is_absolute():
                raise v.ContractError("RECORD_HISTORY_UNAVAILABLE", "Historical card inputs require a fixed SHA-256 and absolute path")
            if expected not in objects:
                file = Path(filename)
                for part in (file, *file.parents):
                    if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
                        raise v.ContractError("INVALID_HISTORICAL_PATH", "Linked historical card objects are forbidden")
                raw = _read(file)
                if _read(file) != raw:
                    raise v.ContractError("HISTORICAL_CARD_CHANGED", "Historical input changed while reading")
                objects[expected] = raw
            yield parse(objects[expected], path, expected)

    def git_objects():
        nonlocal workspace
        if not history["loaded"]:
            history["loaded"] = True
            try:
                try:
                    workspace = v.workspace_config_path(root).parent
                except v.ContractError as exc:
                    if exc.code != "WORKSPACE_CONFIG_UNAVAILABLE":
                        raise
                    workspace = Path(git(["rev-parse", "--show-toplevel"], root).decode("utf-8").strip()).resolve()
                    ancestors = [parent for parent in root.parents if parent == workspace or parent.is_relative_to(workspace)]
                    if not root.resolve().is_relative_to(workspace) or any(os.path.lexists(parent / "config.yml") for parent in ancestors):
                        raise v.ContractError("RECORD_HISTORY_UNAVAILABLE", "An existing workspace config is invalid; Git history cannot bypass it")
                prefix = root.relative_to(workspace).as_posix()
                top = Path(git(["rev-parse", "--show-toplevel"]).decode("utf-8").strip()).resolve()
                if top != workspace:
                    return
                revision = identity.get("commit", "HEAD")
                if revision != "HEAD" and not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
                    return
                commits = git(["log", "--format=%H", "--max-count=1001", revision, "--", prefix + "/knowledge"]).decode("ascii").splitlines()
                history["complete"] = len(commits) < 1001
                seen = set()
                for commit in commits[:1000]:
                    tree = git(["ls-tree", "-r", "-z", commit, "--", prefix + "/knowledge"])
                    for entry in tree.split(b"\x00"):
                        if not entry:
                            continue
                        header, name = entry.split(b"\t", 1)
                        mode, kind, object_id = header.split()
                        path = name.decode("utf-8")
                        if mode not in {b"100644", b"100755"} or kind != b"blob" or not path.endswith(".md") or PurePosixPath(path).name in {"index.md", "AGENTS.md", "README.md"} or object_id in seen:
                            continue
                        seen.add(object_id)
                        relative = path[len(prefix) + 1:]
                        v.safe_path(root, relative, ["knowledge"])
                        raw = git(["cat-file", "blob", object_id.decode("ascii")])
                        try:
                            git_cache.append(parse(raw, relative))
                        except v.ContractError:
                            history["complete"] = False
            except (OSError, subprocess.SubprocessError, UnicodeError, ValueError):
                history["complete"] = False
        yield from git_cache

    def resolve(reference, record):
        if "record_version_resolver" in inputs:
            raise v.ContractError("INVALID_RECORD_INPUT", "JSON callbacks are not supported; provide exact historical_card_objects")
        ref = reference if isinstance(reference, dict) else {"card_id": reference}
        target = ref.get("card_id") or ref.get("path")
        claim = ref.get("claim_id")
        accepted = [row for row in record.get("acceptance", {}).get("cards", []) if row.get("card_id") == target or row.get("path") == target]
        expected = ref.get("sha256") or (accepted[0]["sha256"] if accepted else None)
        if expected is not None and not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
            raise v.ContractError("INVALID_RECORD_REFERENCE", "A record card fingerprint must be SHA-256")
        card = current.get(target)
        path = ref.get("path") or (accepted[0]["path"] if accepted else card["path"] if card else "knowledge/.historical/card.md")
        v.safe_path(root, path, ["knowledge"])
        explicit_id = ref.get("card_id")
        if isinstance(explicit_id, str) and "/" in explicit_id:
            explicit_id = None
        logical_id = explicit_id or (accepted[0]["card_id"] if accepted else card["metadata"]["id"] if card else None)
        def matches(candidate, archive=False):
            if accepted and candidate["metadata"]["id"] != accepted[0]["card_id"]:
                return False
            # An archive object has body/hash authority, not path authority.
            # Never manufacture an existing path by assigning the requested path.
            identity_matches = candidate["metadata"]["id"] == logical_id if archive else (candidate["metadata"]["id"] == target or candidate["path"] == target)
            if identity_matches and expected is not None and candidate["sha256"] == expected and claim is not None and claim not in {item["id"] for item in candidate["metadata"]["claims"]}:
                raise v.ContractError("DANGLING_CLAIM_RECORD", "The exact pinned card body has no referenced Claim", str(claim))
            return identity_matches and (expected is None or candidate["sha256"] == expected) and (claim is None or claim in {item["id"] for item in candidate["metadata"]["claims"]})
        if card and matches(card):
            return card
        for candidate in archive_objects(path):
            if matches(candidate, archive=True):
                return candidate
        for candidate in git_objects():
            if matches(candidate):
                return candidate
        if expected is not None or not history["complete"]:
            raise v.ContractError("RECORD_HISTORY_UNAVAILABLE", "Required exact historical card/Claim body could not be recovered", str(target))
        raise v.ContractError("DANGLING_CLAIM_RECORD" if claim else "DANGLING_CARD_RECORD", "No such card/Claim exists in the complete candidate or available Git knowledge history", str(target))
    return resolve


def _read(path):
    # The validated Path is extended only for IO, never for trust decisions.
    import os
    absolute = str(path.absolute())
    if os.name == "nt" and not absolute.startswith("\\\\?\\"):
        absolute = "\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute
    return Path(absolute).read_bytes()


def prepare_view(root, candidate=None, *, mode="formal", identity=None):
    root = Path(root).resolve(strict=True)
    files = {}
    for prefix in ("knowledge", "logs/ingest"):
        folder = v.safe_path(root, prefix)
        if folder.exists():
            for path in folder.rglob("*"):
                ref = path.relative_to(root).as_posix()
                checked = v.safe_path(root, ref, [prefix])
                if checked.is_file():
                    files[ref] = _read(checked)
    lock = v.safe_path(root, "governance/sources.lock.yaml")
    if lock.exists():
        files["governance/sources.lock.yaml"] = _read(lock)
    view = {"mode": mode, "root": root, "files": files, "identity": identity or {"root": str(root)}}
    if candidate is not None:
        view["candidate"] = candidate
    return view


def _scope(scope):
    if scope is None or scope == "full":
        return {"kind": "full", "paths": []}
    if isinstance(scope, list):
        return {"kind": "local", "paths": scope}
    if not isinstance(scope, dict) or scope.get("kind") not in {"full", "local"}:
        raise v.ContractError("INVALID_SCOPE", "A full or explicit local check scope is required")
    if scope["kind"] == "local" and not scope.get("paths"):
        raise v.ContractError("INVALID_SCOPE", "Local scope must enumerate its objects")
    return {"kind": scope["kind"], "paths": list(scope.get("paths", []))}


def run(view, rules, inputs=None, scope=None):
    """Return a complete protocol report. No repair, confirmation or activation."""
    inputs = inputs or {}
    scope = _scope(scope)
    if isinstance(view, (str, Path)):
        view = prepare_view(view)
    root = Path(view.get("root", rules["knowledge_root"])).resolve(strict=True)
    report = {"report_version": "1.0", "object": dict(view.get("identity", {})),
              "rules_digest": rules["rules_digest"], "mode": view.get("mode", "formal"),
              "scope": scope, "checks": [], "findings": []}
    by_group = {}
    for check_id, group in CHECKS:
        row = {"check_id": check_id, "group": group, "status": "passed", "findings": []}
        report["checks"].append(row)
        by_group[group] = row

    def finding(group, code, reason, path="", line=None, *, incomplete=False, severity="error"):
        row = by_group[group]
        item = {"check_id": row["check_id"], "code": code, "severity": severity,
                "path": str(path), "line": line, "reason": str(reason)}
        row["findings"].append(item)
        report["findings"].append(item)
        if severity == "error":
            if incomplete and row["status"] != "failed":
                row["status"] = "incomplete"
            elif not incomplete:
                row["status"] = "failed"

    def caught(group, exc, path=""):
        code = getattr(exc, "code", "CHECK_RUNTIME_UNAVAILABLE")
        incomplete = isinstance(exc, OSError) or code.endswith("UNAVAILABLE")
        finding(group, code, str(exc), path or getattr(exc, "path", ""), incomplete=incomplete)

    files = dict(view.get("files", {}))
    baseline = dict(files)
    try:
        folded = set()
        for ref, raw in files.items():
            v.safe_path(root, ref, ["knowledge", "governance/sources.lock.yaml", "logs/ingest"])
            if ref.casefold() in folded or not isinstance(raw, bytes):
                raise v.ContractError("INVALID_VIEW", "Aliased paths or non-byte input", ref)
            folded.add(ref.casefold())
        candidate = view.get("candidate")
        if candidate is not None:
            records.verify(candidate)
            touched = set()
            for item in candidate.get("writes", []):
                ref = item["path"]
                v.safe_path(root, ref, ["knowledge", "governance/sources.lock.yaml"])
                if ref.casefold() in touched:
                    raise v.ContractError("DUPLICATE_WRITE", "Candidate paths overlap", ref)
                touched.add(ref.casefold())
                raw = base64.b64decode(item["bytes_b64"], validate=True)
                old = v.sha256_bytes(baseline[ref]) if ref in baseline else None
                if old != item["expected_old_digest"] or v.sha256_bytes(raw) != item["final_digest"]:
                    raise v.ContractError("BASELINE_CHANGED", "Candidate bytes or old baseline differ", ref)
                files[ref] = raw
            for item in candidate.get("deletes", []):
                ref = item["path"]
                v.safe_path(root, ref, ["knowledge"])
                if ref.casefold() in touched:
                    raise v.ContractError("CONFLICTING_WRITE", "Candidate writes and deletes overlap", ref)
                touched.add(ref.casefold())
                old = v.sha256_bytes(baseline[ref]) if ref in baseline else None
                if old != item["expected_old_digest"]:
                    raise v.ContractError("BASELINE_CHANGED", "Deleted object baseline differs", ref)
                files.pop(ref, None)
            if candidate.get("plan_ref"):
                plan_path = v.safe_path(root, candidate["plan_ref"], [".build", "logs"])
                plan = json.loads(_read(plan_path))
                records.verify(plan)
                if plan["digest"] != candidate.get("plan_digest") or plan["operation_id"] != candidate["operation_id"]:
                    raise v.ContractError("PLAN_CHANGED", "Candidate plan binding differs")
                actual_writes = {item["path"]: item for item in candidate.get("writes", [])}
                for planned in plan.get("writes", []):
                    actual = actual_writes.get(planned["path"])
                    if actual is None or any(actual.get(key) != planned.get(key) for key in ("bytes_b64", "final_digest", "expected_old_digest")):
                        raise v.ContractError("PLAN_CHANGED", "Candidate content differs from the fixed planned writes", planned["path"])
                if candidate.get("deletes", []) != plan.get("deletes", []):
                    raise v.ContractError("PLAN_CHANGED", "Candidate deletions differ from the fixed plan")
                planned_paths = {item["path"] for item in plan.get("writes", [])}
                if any(ref not in planned_paths and ref != "governance/sources.lock.yaml" and PurePosixPath(ref).name != "index.md" for ref in actual_writes):
                    raise v.ContractError("PLAN_CHANGED", "Unplanned candidate write")
            if candidate.get("baseline_digest"):
                expected = {item["path"]: item["expected_old_digest"] for item in candidate.get("writes", []) + candidate.get("deletes", [])}
                if v.digest_payload({"files": expected}) != candidate["baseline_digest"]:
                    raise v.ContractError("BASELINE_CHANGED", "Candidate baseline digest differs")
        if report["mode"] != "ci":
            journal_root = v.safe_path(root, "logs/operations")
            if journal_root.exists():
                for journal in journal_root.glob("*/journal.json"):
                    item = json.loads(_read(v.safe_path(root, journal.relative_to(root).as_posix())))
                    if item.get("status") not in {"committed", "rolled_back"}:
                        finding("view", "RECOVERY_REQUIRED", "An unfinished transaction requires recovery before checking", str(journal.relative_to(root)), incomplete=True)
    except (v.ContractError, OSError, ValueError, KeyError, TypeError) as exc:
        caught("view", exc)
    report["object"]["files_digest"] = v.digest_payload({ref: v.sha256_bytes(raw) for ref, raw in files.items() if isinstance(raw, bytes)})

    def selected(ref):
        return scope["kind"] == "full" or any(ref == prefix or ref.startswith(prefix.rstrip("/") + "/") for prefix in scope["paths"])
    cards, structures = {}, {}
    for ref, raw in sorted(files.items()):
        if not ref.startswith("knowledge/") or not ref.endswith(".md") or PurePosixPath(ref).name == "AGENTS.md":
            continue
        try:
            structures[ref] = v.markdown_structure(raw)
            if selected(ref):
                for line in structures[ref]["conflicts"]:
                    finding("format", "CONFLICT_MARKER", "Unresolved conflict marker", ref, line)
                for anchor in structures[ref]["duplicate_anchors"]:
                    finding("format", "DUPLICATE_ANCHOR", anchor["anchor"], ref, anchor["line"])
            if PurePosixPath(ref).name == "index.md":
                continue
            card = knowledge.parse_card(raw, ref, rules)
            identity = card["metadata"]["id"]
            if identity in cards:
                finding("relation", "DUPLICATE_CARD_ID", "Card ID must be domain-unique", ref)
            cards[identity] = card
        except (v.ContractError, UnicodeError, ValueError, KeyError) as exc:
            if selected(ref):
                caught("format", exc, ref)
    try:
        knowledge.validate_relations(cards)
    except v.ContractError as exc:
        caught("relation", exc)
    for ref, structure in structures.items():
        if not selected(ref):
            continue
        for link in structure["links"]:
            target = link["target"]
            if target is None:
                finding("relation", "UNRESOLVED_LINK", "Reference link definition is missing", ref, link["line"])
                continue
            split = urlsplit(target)
            if split.scheme in {"http", "https", "mailto", "tel"}:
                continue
            if split.scheme or target.startswith("/") or "\\" in target:
                finding("relation", "LINK_OUTSIDE_VIEW", "Link is outside the governed data view", ref, link["line"])
                continue
            import posixpath
            destination = posixpath.normpath(posixpath.join(posixpath.dirname(ref), unquote(split.path))) if split.path else ref
            if destination not in files:
                finding("relation", "BROKEN_LINK", "Target file is absent from the exact view", ref, link["line"])
            elif split.fragment and unquote(split.fragment) not in structures.get(destination, {}).get("anchors", set()):
                finding("relation", "BROKEN_FRAGMENT", "Target anchor is absent", ref, link["line"])
        if PurePosixPath(ref).name != "index.md":
            parent = str(PurePosixPath(ref).parent / "index.md")
            if parent not in files:
                finding("relation", "MISSING_PARENT_NAVIGATION", "Managed card requires a parent index.md", ref)
            elif not any(urlsplit(item.get("target") or "").path == PurePosixPath(ref).name for item in structures.get(parent, {}).get("links", [])):
                finding("relation", "NAVIGATION_OMISSION", "Parent navigation does not reference this card", parent)

    lock = None
    try:
        lock = v.load_yaml(files["governance/sources.lock.yaml"])
        v.validate_shape("sources", lock, rules)
        ids = [item["source_id"] for item in lock["resources"]]
        snapshots = [item["snapshot_id"] for item in lock["snapshots"]]
        if len(ids) != len(set(ids)) or len(snapshots) != len(set(snapshots)):
            raise v.ContractError("DUPLICATE_SOURCE", "Source identities must be unique")
        candidate = view.get("candidate")
        if candidate is not None:
            written_paths = {item["path"] for item in candidate.get("writes", [])}
            referenced = {source["snapshot_id"] for card in cards.values() if card["path"] in written_paths for source in card["metadata"]["sources"]}
            relevant = sorted((item for item in lock["snapshots"] if item["snapshot_id"] in referenced), key=lambda item: item["snapshot_id"])
            if relevant != candidate.get("source_refs") or v.sha256_bytes(v.canonical_bytes(relevant)) != candidate.get("source_set_digest"):
                raise v.ContractError("SOURCE_SET_CHANGED", "Candidate source-set binding differs")
    except (v.ContractError, KeyError, ValueError) as exc:
        lock = None
        if cards or "governance/sources.lock.yaml" in files:
            caught("source", exc)
        else:
            by_group["source"]["status"] = "not_applicable"
            by_group["source"]["reason"] = "Empty library has no source lock or source references"

    def resolver(snapshot):
        objects = inputs.get("source_objects", {})
        if snapshot["snapshot_id"] in objects:
            value = objects[snapshot["snapshot_id"]]
            if isinstance(value, (str, Path)):
                return _read(Path(value))
            return value
        if report["mode"] == "ci":
            raise OSError("CI requires explicitly supplied exact source inputs")
        return source_resources.recover_snapshot(root, snapshot)

    code_cards = []
    for card in cards.values():
        ref = card["path"]
        if not selected(ref):
            continue
        metadata = card["metadata"]
        if metadata["review_mode"] == "code_gate" and metadata["lifecycle"] != "deprecated":
            current_claims = [claim for claim in metadata["claims"] if claim["usage"] == "current"]
            if current_claims:
                evidence = {ref for claim in current_claims for ref in claim["source_refs"]}
                contexts = {ref for claim in current_claims for ref in claim["context_ids"]}
                projected_metadata = {**metadata, "claims": current_claims,
                    "sources": [source for source in metadata["sources"] if source["evidence_ref"] in evidence],
                    "scope": {**metadata["scope"], "contexts": [context for context in metadata["scope"]["contexts"] if context["context_id"] in contexts]}}
                code_cards.append({**card, "metadata": projected_metadata,
                    "claims": [claim for claim in card["claims"] if claim["id"] in {item["id"] for item in current_claims}]})
        if lock is not None:
            for source in card["metadata"]["sources"]:
                try:
                    checked_source = source_resources.validate_reference(source, lock, resolver, allowed_kinds=set(rules["registries"].get("locator_kinds", [])) or None)
                    by_group["source"].setdefault("inputs", []).append(checked_source)
                except (v.ContractError, OSError, ValueError, KeyError) as exc:
                    caught("source", exc, ref)
    report["code_check_status"] = "not_applicable" if not code_cards else "passed"
    if code_cards and not inputs.get("code_checkout"):
        finding("source", "CODE_INPUT_UNAVAILABLE", "Code cards require the explicitly supplied fixed checkout and real mapping", incomplete=True)
        report["code_check_status"] = "incomplete"
    elif code_cards and lock is not None:
        for card in code_cards:
            try:
                checked_code = source_resources.validate_code_references(card, lock, inputs["code_checkout"], rules)
                by_group["source"].setdefault("code_inputs", []).extend(checked_code)
            except (v.ContractError, OSError, ValueError, KeyError, TypeError) as exc:
                caught("source", exc, card["path"])
                report["code_check_status"] = "incomplete" if getattr(exc, "code", "").endswith("UNAVAILABLE") else "failed"

    record_resolver = _record_resolver(cards, rules, inputs, root, report["object"])
    formal_records, record_paths = [], {}
    for ref, raw in files.items():
        if ref.startswith("logs/ingest/") and selected(ref):
            try:
                record = v.load_yaml(raw)
                records.validate_ingest_record(record, rules={**rules, "source_lock": lock}, version_resolver=record_resolver, require_final=True)
                formal_records.append(record)
                record_paths[record["digest"]] = ref
            except (v.ContractError, ValueError, KeyError, TypeError) as exc:
                caught("records", exc, ref)
    if formal_records:
        reconstructed = records.rebuild_restrictions(formal_records, rules=rules, cards=cards)
        by_group["records"]["processing_state"] = reconstructed
        for gap in reconstructed["gaps"]:
            finding("records", gap["code"], gap["reason"], record_paths.get(gap.get("record_digest"), ""), incomplete=gap["code"].endswith("UNAVAILABLE"))
    prerequisites = ("view", "format", "source", "relation", "records")
    if any(by_group[group]["status"] not in {"passed", "not_applicable"} for group in prerequisites):
        by_group["index"]["status"] = "incomplete"
        by_group["index"]["reason"] = "Index check was not run because prerequisite checks did not pass"
    else:
        try:
            from . import indexing
            with tempfile.TemporaryDirectory(prefix="knowledge-lint-", dir=inputs.get("temporary_parent")) as temporary:
                by_group["index"]["summary"] = indexing.check(list(cards.values()), rules, temporary)
        except (v.ContractError, OSError, ValueError, ImportError) as exc:
            caught("index", exc)
    states = {row["status"] for row in report["checks"]}
    report["status"] = "failed" if "failed" in states else "incomplete" if "incomplete" in states else "passed"
    report["complete"] = "incomplete" not in states
    report["exit_code"] = {"passed": 0, "failed": 1, "incomplete": 2}[report["status"]]
    report["phase"] = report["status"]
    report["digest"] = v.digest_payload(report)
    return report


def validate_report(report, expected_object=None, expected_rules=None, required_scope=None):
    if not isinstance(report, dict) or report.get("report_version") != "1.0" or not report.get("checks"):
        raise v.ContractError("INVALID_CHECK_REPORT", "A nonempty fixed check report is required")
    if report.get("digest") != v.digest_payload(report):
        raise v.ContractError("INVALID_CHECK_REPORT", "Report fingerprint differs")
    ids = [row.get("check_id") for row in report["checks"]]
    if set(ids) != {item[0] for item in CHECKS} or len(ids) != len(set(ids)) or any(row.get("status") not in STATUSES for row in report["checks"]):
        raise v.ContractError("INVALID_CHECK_REPORT", "Fixed check coverage or status is invalid")
    flattened = [item for row in report["checks"] for item in row.get("findings", [])]
    if flattened != report.get("findings"):
        # Groups execute independently, so compare canonical multisets rather
        # than their interleaved execution order.
        if sorted(v.canonical_bytes(item) for item in flattened) != sorted(v.canonical_bytes(item) for item in report.get("findings", [])):
            raise v.ContractError("INVALID_CHECK_REPORT", "Report findings disagree with fixed check details")
    for row in report["checks"]:
        if row.get("group") != dict(CHECKS)[row["check_id"]]:
            raise v.ContractError("INVALID_CHECK_REPORT", "Report check group differs")
        for item in row.get("findings", []):
            if not all(key in item for key in ("check_id", "code", "severity", "path", "line", "reason")) or item["check_id"] != row["check_id"] or item["severity"] not in {"error", "warning"}:
                raise v.ContractError("INVALID_CHECK_REPORT", "Report finding is malformed")
            if item["severity"] == "error" and row["status"] in {"passed", "not_applicable"}:
                raise v.ContractError("INVALID_CHECK_REPORT", "Report errors cannot be marked passed")
    states = {row["status"] for row in report["checks"]}
    status = "failed" if "failed" in states else "incomplete" if "incomplete" in states else "passed"
    if report.get("status") != status or report.get("exit_code") != {"passed": 0, "failed": 1, "incomplete": 2}[status] or report.get("complete") != ("incomplete" not in states):
        raise v.ContractError("INVALID_CHECK_REPORT", "Report status and exit code disagree")
    if expected_rules is not None and report.get("rules_digest") != expected_rules:
        raise v.ContractError("INVALID_CHECK_REPORT", "Report rules differ")
    if expected_object is not None and report.get("object") != expected_object:
        raise v.ContractError("INVALID_CHECK_REPORT", "Report object differs")
    if required_scope == "full" and report.get("scope", {}).get("kind") != "full":
        raise v.ContractError("INVALID_CHECK_REPORT", "A local report cannot pass the repository gate")
    return report


def exit_code(report):
    return validate_report(report)["exit_code"]
