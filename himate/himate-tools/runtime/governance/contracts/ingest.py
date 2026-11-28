"""Single-file authoring workspaces; the workflow supplies content judgement.

One scan, mutable plan/drafts, one review, then a repeatable copy/index operation.
There are no operation graphs, review tickets or application recovery journals.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit

import yaml

from .catalog import Catalog, atomic_write, normalize_page_ranges, pdf_review_result, remaining_page_ranges
from .cards_v3 import parse_card
from .runtime import native_path
from .validation import (ContractError, _workspace_no_links, canonical_bytes, load_yaml, markdown_structure,
                         safe_path, validate_id, workspace_configuration, workspace_layout)
from .workspace_config import relative_path
from . import citation_versions, document_material, document_parser, document_review, intake, source_resources


FORMATS = document_parser.SUPPORTED_FORMATS
IGNORED = {"AGENTS.md", "index.md", "README.md", ".gitkeep", "dbox.local.yml", "dbox.local.yml.example"}
DOCUMENT_CHECK = ".build/document-review-check.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def code_extractor(source, snapshot=None):
    """Use the file's explicit encoding, retaining old declared adapters."""
    encoding = source.get("encoding")
    if encoding is not None:
        adapters = {"utf-8": "code-utf8:1", "gb18030": "code-gb18030:1"}
        if not isinstance(encoding, str) or encoding not in adapters:
            raise ContractError("INVALID_SOURCE_ENCODING", "Code encoding must be utf-8 or gb18030")
        return adapters[encoding]
    return (snapshot or {}).get("extraction", {}).get("extractor") or "code-utf8:1"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path, *, raw=None):
    value = json.loads((path.read_bytes() if raw is None else raw).decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ContractError("INVALID_INPUT", "Expected a JSON object", path)
    return value


def source_path(root, source):
    """Resolve a registered file using its declared workspace, never its text."""
    if source["kind"] != "code":
        if source_resources.is_dbox_path(source["path"]):
            return source_resources.dbox_path(root, source["path"])["actual_path"]
        return safe_path(root, source["path"], ["docs-raw"])
    return _code_source_location(root, source)[0]


def _code_source_location(root, source):
    """Return the checked physical path and its workspace-relative name."""
    config_path, _, config = workspace_configuration(root)
    layout = workspace_layout(config, config_path.parent)
    project = Path(layout["workspace_root"])
    relative = source["path"]
    repo = source.get("repo", source.get("repo_id", ""))
    if repo:
        matches = [item for item in layout["repos"] if item["repo_id"] == repo]
        if len(matches) != 1:
            raise ContractError("CODE_REPO_UNAVAILABLE", repo)
        relative = (PurePosixPath(matches[0]["root"]) / relative).as_posix()
    path = safe_path(project, relative)
    if layout.get("mapping_kind") == "modules":
        allowed = [project / item["workspace_path"] for item in layout["modules"]]
        if not any(path.is_relative_to(directory) for directory in allowed):
            raise ContractError("CODE_SCOPE_REQUIRED", "Register a file inside a configured module", relative)
    return path, relative


def git_read(directory, arguments):
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    environment.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(
        ["git", "--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false",
         "-C", str(directory), *arguments], capture_output=True, timeout=30, env=environment,
    )
    if result.returncode:
        raise ContractError("GIT_SOURCE_UNAVAILABLE", result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def git_location(path):
    directory = path.parent
    while not directory.exists() and directory != directory.parent:
        directory = directory.parent
    base = Path(git_read(directory, ["rev-parse", "--show-toplevel"]).decode().strip())
    return base, path.relative_to(base).as_posix()


def source_commit(path, data):
    try:
        repository, relative = git_location(path)
        commit = git_read(repository, ["rev-parse", "HEAD"]).decode().strip()
        return commit if git_read(repository, ["show", commit + ":" + relative]) == data else None
    except (OSError, subprocess.TimeoutExpired, ContractError, ValueError):
        return None


def old_source(root, source, *, commit=None, expected_hash=None):
    """Find only a real historical version, including an uncommitted baseline."""
    reviewed = source.get("reference_review", {}) if source.get("kind") == "code" else {}
    expected_hash = (expected_hash or reviewed.get("source_sha256") or reviewed.get("last_present_sha256")
                     or source.get("processed_hash"))
    path = source_path(root, source)
    repository, relative = git_location(path)
    if commit:
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", commit):
            raise ContractError("INVALID_GIT_COMMIT", "Use a commit object ID")
        candidates = [commit]
    else:
        candidates = []
        if source.get("source_commit"):
            candidates.append(source["source_commit"])
        candidates += git_read(repository, ["log", "--format=%H", "--", relative]).decode().splitlines()
    for revision in dict.fromkeys(candidates):
        try:
            data = git_read(repository, ["show", revision + ":" + relative])
        except ContractError:
            continue
        if commit or expected_hash and sha(data) == expected_hash:
            return data, revision
    raise ContractError("OLD_SOURCE_UNAVAILABLE", "The processed content is not available in local Git history", source["id"])


def recover_bound_source(root, source, snapshot):
    """Read the exact checked version for both reference validation and preview."""
    try:
        data, reference = source_resources.recover_snapshot_source(root, snapshot)
        return data, reference.split(":", 2)[1] if reference.startswith("git:") else None
    except ContractError as error:
        if "card_references" not in snapshot or error.code not in citation_versions.MISSING_VERSION:
            raise

    expected = snapshot["sha256"]
    try:
        path = source_path(root, source)
        _workspace_no_links(path)
        data = path.read_bytes()
    except (OSError, ContractError):
        data = None
    if data is not None and len(data) == snapshot["bytes"] and sha(data) == expected:
        return data, None
    try:
        data, commit = old_source(root, source, expected_hash=expected)
        if len(data) == snapshot["bytes"] and sha(data) == expected:
            return data, commit
    except (OSError, ContractError, subprocess.TimeoutExpired):
        pass
    raise ContractError("SOURCE_INPUT_UNAVAILABLE", "The exact checked source version is unavailable",
                        snapshot["snapshot_id"])


def _raw_files(root, selected=None):
    """Enumerate supported documents; each original is read once by observe."""
    raw = safe_path(root, "docs-raw")
    found = []
    packages = {}
    if raw.exists():
        for parent, directories, names in os.walk(raw, followlinks=False, onerror=lambda error: (_ for _ in ()).throw(error)):
            location = Path(parent)
            directories[:] = [name for name in directories if not name.startswith(intake.TEMP_PREFIX)]
            for directory in list(directories):
                if (location / directory).is_symlink():
                    raise ContractError("LINKED_SOURCE", "Raw source directories must not be links", directory)
            document = packages.get(location.parent)
            if document is None and intake.MARKER in names:
                package = intake.package_manifest(location)
                if package:
                    document = location / package["document_path"]
            if document is not None:
                packages[location] = document
            for name in sorted(names):
                if name in IGNORED or Path(name).suffix.lower() not in FORMATS:
                    continue
                if document is not None and location / name != document:
                    continue
                found.append((location / name).relative_to(root).as_posix())
    # An explicitly limited ordinary scope does not depend on an unrelated dbox.
    config = raw / "sources/dbox.local.yml"
    use_dbox = selected is None or source_resources.is_dbox_path(selected)
    if use_dbox and config.exists():
        external = source_resources.dbox_root(root)["root"]
        for parent, directories, names in os.walk(external, followlinks=False, onerror=lambda error: (_ for _ in ()).throw(error)):
            if any((Path(parent) / name).is_symlink() for name in directories):
                raise ContractError("LINKED_SOURCE", "dbox source directories must not be links")
            for name in sorted(names):
                if name not in IGNORED and Path(name).suffix.lower() in FORMATS:
                    relative = (Path(parent) / name).relative_to(external).as_posix()
                    found.append("docs-raw/sources/dbox/" + relative)
    return sorted(set(found))


def observe(root, catalog, selected=None, *, include_code=False, code_review=False,
            first=False, keep_content=False, reprocess=False, ingest_only=False):
    target = catalog.get_file(selected) if selected else None
    if code_review and (target is None or target["kind"] != "code"):
        raise ContractError("CODE_REVIEW_SOURCE_REQUIRED", "Select one registered code source ID")
    selected_path = target["path"] if target else selected
    paths = [] if code_review else _raw_files(root, selected_path)
    selected_directory = False
    if selected_path and not target:
        if selected_path != "docs-raw" and not selected_path.startswith("docs-raw/"):
            selected_path = "docs-raw/" + selected_path
        selected_location = safe_path(root, selected_path, ["docs-raw"])
        selected_directory = selected_location.is_dir()
        if selected_path not in paths and selected_location.exists() and not selected_directory:
            raise ContractError("UNSUPPORTED_DOCUMENT_FORMAT", selected_path)
    catalog.register_many([
        {"kind": "raw", "path": path} for path in paths
        if not selected_path or path == selected_path or path.startswith(selected_path.rstrip("/") + "/")
    ])
    if target:
        candidates = [target]
    else:
        candidates = catalog.list_files()
        if selected_path:
            candidates = [row for row in candidates if row["kind"] != "code" and
                          (row["path"] == selected_path or row["path"].startswith(selected_path.rstrip("/") + "/"))]
            if not candidates and not selected_directory:
                raise ContractError("SOURCE_MISSING", selected_path)
        elif include_code:
            referenced = {row["id"] for row in catalog.list_files(kind="code", referenced=True)}
            candidates = [row for row in candidates if row["kind"] != "code" or row["id"] in referenced]
        else:
            candidates = [row for row in candidates if row["kind"] != "code"]
    # Old registries may contain directory guidance mistakenly observed as raw.
    # Keep those identities readable, but never schedule them as source content.
    candidates = [row for row in candidates
                  if row["kind"] != "raw" or PurePosixPath(row["path"]).name not in IGNORED]
    pending = []
    candidates.sort(key=lambda row: (row.get("last_attempt") or "", row["path"]))
    for row in candidates:
        path = source_path(root, row)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            data = None
        current = sha(data) if data is not None else None
        exists = data is not None
        if ingest_only and (row["kind"] == "code" or not exists):
            continue
        if row["kind"] == "code" and (include_code or code_review):
            change = _code_review_change(root, catalog, row, data, current)
        else:
            processing = row.get("processing") or {}
            unfinished = exists and processing.get("source_sha256") == current
            handled_missing = (not exists and row.get("reference_review", {}).get("exists") is False)
            restored = exists and row["kind"] == "raw" and row.get("reference_review", {}).get("exists") is False
            if handled_missing:
                continue
            if not (reprocess or restored or unfinished or row.get("processed_exists") is None
                    or bool(row["processed_exists"]) != exists or row.get("processed_hash") != current):
                continue
            change = ("deleted" if not exists else "reprocess" if reprocess or restored else
                      "resume" if unfinished else
                      "added" if row.get("processed_exists") is None else "modified")
        if change is None:
            continue
        pending.append({**row, "hash": current, "exists": exists, "change": change,
                        **({"content": data} if keep_content else {})})
        if first:
            break
    return pending


def _clear_build(root, *, remove_empty=False):
    path = safe_path(root, ".build")
    if path.exists():
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise OSError("Cannot clean a linked .build directory")
        for child in path.iterdir():
            linked = child.is_symlink() or getattr(child.lstat(), "st_file_attributes", 0) & 0x400
            if child.name == "README.md" and child.is_file() and not linked:
                continue
            if child.is_dir() and not child.is_symlink():
                if linked:
                    child.rmdir()
                else:
                    shutil.rmtree(child)
            else:
                child.unlink()
        if remove_empty and not any(path.iterdir()):
            path.rmdir()
    elif not remove_empty:
        path.mkdir()


def _prepared_document(source):
    return (source.get("kind") == "raw" and source.get("exists", True)
            and PurePosixPath(source["path"]).suffix.lower() in document_material.FORMATS)


def _task_source(catalog, task):
    source = dict(task["source"])
    identity = source.get("source_id")
    registered = catalog.get_file(identity)
    if registered is None:
        raise ContractError("UNKNOWN_SOURCE_ID", str(identity))
    for field in ("id", "kind", "path", "repo", "encoding"):
        if field in source and source[field] != registered[field]:
            raise ContractError("SOURCE_IDENTITY_CHANGED", "Task differs from registered source identity", field)
        source[field] = registered[field]
    if (type(source.get("exists")) is not bool
            or (source["exists"] and not re.fullmatch(r"[0-9a-f]{64}", str(source.get("hash"))))
            or (not source["exists"] and (source.get("hash") is not None
                                         or any(key in source for key in ("original_ref", "parsed", "text_ref"))
                                         or "pdf_review" in task or "document_review" in task))):
        raise ContractError("SOURCE_IDENTITY_CHANGED", "Task existence and original-material facts disagree")
    return source


def _review_batch(root, task, loaded=None):
    source = task["source"]
    if not _prepared_document(source):
        return None
    if not source.get("parsed") or not source.get("original_ref"):
        raise ContractError("DOCUMENT_REVIEW_REQUIRED", "No complete P1 document material is available")
    if loaded is None:
        loaded = document_parser.load(root, source["parsed"], expected_source_id=source["source_id"],
                                      expected_sha256=source["hash"])
    if loaded["manifest"].get("material_version") != 1 or loaded["manifest"]["parse_status"] != "parsed":
        raise ContractError("DOCUMENT_REVIEW_REQUIRED", "Run ingest scan with the current CLI to prepare complete materials")
    original = safe_path(root, source["original_ref"], [".build/materials"]).read_bytes()
    if sha(original) != source["hash"]:
        raise ContractError("SOURCE_CHANGED", "P1 source copy differs from its recorded hash")
    return document_review.validate(root, task, _plan_metadata(root), loaded)


def _checked_document_digest(root, batch, drafts, deletes):
    if batch is None:
        return None
    return sha(canonical_bytes({
        "units": batch["source_units"],
        "plan_sha256": sha(safe_path(root, ".build/plan.md").read_bytes()),
        "drafts": {card["path"]: sha(card["raw"]) for card in drafts},
        "deletes": sorted(deletes),
    }))


def _scan_waiting_for_setup(source, pending, gaps):
    return {"source": source, "pending_at_least": len(pending),
            "gaps": [gap["message"] for gap in gaps],
            "diagnostics": [{"code": gap["code"], "message": gap["message"]} for gap in gaps]}, "blocked"


def scan(root, request):
    root = Path(root)
    unknown = set(request) - {"source", "reprocess", "parser", "review_page_budget", "review_text_budget", "code_review"}
    if unknown:
        raise ContractError("INVALID_INPUT", "Unknown scan fields: " + ", ".join(sorted(unknown))
                            + ". Put conversion settings in the top-level parser object.")
    if "parser" in request:
        document_parser._options(root, request["parser"])
    reprocess = request.get("reprocess", False)
    if type(reprocess) is not bool:
        raise ContractError("INVALID_REPROCESS", "reprocess must be a boolean")
    code_review = request.get("code_review", False)
    if type(code_review) is not bool or (code_review and reprocess):
        raise ContractError("INVALID_CODE_REVIEW", "code_review is a boolean and cannot be combined with reprocess")
    page_budget = request.get("review_page_budget")
    if "review_page_budget" in request and (type(page_budget) is not int or not 1 <= page_budget <= 1000):
        raise ContractError("PDF_REVIEW_BUDGET", "review_page_budget must be an integer from 1 to 1000")
    text_budget = request.get("review_text_budget", document_review.MAX_REVIEW_BYTES)
    if type(text_budget) is not int or not 1 <= text_budget <= 4_000_000:
        raise ContractError("PDF_REVIEW_BUDGET", "review_text_budget must be an integer from 1 to 4000000")
    with Catalog(root) as catalog:
        selected_source = request.get("source")
        registered = catalog.get_file(selected_source) if isinstance(selected_source, str) else None
        if registered is None and isinstance(selected_source, str):
            matches = [row for row in catalog.list_files() if row["path"] == selected_source]
            registered = matches[0] if len(matches) == 1 else None
        if registered is not None and (registered["kind"] == "code" or not source_path(root, registered).exists()):
            if reprocess:
                raise ContractError("MAINTENANCE_SOURCE_REQUIRED", "Use maintain prepare for existing-card reference maintenance")
            from .maintenance import prepare
            return prepare(root, {"source": registered["id"]}, catalog=catalog)
        if code_review:
            raise ContractError("CODE_REVIEW_SOURCE_REQUIRED", "Select one registered code source ID")
        if reprocess:
            registered = catalog.get_file(selected_source) if isinstance(selected_source, str) else None
            if registered is None and isinstance(selected_source, str):
                matches = [row for row in catalog.list_files() if row["path"] == selected_source]
                registered = matches[0] if len(matches) == 1 else None
            if registered is None:
                raise ContractError("REPROCESS_SOURCE_REQUIRED", "Select one explicitly registered source ID or exact path")
            selected_source = registered["id"]
        pending = observe(root, catalog, selected_source, code_review=code_review, first=True,
                          keep_content=True, reprocess=reprocess, ingest_only=True)
        if not pending:
            _clear_build(root)
            catalog.set_maintenance_input(None)
            return {"pending": 0}, "unchanged"
        selected = pending[0]
        source = {key: value for key, value in selected.items() if key != "content"}
        source["code_id" if source["kind"] == "code" else "doc_id"] = source["id"]
        source["source_id"] = source["id"]
        if selected["kind"] != "code" and selected["content"] is not None:
            try:
                document_parser.require_document_parser(Path(source["path"]).suffix.lower())
            except ContractError as error:
                return _scan_waiting_for_setup(source, pending, [{"code": error.code, "message": str(error)}])
        _clear_build(root)
        catalog.set_maintenance_input(None)
        catalog.touch_attempt(selected["id"])
        cards = catalog.cards_for(selected["id"])
    if (source.get("processing", {}).get("source_sha256") != source["hash"]
            or source["change"] == "reprocess"):
        source.pop("processing", None)
    source["source_commit"] = (source_commit(source_path(root, selected), selected["content"])
                               if selected["content"] is not None else None)
    materials = safe_path(root, ".build/materials")
    materials.mkdir()
    gaps = []
    pdf_review, review = None, None
    if selected["content"] is not None:
        suffix = Path(selected["path"]).suffix.lower()
        original = materials / ("current" + suffix)
        original.write_bytes(selected["content"])
        source["original_ref"] = original.relative_to(root).as_posix()
        try:
            if selected["kind"] == "code":
                text = source_resources.extract_code_text(selected["content"], code_extractor(selected))[0]
                text_path = materials / ("code-text.txt" if suffix == ".txt" else "current.txt")
                text_path.write_text(text, encoding="utf-8")
                source["text_ref"] = text_path.relative_to(root).as_posix()
            else:
                if _prepared_document(source):
                    parsed, loaded = document_parser.prepare_document(root, source, selected["content"], options=request.get("parser"))
                else:
                    assets = (intake.package_assets(root, source["path"], expected_sha256=source["hash"])
                              if suffix == ".md" else None)
                    parsed = document_parser.parse(root, source, selected["content"], ".build/materials/parsed",
                                                   options=request.get("parser"), local_images=assets)
                source["parsed"] = parsed
                source["text_ref"] = parsed["text_ref"]
                setup_gaps = [gap for gap in parsed.get("gaps", []) if gap.get("code") in document_parser.PARSER_SETUP_CODES]
                if setup_gaps:
                    return _scan_waiting_for_setup(source, pending, setup_gaps)
                # Keep the old entry usable without changing the parser's
                # manifest-owned files or its text/locator semantics.
                if suffix not in {".txt", ".pdf"}:
                    text_file = Path(native_path(safe_path(root, parsed["text_ref"])))
                    (materials / "current.txt").write_bytes(text_file.read_bytes())
                for item in parsed.get("gaps", []):
                    message = item.get("message", str(item)) if isinstance(item, dict) else str(item)
                    if isinstance(item, dict) and "count" in item:
                        message += f" ({item['count']} occurrences; details: {item['details_ref']})"
                    gaps.append(message)
                if _prepared_document(source) and parsed["parse_status"] == "parsed":
                    review, pdf_review = document_review.prepare(root, source, loaded, text_budget, page_budget)
        except (OSError, ValueError, UnicodeError, ImportError, ContractError) as error:
            gaps.append(str(error))
    if _prepared_document(source) and review is None:
        return {"source": source, "gaps": gaps, "pending_at_least": len(pending)}, "blocked"
    (root / ".build/cards").mkdir()
    task = {"source": source, "affected_cards": [{"id": card["id"], "path": card["path"],
                                                 "title": card["title"]} for card in cards],
            "cards_dir": ".build/cards", "plan_ref": ".build/plan.md", "gaps": gaps}
    task["task_type"] = "document_ingest"
    if pdf_review is not None:
        task["pdf_review"] = pdf_review
    if review is not None:
        task["document_review"] = review
    write_json(root / ".build/task.json", task)
    return {**task, "task_ref": ".build/task.json", "pending_at_least": len(pending)}, "prepared"


def _finding(error, path=""):
    result = {"code": getattr(error, "code", "INVALID_CARD"),
              "path": path or str(getattr(error, "path", "")), "message": str(error)}
    if getattr(error, "field", ""):
        result.update(field=error.field, actual=error.actual)
    return result


def _drafts(root, catalog, rules=None, *, concise_only=False, findings=None):
    directory = safe_path(root, ".build/cards")
    lookup = {row["id"]: row for row in catalog.list_files()}
    drafts = []
    for path in sorted(directory.rglob("*.md")) if directory.exists() else []:
        reference = "knowledge/" + path.relative_to(directory).as_posix()
        try:
            drafts.append(parse_card(path.read_bytes(), reference, rules,
                                     source_lookup=lookup, concise_only=concise_only))
        except (ValueError, OSError, ContractError, yaml.YAMLError) as error:
            if findings is None:
                raise
            findings.append(_finding(error, reference))
    return drafts


def _plan_metadata(root):
    path = safe_path(root, ".build/plan.md")
    if not path.is_file():
        raise ContractError("PLAN_REQUIRED", "P2 must write plan.md with a cards target list", ".build/plan.md")
    try:
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", path.read_text(encoding="utf-8-sig"), re.S)
        metadata = load_yaml(match.group(1)) if match else None
        if not isinstance(metadata, dict) or not isinstance(metadata.get("cards"), list):
            raise ValueError("Expected YAML frontmatter with cards: [{id, path}], or cards: []")
        return metadata
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        raise ContractError("INVALID_PLAN", str(error), ".build/plan.md") from error


def _required_code_refs(item):
    required = item.get("required_code_refs", [])
    if not isinstance(required, list):
        raise ValueError("required_code_refs must be a list")
    for entry in required:
        if (not isinstance(entry, dict) or not entry or set(entry) - {"path", "symbol"}
                or any(not isinstance(value, str) or not value.strip() or value != value.strip()
                       for value in entry.values())):
            raise ValueError("Each required code reference needs a path, a symbol, or both")
        if "path" in entry and relative_path(entry["path"]) == ".":
            raise ValueError("A required code reference path must identify a file")
    return required


def _planned_cards(root):
    """Read P2's targets and required code locations."""
    metadata = _plan_metadata(root)
    try:
        targets, paths = {}, set()
        for item in metadata["cards"]:
            if not isinstance(item, dict):
                raise ValueError("Each planned card needs id and path")
            identity = validate_id(item.get("id"))
            reference = item.get("path")
            safe_path(root, reference, ["knowledge"])
            if not reference.endswith(".md"):
                raise ValueError("Planned paths must name knowledge Markdown files")
            if identity in targets or reference.casefold() in paths:
                raise ValueError("Planned card IDs and paths must be unique")
            targets[identity] = {"path": reference, "required_code_refs": _required_code_refs(item)}
            paths.add(reference.casefold())
        return targets
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        raise ContractError("INVALID_PLAN", str(error), ".build/plan.md") from error


def _matches_required_code_ref(required, path, symbols):
    planned_path = required.get("path")
    return ((planned_path is None or path == planned_path or path.endswith("/" + planned_path))
            and ("symbol" not in required or required["symbol"] in symbols))


def _deletes(root):
    path = safe_path(root, ".build/changes.json")
    value = read_json(path).get("delete", []) if path.exists() else []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ContractError("INVALID_DELETE_LIST", "changes.json delete must be a list of knowledge paths")
    for reference in value:
        safe_path(root, reference, ["knowledge"])
        if not reference.endswith(".md") or reference == "knowledge/AGENTS.md":
            raise ContractError("INVALID_DELETE_PATH", reference)
    return value


def _parsed_document(root, source, data, context, *, options=None):
    """Load the author's exact parse, or prepare a distinct secondary source once."""
    identity, digest = source["source_id"], sha(data)
    if identity == context.get("primary_id"):
        if (identity, digest) in context["loaded"]:
            return context["loaded"][(identity, digest)]
        # A failed or removed P1 parse is a gap, not permission for P4 to
        # silently give the reviewer different material from the author.
        raise ContractError("SOURCE_PARSING_UNAVAILABLE", "P1 has no verified parse for this source", source["path"])
    options_hash = sha(canonical_bytes(options or {}))
    key = identity, digest, options_hash
    if key in context["loaded"]:
        return context["loaded"][key]
    if context["formal"]:
        from . import source_read

        reading = source_read.create(root, source, data, options=options)
        try:
            loaded = document_parser.load(root, reading["parsed"], expected_source_id=identity,
                                          expected_sha256=digest)
        finally:
            source_read.release(root, reading["read_id"])
    else:
        index_ref = ".build/materials/reference-parses.json"
        index_path = document_parser.safe_path(root, index_ref, [".build/materials"])
        index = read_json(index_path) if index_path.is_file() else {}
        index_key = identity + ":" + digest + ":" + options_hash
        parsed = index.get(index_key)
        if parsed is None:
            component = sha(identity.encode("utf-8"))[:20] + "-" + digest[:16] + "-" + options_hash[:16]
            assets = (intake.package_assets(root, source["path"], expected_sha256=digest)
                      if PurePosixPath(source["path"]).suffix.lower() == ".md" else None)
            parsed = document_parser.parse(root, source, data,
                                           f".build/materials/references/{component}", options=options, local_images=assets)
            index[index_key] = parsed
            write_json(document_parser.safe_path(root, index_ref, [".build/materials"]), index)
        loaded = document_parser.load(root, parsed, expected_source_id=identity, expected_sha256=digest)
        descriptor_key = identity if identity not in context["descriptors"] else identity + ":" + parsed["profile_sha256"]
        context["descriptors"][descriptor_key] = parsed
    context["loaded"][key] = loaded
    return loaded


def _reference_check(root, source, reference, staged=None, *, extractor=None, context=None):
    path = PurePosixPath(source["path"])
    context = context if context is not None else {"formal": True, "loaded": {}, "legacy": {}, "data": {}, "descriptors": {}}
    identity = source["source_id"]
    if staged is not None:
        data = staged
    elif identity in context["data"]:
        data = context["data"][identity]
    else:
        try:
            data = source_path(root, source).read_bytes()
        except FileNotFoundError:
            data, _ = old_source(root, source)
        context["data"][identity] = data
    if source["kind"] == "code":
        symbol = reference.get("symbol")
        if symbol or reference.get("selector"):
            from .code_symbols import resolve

            selector = reference.get("selector") or (symbol if isinstance(symbol, dict)
                                                      else {"kind": "function", "name": symbol})
            result = resolve(data, selector, path=source["path"], extractor=extractor,
                             cache=context.setdefault("code_symbols", {}))
            if result["status"] != "resolved":
                raise ContractError("CODE_SYMBOL_" + result["status"].upper(),
                                    f"{symbol or selector}: {result['reason']}", source["path"])
            if "line_start" in reference and (
                reference["line_start"] != result["range"]["start_line"]
                or reference["line_end"] != result["range"]["end_line"]
            ):
                raise ContractError("CODE_RANGE_CHANGED", "Update the symbol's current line range", source["path"])
            return result
        text, _ = source_resources.extract_code_text(data, extractor or "code-utf8:1")
        addresses = []
    else:
        suffix = path.suffix.lower()
        locator = reference.get("locator")
        kind = (locator or {}).get("kind")
        options = (locator or {}).get("parser") if kind == "element" else None
        legacy = (suffix in {".md", ".txt"} or
                  suffix in {".pdf", ".docx"} and
                  ("line_start" in reference or reference.get("section") or
                   kind in {"lines", "section", "paragraph", "paragraphs", "table_row"}))
        if legacy:
            key = identity, sha(data)
            if key not in context["legacy"]:
                context["legacy"][key] = source_resources.extract_document(data, suffix)
            text, addresses, _, _ = context["legacy"][key]
        else:
            loaded = _parsed_document(root, source, data, context, options=options)
            text, addresses = loaded["text"], []
        if locator and kind not in {"lines", "section"}:
            if kind in {"paragraph", "paragraphs", "table_row"}:
                source_resources.document_segments(addresses, locator, suffix)
            else:
                document_parser.select(_parsed_document(root, source, data, context, options=options), locator)
        if "page_start" in reference and not legacy:
            document_parser.select(loaded, {"kind": "pages", "start": reference["page_start"],
                                             "end": reference["page_end"]})
        if "line_start" in reference and suffix not in {".md", ".txt", ".pdf", ".docx"}:
            raise ContractError("INVALID_SOURCE_LOCATOR", "Converted text lines are not native source addresses", source["path"])
    if "line_start" in reference:
        if not 1 <= reference["line_start"] <= reference["line_end"] <= len(text.splitlines()):
            raise ContractError("SOURCE_RANGE_INVALID", "Line range is outside its source", source["path"])
    if "page_start" in reference and (source["kind"] == "code" or legacy):
        pages = [item.get("page", 0) for item in addresses]
        if not pages or reference["page_end"] > max(pages):
            raise ContractError("SOURCE_RANGE_INVALID", "Page range is outside its source", source["path"])
    if reference.get("section") and reference["section"] not in text:
        raise ContractError("SOURCE_SECTION_MISSING", reference["section"], source["path"])
    return None


def _code_reference_findings(root, source, references, data):
    findings = []
    extractor = code_extractor(source)
    context = {}
    for card_id, reference in references:
        if reference.get("snapshot_id"):
            continue
        try:
            _reference_check(root, source, reference, data, extractor=extractor, context=context)
        except (ValueError, OSError, ContractError, subprocess.TimeoutExpired) as error:
            findings.append({**_finding(error, source["path"]), "card_id": card_id})
    return findings


def _code_review_change(root, catalog, source, data, digest):
    references = catalog.reference_rows(source["id"])
    if not references:
        return None
    from . import evidence_review
    cards = [catalog.get_card(row["id"]) for row in catalog.cards_for(source["id"])]
    states, _ = evidence_review.observe(root, catalog, cards, data={source["id"]: data}, only_source=source["id"])
    statuses = [item["status"] for rows in states.values() for item in rows
                if item["source_id"] == source["id"]]
    if not statuses or all(status == "fresh" for status in statuses):
        return None
    if "unversioned" in statuses:
        return "baseline_missing"
    if "unresolved" in statuses:
        return "deleted" if data is None else "reference_invalid"
    return "modified" if "changed" in statuses else "relocated"


def _snapshot_reference_check(root, source, reference, snapshot, registry, context):
    """A real retained document snapshot must never be checked against newer bytes."""
    frozen = context.setdefault("frozen", {})
    snapshot_id = snapshot["snapshot_id"]
    if snapshot_id not in frozen:
        frozen[snapshot_id], _ = recover_bound_source(root, source, snapshot)
    data = frozen[snapshot_id]
    locator = reference.get("locator")
    if locator is None:
        if "line_start" in reference:
            locator = {"kind": "lines", "start": reference["line_start"], "end": reference["line_end"]}
        elif "page_start" in reference:
            locator = {"kind": "pages", "start": reference["page_start"], "end": reference["page_end"]}
        else:
            locator = {"kind": "section", "anchor": reference.get("section")}
    evidence = {"evidence_ref": reference.get("evidence_ref", "document-reference"),
                "source_id": source["source_id"], "snapshot_id": snapshot_id, "locator": locator}
    source_resources.validate_source_ref(evidence, registry)
    suffix = snapshot.get("format", PurePosixPath(source["path"]).suffix.lower())
    if suffix in {".pdf", ".docx"} and locator.get("kind") in {"lines", "section"}:
        # The historical binary adapter has native paragraph/page checks and
        # a separate text view. Bind that text view before using old line or
        # section semantics; Docling text cannot substitute for it.
        key = source["source_id"], snapshot["sha256"]
        if key not in context["legacy"]:
            context["legacy"][key] = source_resources.extract_document(data, suffix)
        text, addresses, extractor, _ = context["legacy"][key]
        retained = snapshot.get("extraction") or {}
        if extractor != retained.get("extractor"):
            raise ContractError("SOURCE_ADAPTER_UNAVAILABLE", "Installed document adapter differs from the retained snapshot")
        locator_hash = sha(canonical_bytes({"locators": addresses}))
        if (sha(text.encode("utf-8")) != retained.get("text_sha256")
                or locator_hash != retained.get("locator_sha256")
                or snapshot.get("locator", {}).get("sha256", locator_hash) != locator_hash):
            raise ContractError("SOURCE_EXTRACTION_UNAVAILABLE", "Retained document text or native locators differ")
        text_reference = dict(reference)
        if locator["kind"] == "lines":
            text_reference["line_start"] = locator.get("start", locator.get("number"))
            text_reference["line_end"] = locator.get("end", text_reference["line_start"])
        elif not text_reference.get("section"):
            text_reference["section"] = locator.get("section", locator.get("anchor", locator.get("id")))
        _reference_check(root, source, text_reference, data, context=context)
    else:
        source_resources.validate_reference(evidence, registry, lambda _snapshot: data)


def _card_reference_check(root, source, reference, kind, registry, context, staged=None):
    """Use the same actual-version checks for candidates and retained refs."""
    identity = source["source_id"]
    if (source["kind"] == "code") != (kind == "code"):
        raise ContractError("SOURCE_KIND_MISMATCH", identity)
    snapshot_id = reference.get("snapshot_id")
    snapshot = next((item for item in registry.get("snapshots", []) if item["snapshot_id"] == snapshot_id), None)
    # Old cards may retain a version label without a registered snapshot.
    # Validate their actual current/recoverable source and native locator;
    # only a registered snapshot establishes immutable version semantics.
    if snapshot is not None and snapshot.get("source_id") != identity:
        raise ContractError("SOURCE_SNAPSHOT_MISMATCH", "The retained snapshot does not belong to this source")
    if snapshot is not None:
        if kind == "doc":
            _snapshot_reference_check(root, source, reference, snapshot, registry, context)
            return None
        frozen = context.setdefault("frozen", {})
        if snapshot_id not in frozen:
            frozen[snapshot_id], _ = recover_bound_source(root, source, snapshot)
        staged = frozen[snapshot_id]
    extractor = code_extractor(source, snapshot) if kind == "code" else None
    result = _reference_check(root, source, reference, staged, extractor=extractor, context=context)
    if kind == "code" and snapshot is None:
        from . import evidence_review
        actual = staged if staged is not None else context["data"][identity]
        evidence_review.record(context, source, reference, actual)
    return result


def check(root, request, rules=None):
    """Fixed checks only; the independent reviewer judges actual knowledge."""
    findings = []
    formal = bool(request.get("formal"))
    maintenance_fixed = None
    try:
        if not formal:
            safe_path(root, DOCUMENT_CHECK, [".build"]).unlink(missing_ok=True)
            from . import evidence_review
            safe_path(root, evidence_review.CHECK, [".build"]).unlink(missing_ok=True)
            from . import maintenance
            safe_path(root, maintenance.CHECK, [".build"]).unlink(missing_ok=True)
        planned = None if formal else _planned_cards(root)
        catalog = Catalog(root)
    except (ValueError, OSError, ContractError, yaml.YAMLError) as error:
        return {"findings": [_finding(error)]}, "failed"
    with catalog:
        try:
            drafts = (catalog.all_cards() if request.get("formal")
                      else _drafts(root, catalog, rules, concise_only=True, findings=findings))
            # A partial parsed set cannot establish plan membership or links.
            if findings:
                return {"findings": findings}, "failed"
            deletes = set() if request.get("formal") else set(_deletes(root))
            overlap = deletes & {card["path"] for card in drafts}
            if overlap:
                raise ContractError("WRITE_DELETE_CONFLICT", "A candidate cannot also be deleted", ", ".join(sorted(overlap)))
            staged_sources = {}
            task_bytes = None
            document_batch = None
            context = {"formal": formal, "loaded": {}, "legacy": {}, "data": {}, "descriptors": {}}
            task_path = safe_path(root, ".build/task.json")
            if not formal and task_path.is_file():
                task_bytes = task_path.read_bytes()
                task = read_json(task_path, raw=task_bytes)
                source = _task_source(catalog, task)
                task["source"] = source
                context["primary_id"] = source["source_id"]
                if source.get("original_ref"):
                    staged_sources[source["source_id"]] = safe_path(
                        root, source["original_ref"], [".build/materials"]
                    ).read_bytes()
                    if sha(staged_sources[source["source_id"]]) != source["hash"]:
                        raise ContractError("SOURCE_CHANGED", "P1 source copy differs from its recorded hash")
                if source.get("parsed"):
                    loaded = document_parser.load(root, source["parsed"], expected_source_id=source["source_id"],
                                                  expected_sha256=source["hash"])
                    context["loaded"][(source["source_id"], source["hash"])] = loaded
                document_batch = _review_batch(root, task, context["loaded"].get((source["source_id"], source["hash"])))
                if maintenance.required(task, catalog):
                    findings.extend(maintenance.findings(root, catalog, task, drafts, deletes, context=context))
                    if not findings:
                        maintenance_fixed = catalog.maintenance_input()
        except (ValueError, OSError, ContractError, yaml.YAMLError) as error:
            return {"findings": [_finding(error)]}, "failed"
        if planned is not None:
            actual = {card["id"]: card["path"] for card in drafts}
            for identity in sorted(planned.keys() | actual.keys()):
                expected_path, actual_path = planned.get(identity, {}).get("path"), actual.get(identity)
                if expected_path != actual_path:
                    findings.append({"code": "PLAN_CARD_MISMATCH", "card_id": identity,
                                     "path": actual_path or expected_path,
                                     "expected_path": expected_path, "actual_path": actual_path,
                                     "message": "Expected " + (expected_path or "<not planned>")
                                                + "; found " + (actual_path or "<missing candidate>")
                                                + ". Fix the candidate in P3; revise P2 only if the target changes."})
        replaced = deletes | {card["path"] for card in drafts}
        candidates = {card["id"]: card for card in catalog.all_cards() if card["path"] not in replaced}
        for card in drafts:
            other = candidates.get(card["id"])
            if other and other["path"] != card["path"] and other["path"] not in deletes:
                findings.append({"code": "DUPLICATE_CARD_ID", "path": card["path"], "message": card["id"]})
            candidates[card["id"]] = card
        if len({card["id"] for card in drafts}) != len(drafts):
            findings.append({"code": "DUPLICATE_CARD_ID", "message": "Draft IDs repeat"})
        source_lookup = {row["source_id"]: row for row in catalog.list_files()}
        registry = catalog.registry
    code_paths = {}
    for card in drafts:
        required = (planned or {}).get(card["id"], {}).get("required_code_refs", [])
        checked_code_refs = []
        for kind in ("doc", "code"):
            for reference in card[kind + "_ref"]:
                identity = reference[kind + "_id"]
                source = source_lookup.get(identity)
                try:
                    if source is None:
                        raise ContractError("UNKNOWN_SOURCE_ID", identity)
                    resolved = _card_reference_check(root, source, reference, kind, registry, context,
                                                     staged_sources.get(identity))
                    if kind == "code" and required:
                        if identity not in code_paths:
                            code_paths[identity] = (_code_source_location(root, source)[1]
                                                    if source.get("repo", source.get("repo_id"))
                                                    else source["path"])
                        symbols = ()
                        if resolved:
                            match = resolved["matches"][0]
                            symbols = (match["name"], "::".join([*match["scope"], match["name"]]))
                        checked_code_refs.append((code_paths[identity], symbols))
                except (ValueError, OSError, ContractError, subprocess.TimeoutExpired) as error:
                    findings.append({"code": getattr(error, "code", "SOURCE_UNAVAILABLE"),
                                     "path": card["path"], "message": str(error)})
        for location in required:
            if not any(_matches_required_code_ref(location, *ref) for ref in checked_code_refs):
                findings.append({"code": "PLANNED_CODE_REF_MISSING", "card_id": card["id"], "path": card["path"],
                                 "required_code_ref": location,
                                 "message": "Add the planned code reference in P3, or revisit the evidence in P2."})
    structures = {card["path"]: markdown_structure(card["raw"]) for card in candidates.values()}
    # Check final relationships, including retained cards that link to a
    # removed card. Their source material does not need to be re-read.
    for card in candidates.values():
        for relation in card["metadata"].get("relations", []):
            if relation.get("target_card_id") not in candidates:
                findings.append({"code": "UNKNOWN_RELATED_CARD", "path": card["path"],
                                 "message": str(relation.get("target_card_id"))})
        for link in structures[card["path"]]["links"]:
            target = link["target"]
            if target is None:
                findings.append({"code": "UNKNOWN_LINK_LABEL", "path": card["path"], "message": link["label"]})
                continue
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            related = ((PurePosixPath(card["path"]).parent / unquote(parsed.path)).as_posix()
                       if parsed.path else card["path"])
            normalized = Path(os.path.normpath(related)).as_posix()
            if normalized.startswith("knowledge/") and normalized.endswith(".md"):
                # Navigation is a Markdown link target, not a knowledge
                # card. Resolve links from the final file overlay while
                # keeping card-ID relationships in the catalog.
                if normalized not in structures and normalized not in deletes:
                    target_path = safe_path(root, normalized, ["knowledge"])
                    if target_path.is_file():
                        structures[normalized] = markdown_structure(target_path.read_bytes())
                if normalized not in structures or normalized in deletes:
                    findings.append({"code": "BROKEN_CARD_LINK", "path": card["path"], "message": target})
                elif parsed.fragment and unquote(parsed.fragment) not in structures[normalized]["anchors"]:
                    findings.append({"code": "BROKEN_CARD_ANCHOR", "path": card["path"], "message": target})
    if not findings and not formal:
        from . import evidence_review
        atomic_write(safe_path(root, evidence_review.CHECK, [".build"]),
                     canonical_bytes(evidence_review.receipt(task_bytes, drafts, context)))
    if not findings and document_batch is not None:
        try:
            checked = {"task_sha256": sha(task_bytes),
                       "document_review_sha256": _checked_document_digest(root, document_batch, drafts, deletes)}
            atomic_write(safe_path(root, DOCUMENT_CHECK, [".build"]), canonical_bytes(checked))
        except (ValueError, OSError, ContractError) as error:
            findings.append(_finding(error))
    if not findings and maintenance_fixed is not None:
        try:
            atomic_write(safe_path(root, maintenance.CHECK, [".build"]),
                         canonical_bytes({"sha256": maintenance.digest(root, maintenance_fixed, drafts, deletes)}))
        except (ValueError, OSError, ContractError) as error:
            findings.append(_finding(error))
    return {"findings": findings, "card_ids": [card["id"] for card in drafts],
            "parsed_sources": context["descriptors"],
            "review_required": True}, "failed" if findings else "passed"


def commit(root, request):
    """Copy the reviewed drafts and refresh metadata; retry the same workspace.

    Documents are checked against their fixed P1 copy and planned reading range.
    The five-node workflow owns independent content review and its order.
    """
    task_path = safe_path(root, ".build/task.json")
    if not task_path.is_file():
        raise ContractError("TASK_REQUIRED", "Run ingest scan before commit")
    task_bytes = task_path.read_bytes()
    task = read_json(task_path, raw=task_bytes)
    from . import maintenance
    with Catalog(root, refresh=False) as catalog:
        _task_source(catalog, task)
        maintenance_required = maintenance.required(task, catalog)
    if maintenance_required:
        return maintenance.commit(root, request)
    source = task["source"]
    # A previous copy may have stopped before deleting a moved card's old path.
    # Finish the reviewed overlay before reading formal cards into the catalog.
    with Catalog(root, refresh=False, rollback_registry=True) as catalog:
        source = _task_source(catalog, task)
        task["source"] = source
        drafts = _drafts(root, catalog)
        deletes = _deletes(root)
        if request.get("defer"):
            return {"source_id": source["source_id"], "reason": request.get("reason", "Materials are incomplete")}, "deferred"
        document_batch = _review_batch(root, task)
        pdf_batch = document_batch["pdf_batch"] if document_batch is not None else None
        if not drafts and not request.get("reason"):
            raise ContractError("NO_CHANGE_REASON_REQUIRED", "Explain the reviewed no-card result")
        if document_batch is not None:
            checked_path = safe_path(root, DOCUMENT_CHECK, [".build"])
            checked = read_json(checked_path) if checked_path.is_file() else {}
            if (checked.get("task_sha256") != sha(task_bytes)
                    or checked.get("document_review_sha256") != _checked_document_digest(root, document_batch, drafts, deletes)):
                raise ContractError("DOCUMENT_REVIEW_NOT_CHECKED", "Run P4 again for the current document range, plan and candidates")
        from . import evidence_review
        evidence_path = safe_path(root, evidence_review.CHECK, [".build"])
        if evidence_path.is_file():
            versions = evidence_review.verify(root, catalog, read_json(evidence_path), task_bytes, drafts)
            drafts = evidence_review.stamp(drafts, versions)
        elif any(ref for card in drafts for ref in card["code_ref"]
                 if not evidence_review.historical(ref, catalog.registry)):
            raise ContractError("CODE_EVIDENCE_NOT_CHECKED", "Run independent reference checks before publishing code references")
        for card in drafts:
            destination = safe_path(root, card["path"], ["knowledge"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(destination, card["raw"])
        for reference in deletes:
            safe_path(root, reference, ["knowledge"]).unlink(missing_ok=True)
        catalog.rebuild()
        from .library import build_search

        current = catalog.get_file(source["source_id"])
        review_identity = document_batch["review_sha256"] if document_batch is not None else None
        processing = (pdf_review_result(current, source["hash"], pdf_batch["pages"], pdf_batch["total_pages"],
                                        restart=source["change"] == "reprocess", review_sha256=review_identity)
                      if pdf_batch is not None else None)
        remaining_units = []
        if document_batch is not None and pdf_batch is None:
            previous = current.get("processing", {})
            reviewed = document_batch["reviewed_units"]
            if (source["change"] != "reprocess" and previous.get("source_sha256") == source["hash"]
                    and previous.get("review_sha256") == document_batch["review_sha256"]):
                reviewed = normalize_page_ranges([*reviewed, *previous["reviewed_units"]], document_batch["total_units"])
            already_complete = (not previous and source["change"] != "reprocess"
                                and current.get("processed_hash") == source["hash"] and current["processed_exists"] is True)
            if not already_complete:
                remaining_units = remaining_page_ranges(document_batch["total_units"], reviewed)
            if remaining_units:
                processing = {"source_sha256": source["hash"], "review_sha256": document_batch["review_sha256"],
                              "reviewed_units": reviewed}
        result = {"source_id": source["source_id"],
                  "processed_hash": current.get("processed_hash") if processing is not None else source["hash"],
                  "card_ids": [card["id"] for card in drafts], "deleted": deletes,
                  "source_complete": processing is None,
                  "reason": request.get("reason", "Reviewed card changes published")}
        if processing is not None:
            result["processing"] = processing
            if pdf_batch is not None:
                result["remaining_pages"] = remaining_page_ranges(
                    pdf_batch["total_pages"], processing["reviewed_pages"])
            else:
                result["remaining_units"] = remaining_units
        if document_batch is not None:
            result["source_units"] = document_batch["source_units"]
        # Publish the matching read view before updating the authoritative lock.
        # A failure rolls back the entire SQLite transaction and leaves P5 retryable.
        projected_source = {"processing": processing}
        if processing is None:
            projected_source.update(processed=True, processed_exists=source["exists"],
                                    processed_hash=source["hash"], source_commit=source.get("source_commit"))
        build_search(catalog, panel_sources={source["source_id"]: projected_source})
        if pdf_batch is not None:
            catalog.record_pdf_review(
                source["source_id"], source["hash"], pdf_batch["pages"], pdf_batch["total_pages"],
                source_commit=source.get("source_commit"), restart=source["change"] == "reprocess",
                review_sha256=review_identity)
        elif document_batch is not None:
            catalog.record_document_review(source["source_id"], source["hash"], processing,
                                           source_commit=source.get("source_commit"))
        else:
            catalog.mark_processed(source["source_id"], source["hash"], source["exists"],
                                   source_commit=source.get("source_commit"))
    # The committed source ledger is authoritative. A local receipt is optional.
    receipt_ref = "artifacts/ingest/latest.json"
    try:
        receipt = safe_path(root, receipt_ref)
        atomic_write(receipt, (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    except OSError as error:
        result["receipt_warning"] = {"code": "INGEST_RECEIPT_WRITE_FAILED", "message": str(error), "path": receipt_ref}
    # Clean staging after a committed publication, even if the receipt could not be saved.
    try:
        _clear_build(root, remove_empty=True)
    except OSError as error:
        result["cleanup_error"] = str(error)
    return result, "completed"


def maintenance_prepare(root, request):
    from .maintenance import prepare
    return prepare(root, request)


def maintenance_check(root, request, rules=None):
    from .maintenance import check
    return check(root, request, rules)


def maintenance_commit(root, request):
    from .maintenance import commit
    return commit(root, request)
