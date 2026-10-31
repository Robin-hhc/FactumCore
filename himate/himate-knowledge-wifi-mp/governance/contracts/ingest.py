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

from .catalog import Catalog, atomic_write
from .cards_v3 import parse_card
from .validation import ContractError, canonical_bytes, load_yaml, markdown_structure, safe_path, validate_id
from . import document_parser, source_resources, workspace_config


FORMATS = document_parser.SUPPORTED_FORMATS
IGNORED = {"AGENTS.md", "index.md", "README.md", ".gitkeep", "dbox.local.yml", "dbox.local.yml.example"}


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


def read_json(path):
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ContractError("INVALID_INPUT", "Expected a JSON object", path)
    return value


def workspace(root):
    path = workspace_config.select(root)
    return path.parent, load_yaml(path.read_bytes())


def source_path(root, source):
    """Resolve a registered file using its declared workspace, never its text."""
    if source["kind"] != "code":
        if source_resources.is_dbox_path(source["path"]):
            return source_resources.dbox_path(root, source["path"])["actual_path"]
        return safe_path(root, source["path"], ["docs-raw"])
    project, config = workspace(root)
    relative = source["path"]
    repo = source.get("repo", source.get("repo_id", ""))
    if repo:
        from .validation import normalize_workspace

        mapped = normalize_workspace(config, project)
        matches = [item for item in mapped.get("repos", []) if item["repo_id"] == repo]
        if len(matches) != 1:
            raise ContractError("CODE_REPO_UNAVAILABLE", repo)
        relative = (PurePosixPath(matches[0]["root"]) / relative).as_posix()
    path = safe_path(project, relative)
    from .validation import workspace_layout

    layout = workspace_layout(config, project)
    if layout.get("mapping_kind") == "modules":
        allowed = [project / item["workspace_path"] for item in layout["modules"]]
        if not any(path.is_relative_to(directory) for directory in allowed):
            raise ContractError("CODE_SCOPE_REQUIRED", "Register a file inside a configured module", relative)
    return path


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
    expected_hash = expected_hash or source.get("processed_hash")
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


def _raw_files(root, selected=None):
    """Enumerate supported documents; each original is read once by observe."""
    raw = safe_path(root, "docs-raw")
    found = []
    if raw.exists():
        for parent, directories, names in os.walk(raw, followlinks=False, onerror=lambda error: (_ for _ in ()).throw(error)):
            for directory in list(directories):
                if (Path(parent) / directory).is_symlink():
                    raise ContractError("LINKED_SOURCE", "Raw source directories must not be links", directory)
            for name in sorted(names):
                if name in IGNORED or Path(name).suffix.lower() not in FORMATS:
                    continue
                reference = (Path(parent) / name).relative_to(root).as_posix()
                found.append(reference)
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


def observe(root, catalog, selected=None, *, include_code=False, first=False, keep_content=False, reprocess=False):
    target = catalog.get_file(selected) if selected else None
    selected_path = target["path"] if target else selected
    paths = _raw_files(root, selected_path)
    if selected_path and not target:
        if not selected_path.startswith("docs-raw/"):
            selected_path = "docs-raw/" + selected_path
        if selected_path not in paths and safe_path(root, selected_path, ["docs-raw"]).exists():
            raise ContractError("UNSUPPORTED_DOCUMENT_FORMAT", selected_path)
    catalog.register_many([
        {"kind": "raw", "path": path} for path in paths
        if not selected_path or path == selected_path or path.startswith(selected_path.rstrip("/") + "/")
    ])
    candidates = catalog.list_files()
    if target:
        candidates = [target]
    elif selected_path:
        candidates = [row for row in candidates if row["kind"] != "code" and
                      (row["path"] == selected_path or row["path"].startswith(selected_path.rstrip("/") + "/"))]
        if not candidates:
            raise ContractError("SOURCE_MISSING", selected_path)
    elif not include_code:
        candidates = [row for row in candidates if row["kind"] != "code"]
    elif include_code:
        referenced = {row["id"] for row in catalog.list_files(kind="code", referenced=True)}
        candidates = [row for row in candidates if row["kind"] != "code" or row["id"] in referenced]
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
        if reprocess or row.get("processed_exists") is None or bool(row["processed_exists"]) != exists or row.get("processed_hash") != current:
            change = ("deleted" if not exists else "reprocess" if reprocess else
                      "added" if row.get("processed_exists") is None else "modified")
            pending.append({**row, "hash": current, "exists": exists, "change": change,
                            **({"content": data} if keep_content else {})})
            if first:
                break
    return pending


def _clear_build(root):
    path = safe_path(root, ".build")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir()


def scan(root, request):
    root = Path(root)
    reprocess = request.get("reprocess", False)
    if type(reprocess) is not bool:
        raise ContractError("INVALID_REPROCESS", "reprocess must be a boolean")
    with Catalog(root) as catalog:
        selected_source = request.get("source")
        if reprocess:
            registered = catalog.get_file(selected_source) if isinstance(selected_source, str) else None
            if registered is None and isinstance(selected_source, str):
                matches = [row for row in catalog.list_files() if row["path"] == selected_source]
                registered = matches[0] if len(matches) == 1 else None
            if registered is None:
                raise ContractError("REPROCESS_SOURCE_REQUIRED", "Select one explicitly registered source ID or exact path")
            selected_source = registered["id"]
        _clear_build(root)
        pending = observe(root, catalog, selected_source, first=True, keep_content=True, reprocess=reprocess)
        if not pending:
            return {"pending": 0}, "unchanged"
        selected = pending[0]
        catalog.touch_attempt(selected["id"])
        cards = catalog.cards_for(selected["id"])
    source = {key: value for key, value in selected.items() if key != "content"}
    source["code_id" if source["kind"] == "code" else "doc_id"] = source["id"]
    source["source_id"] = source["id"]
    source["source_commit"] = (source_commit(source_path(root, selected), selected["content"])
                               if selected["content"] is not None else None)
    materials = safe_path(root, ".build/materials")
    materials.mkdir()
    gaps = []
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
                parsed = document_parser.parse(root, source, selected["content"], ".build/materials/parsed",
                                               options=request.get("parser"))
                source["parsed"] = parsed
                source["text_ref"] = parsed["text_ref"]
                # Keep the old entry usable without changing the parser's
                # manifest-owned files or its text/locator semantics.
                if suffix != ".txt":
                    (materials / "current.txt").write_bytes(safe_path(root, parsed["text_ref"]).read_bytes())
                gaps.extend(item.get("message", str(item)) if isinstance(item, dict) else str(item)
                            for item in parsed.get("gaps", []))
        except (ValueError, UnicodeError, ImportError, ContractError) as error:
            gaps.append(str(error))
    (root / ".build/cards").mkdir()
    task = {"source": source, "affected_cards": [{"id": card["id"], "path": card["path"],
                                                 "title": card["title"]} for card in cards],
            "cards_dir": ".build/cards", "plan_ref": ".build/plan.md", "gaps": gaps}
    write_json(root / ".build/task.json", task)
    return {**task, "task_ref": ".build/task.json", "pending_at_least": len(pending)}, "prepared"


def _drafts(root, catalog, rules=None, *, concise_only=False):
    directory = safe_path(root, ".build/cards")
    lookup = {row["id"]: row for row in catalog.list_files()}
    return [parse_card(path.read_bytes(), "knowledge/" + path.relative_to(directory).as_posix(), rules,
                       source_lookup=lookup, concise_only=concise_only)
            for path in sorted(directory.rglob("*.md"))] if directory.exists() else []


def _planned_cards(root):
    """Read P2's target list; prose remains the author's editable plan."""
    path = safe_path(root, ".build/plan.md")
    if not path.is_file():
        raise ContractError("PLAN_REQUIRED", "P2 must write plan.md with a cards target list", ".build/plan.md")
    try:
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", path.read_text(encoding="utf-8-sig"), re.S)
        metadata = load_yaml(match.group(1)) if match else None
        if not isinstance(metadata, dict) or not isinstance(metadata.get("cards"), list):
            raise ValueError("Expected YAML frontmatter with cards: [{id, path}], or cards: []")
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
            targets[identity] = reference
            paths.add(reference.casefold())
        return targets
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        raise ContractError("INVALID_PLAN", str(error), ".build/plan.md") from error


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
            parsed = document_parser.parse(root, source, data,
                                           f".build/materials/references/{component}", options=options)
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
        text, _ = source_resources.extract_code_text(data, extractor or "code-utf8:1")
        symbol = reference.get("symbol")
        if symbol or reference.get("selector"):
            from .code_symbols import resolve

            selector = reference.get("selector") or (symbol if isinstance(symbol, dict)
                                                      else {"kind": "function", "name": symbol})
            result = resolve(data, selector, path=source["path"], extractor=extractor)
            if result["status"] != "resolved":
                raise ContractError("CODE_SYMBOL_" + result["status"].upper(), str(symbol or selector), source["path"])
            if "line_start" in reference and (
                reference["line_start"] != result["range"]["start_line"]
                or reference["line_end"] != result["range"]["end_line"]
            ):
                raise ContractError("CODE_RANGE_CHANGED", "Update the symbol's current line range", source["path"])
            return result
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


def _snapshot_reference_check(root, source, reference, snapshot, registry, context):
    """A real retained document snapshot must never be checked against newer bytes."""
    frozen = context.setdefault("frozen", {})
    snapshot_id = snapshot["snapshot_id"]
    if snapshot_id not in frozen:
        frozen[snapshot_id] = source_resources.recover_snapshot(root, snapshot)
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


def check(root, request, rules=None):
    """Fixed checks only; the independent reviewer judges actual knowledge."""
    findings = []
    try:
        planned = None if request.get("formal") else _planned_cards(root)
        catalog = Catalog(root)
    except (ValueError, ContractError, yaml.YAMLError) as error:
        return {"findings": [{"code": getattr(error, "code", "INVALID_CARD"),
                              "path": str(getattr(error, "path", "")), "message": str(error)}]}, "failed"
    with catalog:
        try:
            drafts = (catalog.all_cards() if request.get("formal")
                      else _drafts(root, catalog, rules, concise_only=True))
            deletes = set() if request.get("formal") else set(_deletes(root))
            overlap = deletes & {card["path"] for card in drafts}
            if overlap:
                raise ContractError("WRITE_DELETE_CONFLICT", "A candidate cannot also be deleted", ", ".join(sorted(overlap)))
            staged_sources = {}
            context = {"formal": bool(request.get("formal")), "loaded": {}, "legacy": {}, "data": {}, "descriptors": {}}
            task_path = safe_path(root, ".build/task.json")
            if not request.get("formal") and task_path.is_file():
                task = read_json(task_path)
                source = task["source"]
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
        except (ValueError, OSError, ContractError, yaml.YAMLError) as error:
            return {"findings": [{"code": getattr(error, "code", "INVALID_CARD"), "message": str(error)}]}, "failed"
        if planned is not None:
            actual = {card["id"]: card["path"] for card in drafts}
            for identity in sorted(planned.keys() | actual.keys()):
                expected_path, actual_path = planned.get(identity), actual.get(identity)
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
        snapshots = {row["snapshot_id"]: row for row in catalog.registry.get("snapshots", [])}
    for card in drafts:
        for kind in ("doc", "code"):
            for reference in card[kind + "_ref"]:
                identity = reference[kind + "_id"]
                source = source_lookup.get(identity)
                try:
                    if source is None:
                        raise ContractError("UNKNOWN_SOURCE_ID", identity)
                    if (source["kind"] == "code") != (kind == "code"):
                        raise ContractError("SOURCE_KIND_MISMATCH", identity)
                    snapshot = snapshots.get(reference.get("snapshot_id"), {})
                    if snapshot and snapshot.get("source_id") != identity:
                        raise ContractError("SOURCE_SNAPSHOT_MISMATCH", "The retained snapshot belongs to another source")
                    if kind == "doc" and snapshot.get("source_id") == identity:
                        _snapshot_reference_check(root, source, reference, snapshot, registry, context)
                        continue
                    extractor = (code_extractor(source, snapshot if snapshot.get("source_id") == identity else None)
                                 if kind == "code" else None)
                    _reference_check(root, source, reference, staged_sources.get(identity), extractor=extractor, context=context)
                except (ValueError, OSError, ContractError, subprocess.TimeoutExpired) as error:
                    findings.append({"code": getattr(error, "code", "SOURCE_UNAVAILABLE"),
                                     "path": card["path"], "message": str(error)})
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
    return {"findings": findings, "card_ids": [card["id"] for card in drafts],
            "parsed_sources": context["descriptors"],
            "review_required": True}, "failed" if findings else "passed"


def commit(root, request):
    """Copy the reviewed drafts and refresh metadata; retry the same workspace.

    This deliberately does not call check(), re-hash inputs, or infer whether an
    independent agent reviewed the content. The five-node workflow owns order.
    """
    task_path = safe_path(root, ".build/task.json")
    if not task_path.is_file():
        raise ContractError("TASK_REQUIRED", "Run ingest scan before commit")
    task = read_json(task_path)
    source = task["source"]
    # A previous copy may have stopped before deleting a moved card's old path.
    # Finish the reviewed overlay before reading formal cards into the catalog.
    with Catalog(root, refresh=False) as catalog:
        drafts = _drafts(root, catalog)
        deletes = _deletes(root)
        if request.get("defer"):
            return {"source_id": source["source_id"], "reason": request.get("reason", "Materials are incomplete")}, "deferred"
        if not drafts and not request.get("reason"):
            raise ContractError("NO_CHANGE_REASON_REQUIRED", "Explain the reviewed no-card result")
        for card in drafts:
            destination = safe_path(root, card["path"], ["knowledge"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(destination, card["raw"])
        for reference in deletes:
            safe_path(root, reference, ["knowledge"]).unlink(missing_ok=True)
        catalog.rebuild()
        from .library import build_search

        build_search(catalog)
        result = {"source_id": source["source_id"], "processed_hash": source["hash"],
                  "card_ids": [card["id"] for card in drafts], "deleted": deletes,
                  "reason": request.get("reason", "Reviewed card changes published")}
        write_json(safe_path(root, "artifacts/ingest/latest.json"), result)
        catalog.mark_processed(source["source_id"], source["hash"], source["exists"],
                               source_commit=source.get("source_commit"))
    # Cleanup is last. A failed copy or database operation leaves all drafts.
    try:
        shutil.rmtree(safe_path(root, ".build"))
    except OSError as error:
        result["cleanup_error"] = str(error)
    return result, "completed"
