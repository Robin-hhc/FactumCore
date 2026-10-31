"""Direct catalog search, source lookup and serial patrol commands."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from uuid import uuid4

import yaml

from .catalog import Catalog
from . import indexing, ingest, source_resources
from .validation import ContractError, safe_path, validate_id


SEARCH_VERSION = "card-v1"
SEARCH_COLUMNS = [("token", 1), ("card_id", 2), ("field", 3)]
SEARCH_WEIGHTS = {"title": 8, "tags": 5, "body": 1}


def _signature(catalog):
    return ingest.sha(json.dumps([tuple(row) for row in catalog.connection.execute(
        "SELECT id,sha256 FROM cards ORDER BY id")], separators=(",", ":")).encode())


def search_stale(catalog):
    catalog.connection.execute("CREATE TABLE IF NOT EXISTS search_state(key TEXT PRIMARY KEY,value TEXT)")
    state = dict(catalog.connection.execute("SELECT key,value FROM search_state"))
    columns = [(row["name"], row["pk"]) for row in catalog.connection.execute("PRAGMA table_info(search_terms)")]
    return (state.get("format") != SEARCH_VERSION or columns != SEARCH_COLUMNS
            or state.get("cards") != _signature(catalog))


def _search_fields(card):
    metadata = card["metadata"]
    body = [card["body"]]
    if card["legacy"]:
        # Retain old declared lookup terms, without interpreting their Claims
        # as search qualifications or multiplying scores by Claim count.
        body.extend([metadata.get("summary", ""), *metadata.get("aliases", []),
                     *metadata.get("search_terms", [])])
        for claim in metadata.get("claims", []):
            body.extend(claim.get("search_terms", []))
    return {"title": card["title"], "tags": " ".join(metadata.get("tags", [])), "body": "\n".join(body)}


def build_search(catalog):
    """Rebuild only derived search tables, atomically, including old formats."""
    cards = catalog.all_cards()
    with catalog.transaction():
        catalog.connection.execute("CREATE TABLE IF NOT EXISTS search_state(key TEXT PRIMARY KEY,value TEXT)")
        catalog.connection.execute("DROP TABLE IF EXISTS search_terms")
        catalog.connection.execute("""CREATE TABLE search_terms(
            token TEXT,card_id TEXT,field TEXT,
            PRIMARY KEY(token,card_id,field))""")
        catalog.connection.execute("CREATE INDEX search_token ON search_terms(token)")
        rows = []
        for card in cards:
            for field, text in _search_fields(card).items():
                rows.extend((term, card["id"], field) for term in indexing.lexical(text))
        catalog.connection.executemany("INSERT INTO search_terms VALUES(?,?,?)", rows)
        catalog.connection.execute("INSERT OR REPLACE INTO search_state VALUES('cards',?)", (_signature(catalog),))
        catalog.connection.execute("INSERT OR REPLACE INTO search_state VALUES('format',?)", (SEARCH_VERSION,))
    return {"cards": len(cards), "terms": len(rows)}


def _query_options(request, *, read):
    if "purpose" in request or "context" in request:
        raise ContractError("QUERY_PARAMETERS_REMOVED",
                            "purpose/context are removed; search by query and optional tags, then read the card's conditions")
    allowed = {"card_id"} if read else {"query", "tags", "top_k", "include_deprecated"}
    if set(request) - allowed:
        raise ContractError("INVALID_QUERY_REQUEST", "Unsupported fields: " + ", ".join(sorted(set(request) - allowed)))
    if read:
        validate_id(request.get("card_id"))
        return
    if not isinstance(request.get("query"), str) or not request["query"].strip():
        raise ContractError("QUERY_REQUIRED", "Pass a nonempty query")
    tags = request.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise ContractError("INVALID_QUERY_TAGS", "tags must be an array of nonempty strings")
    top_k = request.get("top_k", 10)
    if type(top_k) is not int or not 1 <= top_k <= 100:
        raise ContractError("INVALID_TOP_K", "top_k must be 1..100")
    if type(request.get("include_deprecated", False)) is not bool:
        raise ContractError("INVALID_INCLUDE_DEPRECATED", "include_deprecated must be a boolean")


def query(root, request, *, read=False):
    _query_options(request, read=read)
    with Catalog(root) as catalog:
        if read:
            card = catalog.get_card(request.get("card_id"))
            if card is None:
                raise ContractError("CARD_NOT_FOUND", str(request.get("card_id")))
            return {"card_id": card["id"], "path": card["path"], "title": card["title"],
                    "body": card["body"], "metadata": card["metadata"],
                    "sources": catalog.files_for(card["id"]),
                    "doc_ref": card["doc_ref"], "code_ref": card["code_ref"],
                    "tags": card["metadata"].get("tags", []),
                    "lifecycle": card["metadata"].get("lifecycle", "stable")}, "read"
        text = request.get("query", "")
        groups = indexing.term_groups(text)
        if not groups:
            raise ContractError("QUERY_REQUIRED", "Pass a nonempty query")
        if search_stale(catalog):
            build_search(catalog)
        terms = sorted(set().union(*groups))
        placeholders = ",".join("?" for _ in terms)
        rows = list(catalog.connection.execute(
            f"SELECT token,card_id,field FROM search_terms WHERE token IN ({placeholders})", terms))
        hits = {}
        for row in rows:
            hits.setdefault(row["card_id"], []).append(dict(row))
        matches = []
        for identity, found in hits.items():
            card = catalog.get_card(identity)
            tags = set(card["metadata"].get("tags", []))
            if not set(request.get("tags", [])).issubset(tags):
                continue
            lifecycle = card["metadata"].get("lifecycle", "stable")
            if lifecycle == "draft" or lifecycle == "deprecated" and not request.get("include_deprecated", False):
                continue
            present = {row["token"] for row in found}
            if not all(group & present for group in groups):
                continue
            matches.append({"card_id": identity, "title": card["title"], "path": card["path"],
                            "tags": card["metadata"].get("tags", []), "lifecycle": lifecycle,
                            "score": sum(SEARCH_WEIGHTS[row["field"]] for row in found)})
        top_k = request.get("top_k", 10)
        matches.sort(key=lambda item: (-item["score"], item["card_id"]))
        result = {"matches": matches[:top_k],
                  "truncated": len(matches) > top_k,
                  "report_ref": f"artifacts/query/{uuid4().hex}.json"}
        ingest.write_json(safe_path(root, result["report_ref"]), result)
        return result, "searched"


def sources(root, action, request):
    with Catalog(root) as catalog:
        if action == "register":
            kind = request.get("kind", "raw")
            path = request.get("path", request.get("source_path"))
            candidate = {"kind": "raw" if kind == "doc" else kind, "path": path,
                         "repo": request.get("repo", request.get("repo_id", ""))}
            actual = ingest.source_path(root, candidate)
            if not actual.is_file():
                raise ContractError("SOURCE_MISSING", str(path))
            row = catalog.register(kind, path, candidate["repo"], request.get("source_id"),
                                   encoding=request.get("encoding"))
            return {"source": row}, "registered"
        if action == "list":
            if request.get("card_id"):
                return {"files": catalog.files_for(request["card_id"])}, "listed"
            identity = request.get("source_id", request.get("doc_id", request.get("code_id")))
            if identity:
                return {"source": catalog.get_file(identity),
                        "cards": [{"id": row["id"], "path": row["path"], "title": row["title"]}
                                  for row in catalog.cards_for(identity)]}, "listed"
            return {"files": catalog.list_files(request.get("kind"), request.get("referenced", False))}, "listed"
        if action in {"resolve", "resolve-source"}:
            identity = request.get("source_id", request.get("doc_id", request.get("code_id")))
            source = catalog.get_file(identity)
            if source is None:
                raise ContractError("UNKNOWN_SOURCE_ID", str(identity))
            data, commit = ingest.old_source(root, source, commit=request.get("commit"), expected_hash=request.get("hash"))
            suffix = Path(source["path"]).suffix
            reference = f"artifacts/sources/{identity}-{ingest.sha(data)}{suffix}"
            target = safe_path(root, reference, ["artifacts/sources"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            result = {"source_id": identity, "original_ref": reference, "hash": ingest.sha(data), "commit": commit}
            try:
                text = (source_resources.extract_code_text(data, ingest.code_extractor(source))[0]
                        if source["kind"] == "code" else source_resources.extract_document(data, suffix)[0])
                text_ref = reference + ".txt"
                safe_path(root, text_ref).write_text(text, encoding="utf-8")
                result["text_ref"] = text_ref
            except (ValueError, ImportError, ContractError) as error:
                result["gap"] = str(error)
            return result, "resolved"
        if action == "configure":
            path = request.get("path")
            source_resources._dbox_location(root, path)
            config = safe_path(root, source_resources.DBOX_CONFIG)
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(yaml.safe_dump({"schema_version": "1.0", "path": path}, sort_keys=False), encoding="utf-8")
            return {"path": source_resources.DBOX_CONFIG, "configured": True}, "configured"
    raise ContractError("INVALID_ACTION", "Use source register, list, resolve or configure")


def patrol(root, action, request):
    if action == "sync":
        sync = request.get("sync")
        if sync:
            if not isinstance(sync, dict) or not isinstance(sync.get("argv"), list) or not sync["argv"]:
                raise ContractError("INVALID_SYNC", "sync requires explicit argv and cwd")
            if not all(isinstance(word, str) for word in sync["argv"]) or not isinstance(sync.get("cwd"), str):
                raise ContractError("INVALID_SYNC", "sync requires explicit argv and cwd")
            result = subprocess.run(sync["argv"], cwd=sync["cwd"], capture_output=True, encoding="utf-8",
                                    errors="replace", timeout=sync.get("timeout_seconds", 600))
            if result.returncode:
                raise ContractError("SYNC_FAILED", result.stderr or result.stdout)
        return {"synchronized": bool(sync)}, "synced"
    with Catalog(root) as catalog:
        if action == "plan":
            pending = ingest.observe(root, catalog, include_code=True, first=True)
            if pending:
                selected = pending[0]
                return {"next_file": {"source_id": selected["id"], "kind": selected["kind"], "path": selected["path"]},
                        "pending_at_least": len(pending)}, "needs_ingest"
            if search_stale(catalog):
                return {"pending": 0}, "needs_reindex"
            return {"pending": 0}, "unchanged"
        if action == "reindex":
            catalog.rebuild()
            return build_search(catalog), "reindexed"
        if action == "complete":
            pending = ingest.observe(root, catalog, include_code=True)
            result = {"remaining": len(pending), "completed_at": datetime.now(timezone.utc).isoformat()}
            ingest.write_json(safe_path(root, "artifacts/patrol/latest.json"), result)
            return result, "completed"
    raise ContractError("INVALID_ACTION", "Use patrol sync, plan, reindex or complete")


def audit(root):
    gaps = []
    with Catalog(root) as catalog:
        for source in catalog.list_files(referenced=True):
            try:
                path = ingest.source_path(root, source)
                if not path.is_file():
                    gaps.append({"source_id": source["id"], "code": "SOURCE_MISSING", "path": source["path"]})
            except (ValueError, OSError, ContractError) as error:
                gaps.append({"source_id": source["id"], "code": getattr(error, "code", "SOURCE_UNAVAILABLE"),
                             "message": str(error)})
    return {"findings": gaps}, "failed" if gaps else "passed"
