"""Published knowledge views and live raw operations for the local host."""

import base64
from collections import Counter
from contextlib import closing, contextmanager
import json
from pathlib import PurePosixPath
import posixpath
import sqlite3
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from . import citation_versions, indexing, raw_materials
from .validation import ContractError, canonical_bytes, markdown_structure, safe_path, sha256_bytes, validate_id


CARD_TYPES = {
    "entities": "entity", "flows": "flow", "protocols": "protocol",
    "rules": "rule", "commands": "command", "runbooks": "runbook", "glossaries": "glossary",
}
KINDS = {"card", "document", "code"}
VERSION = 2


def card_detail(card, sources):
    metadata = card["metadata"]
    return {"card_id": card["id"], "path": card["path"], "title": card["title"],
            "body": card["body"], "metadata": metadata, "sources": sources,
            "doc_ref": card["doc_ref"], "code_ref": card["code_ref"],
            "tags": metadata.get("tags", []), "lifecycle": metadata.get("lifecycle", "stable")}


def _card_summary(card):
    metadata = card["metadata"]
    path = PurePosixPath(card["path"])
    category = path.parts[2] if path.parts[1:2] == ("concepts",) and len(path.parts) > 3 else path.parts[1]
    body = card["body"].splitlines()
    summary = metadata.get("summary") or next((line for line in body if line.strip() and not line.startswith("#")), "")
    return {"id": card["id"], "title": card["title"][:160],
            "type": CARD_TYPES.get(category, "other"), "summary": " ".join(summary.split())[:240],
            "tags": [tag[:64] for tag in metadata.get("tags", [])[:16]]}


def _references(card):
    yield from ((item["doc_id"], "document", "doc_ref") for item in card["doc_ref"])
    yield from ((item["code_id"], "code", "code_ref") for item in card["code_ref"])


def _card_links(path, structures, card_ids):
    results = {}
    for link in structures[path]["links"]:
        target = link["target"]
        if not target or link.get("image"):
            continue
        try:
            parsed = urlsplit(target)
        except ValueError:
            continue
        relative = unquote(parsed.path)
        if parsed.scheme or parsed.netloc or parsed.query or relative.startswith("/") or "\\" in relative:
            continue
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), relative)) if relative else path
        if resolved not in card_ids:
            continue
        anchor = unquote(parsed.fragment)
        if anchor and anchor not in structures[resolved]["anchors"]:
            continue
        result = {"target": target, "card_id": card_ids[resolved]}
        if anchor:
            result["anchor"] = anchor
        results[target] = result
    return list(results.values())


def publish(catalog, cards, source_changes, search_weights):
    """Replace the read model inside the existing catalog write transaction."""
    db = catalog.connection
    cards = [card for card in cards if card["metadata"].get("lifecycle") != "draft"]
    summaries = {card["id"]: _card_summary(card) for card in cards}
    files = {item["id"]: item for item in catalog.list_files()}
    for identity, changes in source_changes.items():
        files[identity].update(changes)
    versions = citation_versions.project_index(catalog.registry)
    structures = {card["path"]: markdown_structure(card["body"], strip_frontmatter=False) for card in cards}
    card_ids = {card["path"]: card["id"] for card in cards}
    mtimes = dict(db.execute("SELECT id,mtime_ns FROM cards"))
    edges = set()
    referenced = {"document": set(), "code": set()}
    card_rows = []
    for card in cards:
        identity = card["id"]
        summary = summaries[identity]
        sources = set()
        for source_id, kind, edge_kind in _references(card):
            sources.add(source_id)
            referenced[kind].add(source_id)
            node_id = kind + "/" + source_id if source_id in summaries else source_id
            title = PurePosixPath(files[source_id]["path"]).name[:160]
            edges.add((identity, kind, node_id, title, identity, node_id, edge_kind))
        for relation in card["metadata"].get("relations", []):
            peer = relation.get("target_card_id")
            if relation.get("type") == "related_to" and peer in summaries and peer != identity:
                edges.add((identity, "card", peer, summaries[peer]["title"], identity, peer, "related_to"))
                edges.add((peer, "card", identity, summary["title"], identity, peer, "related_to"))
        detail = card_detail(card, [files[source_id] for source_id in sorted(sources)])
        detail["card_links"] = _card_links(card["path"], structures, card_ids)
        detail["heading_anchors"] = structures[card["path"]]["headings"]
        for peer in {link["card_id"] for link in detail["card_links"]} - {identity}:
            edges.add((identity, "card", peer, summaries[peer]["title"], identity, peer, "card_link"))
            edges.add((peer, "card", identity, summary["title"], identity, peer, "card_link"))
        for kind in ("doc", "code"):
            detail[kind + "_ref"] = [citation_versions.project_reference(card, kind, item, versions)
                                    for item in detail[kind + "_ref"]]
        card_rows.append((identity, summary["title"], summary["type"], summary["summary"],
                          json.dumps(summary["tags"], ensure_ascii=False),
                          card["path"], detail["lifecycle"], json.dumps(detail, ensure_ascii=False)))
    counts = Counter(card["type"] for card in summaries.values())
    recent = sorted(summaries, key=lambda identity: (-mtimes[identity], identity))[:10]
    overview = {"view_revision": uuid4().hex, "card_count": len(cards),
                "document_count": len(referenced["document"]), "code_count": len(referenced["code"]),
                "types": [{"type": category, "count": count} for category, count in sorted(counts.items())],
                "recent_cards": [{key: summaries[identity][key] for key in ("id", "title", "type")}
                                 for identity in recent]}
    with catalog.transaction():
        for table in ("panel_state", "panel_cards", "panel_tags", "panel_terms", "panel_neighbors"):
            db.execute("DROP TABLE IF EXISTS " + table)
        db.execute("CREATE TABLE panel_state(version INTEGER NOT NULL, overview TEXT NOT NULL)")
        db.execute("""CREATE TABLE panel_cards(
            id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL,
            summary TEXT NOT NULL, tags TEXT NOT NULL, path TEXT NOT NULL,
            lifecycle TEXT NOT NULL, detail TEXT NOT NULL)""")
        db.execute("CREATE INDEX panel_card_type ON panel_cards(type,id)")
        db.execute("CREATE TABLE panel_tags(card_id TEXT,tag TEXT,PRIMARY KEY(card_id,tag)) WITHOUT ROWID")
        db.execute("""CREATE TABLE panel_terms(
            card_id TEXT, token TEXT, score INTEGER NOT NULL, PRIMARY KEY(card_id,token)) WITHOUT ROWID""")
        db.execute("CREATE INDEX panel_token ON panel_terms(token,card_id)")
        db.execute("""CREATE TABLE panel_neighbors(
            root_id TEXT, kind TEXT, id TEXT, title TEXT, source TEXT, target TEXT, edge_kind TEXT,
            PRIMARY KEY(root_id,kind,id,edge_kind,source,target)) WITHOUT ROWID""")
        db.executemany("INSERT INTO panel_cards VALUES(?,?,?,?,?,?,?,?)", card_rows)
        db.executemany("INSERT OR IGNORE INTO panel_tags VALUES(?,?)",
                       ((card["id"], tag) for card in cards for tag in card["metadata"].get("tags", [])))
        db.execute("""INSERT INTO panel_terms
            SELECT s.card_id,s.token,SUM(CASE s.field WHEN 'title' THEN ? WHEN 'tags' THEN ? ELSE ? END)
            FROM search_terms s JOIN panel_cards c ON c.id=s.card_id GROUP BY s.card_id,s.token
        """, (search_weights["title"], search_weights["tags"], search_weights["body"]))
        db.executemany("INSERT INTO panel_neighbors VALUES(?,?,?,?,?,?,?)", edges)
        db.execute("INSERT INTO panel_state VALUES(?,?)", (VERSION, json.dumps(overview, ensure_ascii=False)))


def _is_sqlite_contention(error):
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        # Extended SQLite result codes store the primary code in their low byte.
        return (code & 0xff) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    # Python 3.10 does not expose SQLite result codes on exceptions.
    message = str(error)
    return message == "database is locked" or message.startswith((
        "database table is locked", "database schema is locked",
    ))


@contextmanager
def _published(root, expected=None):
    path = safe_path(root, "artifacts/knowledge.sqlite", ["artifacts"])
    try:
        with closing(sqlite3.connect(indexing.sqlite_readonly_uri(path, immutable=False), uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")
            state = db.execute("SELECT version,overview FROM panel_state").fetchone()
            if state is None or state["version"] != VERSION:
                raise ContractError("PANEL_VIEW_UNAVAILABLE", "Build the panel view with maintain reindex")
            overview = json.loads(state["overview"])
            if expected is not None and expected != overview["view_revision"]:
                raise ContractError("PANEL_REVISION_MISMATCH", "The published view changed. Refresh and retry.")
            yield db, overview
    except (sqlite3.Error, json.JSONDecodeError) as error:
        if isinstance(error, sqlite3.OperationalError) and _is_sqlite_contention(error):
            raise ContractError("PANEL_VIEW_BUSY", "The published knowledge view is temporarily busy. Retry shortly.") from error
        raise ContractError("PANEL_VIEW_UNAVAILABLE", "Published panel view is unavailable") from error


def read_card(root, card_id, revision):
    with _published(root, revision) as (db, overview):
        row = db.execute("SELECT detail FROM panel_cards WHERE id=?", (card_id,)).fetchone()
        if row is None:
            raise ContractError("CARD_NOT_FOUND", str(card_id))
        return {**json.loads(row["detail"]), "view_revision": overview["view_revision"]}


def _check(request, keys):
    if set(request) - set(keys):
        raise ContractError("PANEL_INVALID_REQUEST", "Unsupported panel parameters")


def _text(request, key, length, default=""):
    value = request.get(key, default)
    if not isinstance(value, str) or len(value) > length or "\x00" in value:
        raise ContractError("PANEL_INVALID_REQUEST", "Invalid " + key)
    return value


def _page(request, scope, maximum, width=1):
    limit = request.get("limit", min(30, maximum))
    if type(limit) is not int or not 1 <= limit <= maximum:
        raise ContractError("PANEL_INVALID_REQUEST", f"limit must be 1..{maximum}")
    scope = sha256_bytes(canonical_bytes(scope))
    token = request.get("cursor")
    if token is None:
        return limit, ("",) * width, scope
    if not isinstance(token, str) or len(token) > 4096:
        raise ContractError("PANEL_CURSOR_INVALID", "Invalid cursor")
    try:
        saved, key = json.loads(base64.b64decode(token, altchars=b"-_", validate=True))
    except (ValueError, TypeError) as error:
        raise ContractError("PANEL_CURSOR_INVALID", "Invalid cursor") from error
    if (saved != scope or not isinstance(key, list) or len(key) != width
            or any(not isinstance(value, str) or "\x00" in value for value in key)):
        raise ContractError("PANEL_CURSOR_INVALID", "Cursor is from another view or filter")
    return limit, tuple(key), scope


def _next(rows, limit, scope, key):
    if len(rows) <= limit:
        return None
    return base64.urlsafe_b64encode(canonical_bytes([scope, key(rows[limit - 1])])).decode("ascii")


def _has_terms(groups, params):
    predicates = []
    for group in groups:
        marks = ",".join("?" for _ in group)
        predicates.append(f"EXISTS(SELECT 1 FROM panel_terms t WHERE t.card_id=c.id AND t.token IN ({marks}))")
        params.extend(sorted(group))
    return predicates


def _cards(db, revision, request):
    _check(request, ("view_revision", "query", "type", "tag", "cursor", "limit"))
    query = _text(request, "query", 160).strip()
    category = _text(request, "type", 40)
    tag = _text(request, "tag", 160)
    limit, (after,), scope = _page(request, ["cards", revision, query, category, tag], 100)
    predicates, params = ["c.id > ?"], [after]
    if category:
        predicates.append("c.type = ?")
        params.append(category)
    if tag:
        predicates.append("EXISTS(SELECT 1 FROM panel_tags t WHERE t.card_id=c.id AND t.tag=?)")
        params.append(tag)
    if query:
        groups = indexing.term_groups(query)
        if not groups:
            raise ContractError("QUERY_REQUIRED", "Pass a searchable query")
        predicates.extend(_has_terms(groups, params))
    rows = db.execute("SELECT id,title,type,summary,tags FROM panel_cards c WHERE "
                      + " AND ".join(predicates) + " ORDER BY id LIMIT ?", (*params, limit + 1)).fetchall()
    return {"view_revision": revision, "items": [{**dict(row), "tags": json.loads(row["tags"])} for row in rows[:limit]],
            "next_cursor": _next(rows, limit, scope, lambda row: [row["id"]])}


def _search(db, revision, request):
    _check(request, ("query", "tags", "top_k", "view_revision"))
    query = _text(request, "query", 160).strip()
    groups = indexing.term_groups(query)
    if not groups:
        raise ContractError("QUERY_REQUIRED", "Pass a searchable query")
    tags = request.get("tags", [])
    if (not isinstance(tags, list) or len(tags) > 16
            or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 160 for tag in tags)):
        raise ContractError("INVALID_QUERY_TAGS", "Use up to 16 nonempty tag strings")
    top_k = request.get("top_k", 10)
    if type(top_k) is not int or not 1 <= top_k <= 100:
        raise ContractError("INVALID_TOP_K", "top_k must be 1..100")
    terms = sorted(set().union(*groups))
    marks = ",".join("?" for _ in terms)
    predicates, params = ["c.lifecycle != 'deprecated'"], list(terms)
    predicates.extend(_has_terms(groups, params))
    for tag in sorted(set(tags)):
        predicates.append("EXISTS(SELECT 1 FROM panel_tags t WHERE t.card_id=c.id AND t.tag=?)")
        params.append(tag)
    rows = db.execute(f"""
        WITH candidates AS (
            SELECT card_id,SUM(score) AS score FROM panel_terms WHERE token IN ({marks}) GROUP BY card_id
        )
        SELECT c.id AS card_id,c.title,c.path,c.tags,c.lifecycle,s.score
        FROM candidates s JOIN panel_cards c ON c.id=s.card_id WHERE
    """ + " AND ".join(predicates) + " ORDER BY s.score DESC,c.id LIMIT ?", (*params, top_k + 1)).fetchall()
    return {"view_revision": revision,
            "matches": [{**dict(row), "tags": json.loads(row["tags"])} for row in rows[:top_k]],
            "truncated": len(rows) > top_k}


def _graph(db, revision, request):
    _check(request, ("view_revision", "card_id", "kinds", "cursor", "limit"))
    identity = validate_id(request.get("card_id"))
    kinds = request.get("kinds", sorted(KINDS))
    if not isinstance(kinds, list) or any(not isinstance(kind, str) or kind not in KINDS for kind in kinds):
        raise ContractError("PANEL_INVALID_REQUEST", "kinds must contain card, document or code")
    kinds = sorted(set(kinds))
    limit, after, scope = _page(request, ["graph", revision, identity, kinds], 50, width=5)
    card = db.execute("SELECT id,title FROM panel_cards WHERE id=?", (identity,)).fetchone()
    if card is None:
        raise ContractError("CARD_NOT_FOUND", identity)
    key = ("kind", "id", "edge_kind", "source", "target")
    rows = []
    for kind in kinds:
        if kind < after[0]:
            continue
        last = after[1:] if kind == after[0] else ("",) * 4
        rows.extend(db.execute("""
            SELECT kind,id,title,source,target,edge_kind FROM panel_neighbors
            WHERE root_id=? AND kind=? AND (id,edge_kind,source,target) > (?,?,?,?)
            ORDER BY id,edge_kind,source,target LIMIT ?
        """, (identity, kind, *last, limit + 1 - len(rows))))
        if len(rows) > limit:
            break
    nodes = {identity: {**dict(card), "kind": "card"}}
    edges = []
    for row in rows[:limit]:
        nodes[row["id"]] = {"id": row["id"], "title": row["title"], "kind": row["kind"]}
        if "/" in row["id"]:
            nodes[row["id"]]["ref_id"] = row["id"].split("/", 1)[1]
        edges.append({"source": row["source"], "target": row["target"], "kind": row["edge_kind"]})
    return {"view_revision": revision, "nodes": list(nodes.values()), "edges": edges,
            "next_cursor": _next(rows, limit, scope, lambda row: [row[column] for column in key])}


def run(root, action, request):
    if action == "raw-list":
        _check(request, ("path", "cursor", "limit"))
        path = _text(request, "path", 1024)
        limit, (after,), scope = _page(request, [action, path], 100)
        rows = raw_materials.list_entries(root, path, after, limit + 1)
        return {"path": path, "items": rows[:limit],
                "next_cursor": _next(rows, limit, scope, lambda row: [row["name"]])}, "listed"
    if action == "raw-path":
        _check(request, ("path",))
        return raw_materials.file_path(root, _text(request, "path", 1024)), "resolved"
    if action == "raw-save":
        _check(request, ("path", "staged_path", "expected_size", "expected_sha256"))
        return raw_materials.save(root, request), "saved"
    if action == "read":
        _check(request, ("card_id", "view_revision"))
        return read_card(root, validate_id(request.get("card_id")), request.get("view_revision")), "read"
    if action not in {"overview", "cards", "graph", "search"}:
        raise ContractError("INVALID_ACTION", "Use panel overview, cards, graph, search, read, raw-list, raw-save or raw-path")
    with _published(root, request.get("view_revision")) as (db, overview):
        if action == "overview":
            _check(request, ("view_revision",))
            return overview, "listed"
        revision = overview["view_revision"]
        if action == "cards":
            return _cards(db, revision, request), "listed"
        if action == "search":
            return _search(db, revision, request), "searched"
        return _graph(db, revision, request), "listed"
