"""Published knowledge views and live raw operations for the local host."""

import base64
from collections import defaultdict
from contextlib import ExitStack, closing, contextmanager
import json
from pathlib import PurePosixPath
import posixpath
import sqlite3
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from . import citation_versions, indexing, intake, raw_materials
from .validation import ContractError, canonical_bytes, markdown_structure, safe_path, sha256_bytes, validate_id


CARD_TYPES = {
    "entities": "entity", "flows": "flow", "protocols": "protocol",
    "rules": "rule", "commands": "command", "runbooks": "runbook", "glossaries": "glossary",
}
KINDS = {"card", "document", "code"}
VERSION = 3
GRAPH_MAX_NODES = 4000
GRAPH_MAX_EDGES = 15000
GRAPH_MAX_BYTES = 4 * 1024 * 1024


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


def _link_targets(path, structure):
    for link in structure["links"]:
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
        yield target, resolved, unquote(parsed.fragment)


def _related_cards(card):
    return {item["target_card_id"] for item in card["metadata"].get("relations", [])
            if item.get("type") == "related_to" and item.get("target_card_id") != card["id"]}


_PUBLISHED_TABLES = (
    "panel_state", "panel_cards", "panel_tags", "panel_terms", "panel_neighbors", "panel_graph_nodes",
    "panel_graph_edges", "panel_card_inputs", "panel_source_inputs", "panel_registry_input", "panel_dependencies",
)


def _index_ready(db):
    objects = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
    if not {*_PUBLISHED_TABLES, "panel_neighbors_source"}.issubset(objects):
        return False
    version = db.execute("SELECT version FROM panel_state").fetchone()
    return version is not None and version[0] == VERSION


def _create_index(db):
    for table in _PUBLISHED_TABLES:
        db.execute("DROP TABLE IF EXISTS " + table)
    statements = (
        "CREATE TABLE panel_state(version INTEGER NOT NULL, overview TEXT NOT NULL)",
        """CREATE TABLE panel_cards(
            id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL,
            summary TEXT NOT NULL, tags TEXT NOT NULL, path TEXT NOT NULL,
            lifecycle TEXT NOT NULL, detail TEXT NOT NULL)""",
        "CREATE INDEX panel_card_type ON panel_cards(type,id)",
        "CREATE TABLE panel_tags(card_id TEXT,tag TEXT,PRIMARY KEY(card_id,tag)) WITHOUT ROWID",
        """CREATE TABLE panel_terms(
            card_id TEXT, token TEXT, score INTEGER NOT NULL, PRIMARY KEY(card_id,token)) WITHOUT ROWID""",
        "CREATE INDEX panel_token ON panel_terms(token,card_id)",
        """CREATE TABLE panel_neighbors(
            root_id TEXT, kind TEXT, id TEXT, title TEXT, source TEXT, target TEXT, edge_kind TEXT,
            PRIMARY KEY(root_id,kind,id,edge_kind,source,target)) WITHOUT ROWID""",
        "CREATE INDEX panel_neighbors_source ON panel_neighbors(source)",
        """CREATE TABLE panel_graph_nodes(
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, ref_id TEXT NOT NULL, title TEXT NOT NULL,
            path TEXT NOT NULL) WITHOUT ROWID""",
        """CREATE TABLE panel_graph_edges(
            source TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL,
            PRIMARY KEY(source,target,kind)) WITHOUT ROWID""",
        "CREATE INDEX panel_graph_incoming ON panel_graph_edges(target,source,kind)",
        """CREATE TABLE panel_card_inputs(
            id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL, sha256 TEXT NOT NULL, mtime_ns INTEGER NOT NULL,
            title TEXT NOT NULL, visible INTEGER NOT NULL, anchors TEXT NOT NULL)""",
        "CREATE INDEX panel_recent_cards ON panel_card_inputs(visible,mtime_ns DESC,id)",
        "CREATE TABLE panel_source_inputs(id TEXT PRIMARY KEY, sha256 TEXT NOT NULL)",
        "CREATE TABLE panel_registry_input(digest TEXT NOT NULL)",
        """CREATE TABLE panel_dependencies(
            kind TEXT, target TEXT, card_id TEXT, PRIMARY KEY(kind,target,card_id)) WITHOUT ROWID""",
        "CREATE INDEX panel_dependency_card ON panel_dependencies(card_id)",
    )
    for statement in statements:
        db.execute(statement)


def _card_changes(db):
    return {row["id"]: row for row in db.execute("""
        SELECT c.id,c.path,c.sha256,c.mtime_ns,i.path AS previous_path
        FROM cards c LEFT JOIN panel_card_inputs i ON c.id=i.id
        WHERE i.path IS NOT c.path OR i.sha256 IS NOT c.sha256 OR i.mtime_ns IS NOT c.mtime_ns
        UNION ALL
        SELECT i.id,NULL,NULL,NULL,i.path FROM panel_card_inputs i
        WHERE NOT EXISTS (SELECT 1 FROM cards c WHERE c.id=i.id)
    """)}


def _registry_digest(db):
    row = db.execute("SELECT digest FROM panel_registry_input").fetchone()
    return row[0] if row else None


def stale(catalog):
    db = catalog.connection
    return (not _index_ready(db) or _registry_digest(db) != catalog.registry_digest or bool(_card_changes(db)))


def _source_changes(catalog, overrides):
    db = catalog.connection
    if not overrides and _registry_digest(db) == catalog.registry_digest:
        return set(), {}
    files = {file["id"]: file for file in catalog.list_files()}
    for identity, values in overrides.items():
        files[identity].update(values)
    snapshots = defaultdict(list)
    for snapshot in catalog.registry.get("snapshots", []):
        snapshots[snapshot["source_id"]].append(snapshot)
    inputs = {identity: sha256_bytes(canonical_bytes([file, snapshots[identity]]))
              for identity, file in files.items()}
    indexed = dict(db.execute("SELECT id,sha256 FROM panel_source_inputs"))
    changed = {identity for identity in inputs.keys() | indexed.keys() if inputs.get(identity) != indexed.get(identity)}
    db.executemany("DELETE FROM panel_source_inputs WHERE id=?", ((identity,) for identity in changed - inputs.keys()))
    db.executemany("INSERT OR REPLACE INTO panel_source_inputs VALUES(?,?)",
                   ((identity, inputs[identity]) for identity in changed & inputs.keys()))
    db.execute("DELETE FROM panel_registry_input")
    if not overrides:
        db.execute("INSERT INTO panel_registry_input VALUES(?)", (catalog.registry_digest,))
    return changed, files


def _matching(db, statement, values):
    values = sorted(values)
    # Keep batches below the SQLite variable limit on every supported Python.
    for offset in range(0, len(values), 400):
        batch = values[offset:offset + 400]
        yield from db.execute(statement.format(",".join("?" for _ in batch)), batch)


def _dependents(db, changes, sources):
    paths = {row[column] for row in changes.values() for column in ("path", "previous_path") if row[column]}
    related = {row[0] for row in _matching(db, """
        SELECT card_id FROM panel_dependencies WHERE kind='path' AND target IN ({})
    """, paths)}
    related.update(row[0] for row in _matching(db, """
        SELECT card_id FROM panel_dependencies WHERE kind='relation' AND target IN ({})
    """, changes))
    # Legacy graph IDs are disambiguated when a source ID is also a card ID.
    related.update(row[0] for row in _matching(db, "SELECT card_id FROM card_files WHERE file_id IN ({})",
                                               sources | changes.keys()))
    return related


def _visible(card):
    return card is not None and card["metadata"].get("lifecycle") != "draft"


def _link_index(db, paths, identities, full):
    columns = "SELECT id,path,title,anchors FROM panel_card_inputs WHERE visible=1"
    rows = (db.execute(columns) if full else [
        *_matching(db, columns + " AND path IN ({})", paths),
        *_matching(db, columns + " AND id IN ({})", identities),
    ])
    by_path, titles = {}, {}
    for row in rows:
        by_path[row["path"]] = (row["id"], set(json.loads(row["anchors"])))
        titles[row["id"]] = row["title"]
    return by_path, titles


def _forget_card(db, identity):
    typed = "card/" + identity
    old_targets = {row[0] for row in db.execute("""
        SELECT target FROM panel_graph_edges WHERE source=? AND kind IN ('doc_ref','code_ref')
    """, (typed,))}
    db.execute("DELETE FROM panel_graph_edges WHERE source=?", (typed,))
    db.execute("DELETE FROM panel_graph_nodes WHERE id=?", (typed,))
    db.execute("DELETE FROM panel_neighbors WHERE source=?", (identity,))
    db.execute("DELETE FROM panel_dependencies WHERE card_id=?", (identity,))
    db.execute("DELETE FROM panel_cards WHERE id=?", (identity,))
    return old_targets


def _write_card(db, card, structure, links, graph_targets, files, versions):
    identity, path = card["id"], card["path"]
    summary = _card_summary(card)
    sources = {source_id for source_id, _, _ in _references(card)}
    detail = card_detail(card, [files[source_id] for source_id in sorted(sources)])
    by_path, titles = graph_targets
    resolved = {}
    for target, destination, anchor in links:
        found = by_path.get(destination)
        if found and (not anchor or anchor in found[1]):
            resolved[target] = {"target": target, "card_id": found[0]}
            if anchor:
                resolved[target]["anchor"] = anchor
    detail["card_links"] = list(resolved.values())
    detail["heading_anchors"] = structure["headings"]
    for kind in ("doc", "code"):
        detail[kind + "_ref"] = [citation_versions.project_reference(card, kind, item, versions)
                                for item in detail[kind + "_ref"]]
    db.execute("INSERT INTO panel_cards VALUES(?,?,?,?,?,?,?,?)",
               (identity, summary["title"], summary["type"], summary["summary"],
                json.dumps(summary["tags"], ensure_ascii=False), path, detail["lifecycle"],
                json.dumps(detail, ensure_ascii=False)))
    db.execute("INSERT INTO panel_graph_nodes VALUES(?,?,?,?,?)",
               ("card/" + identity, "card", identity, summary["title"], path))
    relations = _related_cards(card)
    dependencies = {("path", destination, identity) for _, destination, _ in links}
    dependencies.update(("relation", peer, identity) for peer in relations)
    db.executemany("INSERT INTO panel_dependencies VALUES(?,?,?)", dependencies)
    neighbors, edges = set(), set()
    for source_id, kind, edge in _references(card):
        source_path = files[source_id]["path"]
        title = PurePosixPath(source_path).name[:160]
        typed = kind + "/" + source_id
        legacy = typed if source_id in titles else source_id
        neighbors.add((identity, kind, legacy, title, identity, legacy, edge))
        edges.add(("card/" + identity, typed, edge))
        db.execute("""
            INSERT INTO panel_graph_nodes VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,path=excluded.path WHERE title IS NOT excluded.title OR path IS NOT excluded.path
        """, (typed, kind, source_id, title, source_path))
    card_links = {link["card_id"] for link in resolved.values()} - {identity}
    for peers, edge in ((relations & titles.keys(), "related_to"), (card_links, "card_link")):
        for peer in peers:
            neighbors.add((identity, "card", peer, titles[peer], identity, peer, edge))
            neighbors.add((peer, "card", identity, summary["title"], identity, peer, edge))
            edges.add(("card/" + identity, "card/" + peer, edge))
    db.executemany("INSERT INTO panel_neighbors VALUES(?,?,?,?,?,?,?)", neighbors)
    db.executemany("INSERT INTO panel_graph_edges VALUES(?,?,?)", edges)


def _write_terms(db, card, weights):
    identity = card["id"]
    db.executemany("INSERT OR IGNORE INTO panel_tags VALUES(?,?)",
                   ((identity, tag) for tag in card["metadata"].get("tags", [])))
    db.execute("""
        INSERT INTO panel_terms
        SELECT card_id,token,SUM(CASE field WHEN 'title' THEN ? WHEN 'tags' THEN ? ELSE ? END)
        FROM search_terms WHERE card_id=? GROUP BY card_id,token
    """, (weights["title"], weights["tags"], weights["body"], identity))


def _publish_overview(db):
    types = [dict(row) for row in db.execute("SELECT type,COUNT(*) AS count FROM panel_cards GROUP BY type ORDER BY type")]
    sources = dict(db.execute("SELECT kind,COUNT(*) FROM panel_graph_nodes WHERE kind!='card' GROUP BY kind"))
    recent = [dict(row) for row in db.execute("""
        SELECT c.id,c.title,c.type FROM panel_card_inputs i JOIN panel_cards c ON i.id=c.id
        WHERE i.visible=1 ORDER BY i.mtime_ns DESC,i.id LIMIT 10
    """)]
    overview = {"view_revision": uuid4().hex, "card_count": sum(item["count"] for item in types),
                "document_count": sources.get("document", 0), "code_count": sources.get("code", 0),
                "types": types, "recent_cards": recent}
    db.execute("DELETE FROM panel_state")
    db.execute("INSERT INTO panel_state VALUES(?,?)", (VERSION, json.dumps(overview, ensure_ascii=False)))


def publish(catalog, parsed, source_overrides, search_weights, full=False):
    """Update one published revision inside the catalog transaction."""
    db = catalog.connection
    full = full or not _index_ready(db)
    if full:
        _create_index(db)
    changes = _card_changes(db)
    sources, files = _source_changes(catalog, source_overrides)
    affected = set(changes)
    if not full:
        affected.update(_dependents(db, changes, sources))
    if not full and not affected:
        return {"mode": "unchanged", "updated_cards": 0}

    cards, structures, links = {}, {}, {}
    for identity in sorted(affected):
        card = parsed.get(identity) or catalog.get_card(identity)
        if card is None:
            continue
        cards[identity] = card
        for source_id, kind, _ in _references(card):
            if source_id not in files:
                files[source_id] = catalog.get_file(source_id)
            if files[source_id] is None:
                raise ContractError("UNKNOWN_SOURCE_ID", source_id, card["path"])
            if (kind == "code") != (files[source_id]["kind"] == "code"):
                raise ContractError("SOURCE_KIND_MISMATCH", source_id, card["path"])
        if _visible(card):
            structure = markdown_structure(card["body"], strip_frontmatter=False)
            structures[identity] = structure
            links[identity] = list(_link_targets(card["path"], structure))

    db.executemany("DELETE FROM panel_card_inputs WHERE id=?", ((identity,) for identity in changes))
    db.executemany("INSERT INTO panel_card_inputs VALUES(?,?,?,?,?,?,?)", (
        (identity, row["path"], row["sha256"], row["mtime_ns"], cards[identity]["title"][:160],
         identity in structures, json.dumps(sorted(structures[identity]["anchors"]) if identity in structures else []))
        for identity, row in changes.items() if identity in cards
    ))
    target_paths = {path for entries in links.values() for _, path, _ in entries}
    target_ids = set().union(*(_related_cards(cards[identity]) for identity in structures))
    target_ids.update(source_id for identity in structures for source_id, _, _ in _references(cards[identity]))
    graph_targets = _link_index(db, target_paths, target_ids, full)
    versions = citation_versions.project_index(catalog.registry)
    old_targets = set()
    if not full:
        for identity in sorted(affected):
            old_targets.update(_forget_card(db, identity))
        for table in ("panel_terms", "panel_tags"):
            db.executemany("DELETE FROM " + table + " WHERE card_id=?", ((identity,) for identity in changes))
    for identity, structure in structures.items():
        _write_card(db, cards[identity], structure, links[identity], graph_targets, files, versions)
        if identity in changes:
            _write_terms(db, cards[identity], search_weights)
    db.executemany("""
        DELETE FROM panel_graph_nodes WHERE id=?
        AND NOT EXISTS (SELECT 1 FROM panel_graph_edges WHERE target=panel_graph_nodes.id)
    """, ((target,) for target in sorted(old_targets)))
    _publish_overview(db)
    return {"mode": "full" if full else "incremental", "updated_cards": len(affected)}


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


def _read_overview(db):
    db.row_factory = sqlite3.Row
    db.execute("BEGIN")
    return db.execute("SELECT version,overview FROM panel_state").fetchone()


def _needs_rollback(error, path):
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        return code == sqlite3.SQLITE_READONLY_ROLLBACK
    return (str(error) == "attempt to write a readonly database"
            and path.with_name(path.name + "-journal").is_file())


@contextmanager
def _published(root, expected=None):
    path = safe_path(root, "artifacts/knowledge.sqlite", ["artifacts"])
    try:
        with ExitStack() as connections:
            db = connections.enter_context(closing(
                sqlite3.connect(indexing.sqlite_readonly_uri(path, immutable=False), uri=True)))
            try:
                state = _read_overview(db)
            except sqlite3.OperationalError as error:
                if not _needs_rollback(error, path):
                    raise
                # The SQLite pager acquires the required locks and rolls back
                # the interrupted write before serving the last published view.
                db.close()
                db = connections.enter_context(closing(sqlite3.connect(indexing.sqlite_recovery_uri(path), uri=True)))
                state = _read_overview(db)
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


def _graph_kinds(request):
    kinds = request.get("kinds", sorted(KINDS))
    if not isinstance(kinds, list) or any(not isinstance(kind, str) or kind not in KINDS for kind in kinds):
        raise ContractError("PANEL_INVALID_REQUEST", "kinds must contain card, document or code")
    return sorted(set(kinds))


def _graph(db, revision, request):
    _check(request, ("view_revision", "card_id", "kinds", "cursor", "limit"))
    identity = validate_id(request.get("card_id"))
    kinds = _graph_kinds(request)
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


def _graph_global(db, revision, request):
    _check(request, ("scope", "view_revision"))
    node_count = db.execute("SELECT COUNT(*) FROM panel_graph_nodes").fetchone()[0]
    edge_count = db.execute("SELECT COUNT(*) FROM panel_graph_edges").fetchone()[0]
    # Reserve room for the result envelope and use the JSON emitter's spacing
    # to count UTF-8 bytes, including non-ASCII titles and paths.
    budget = GRAPH_MAX_BYTES - 1024
    nodes, edges = [], []
    for row in db.execute("SELECT * FROM panel_graph_nodes ORDER BY id LIMIT ?", (GRAPH_MAX_NODES,)):
        node = dict(row)
        size = len(json.dumps(node, ensure_ascii=False).encode("utf-8")) + 2
        if size > budget:
            break
        nodes.append(node)
        budget -= size
    if nodes and budget > 0:
        last_id = nodes[-1]["id"]
        for row in db.execute("""SELECT * FROM panel_graph_edges WHERE source<=? AND target<=?
                                 ORDER BY source,target,kind LIMIT ?""", (last_id, last_id, GRAPH_MAX_EDGES)):
            edge = dict(row)
            budget -= len(json.dumps(edge, ensure_ascii=False).encode("utf-8")) + 2
            if budget < 0:
                break
            edges.append(edge)
    return {"view_revision": revision, "nodes": nodes, "edges": edges,
            "node_count": node_count, "edge_count": edge_count,
            "truncated": len(nodes) < node_count or len(edges) < edge_count}


def _graph_neighbors(db, revision, request):
    _check(request, ("scope", "view_revision", "node_id", "kinds", "cursor", "limit"))
    node_id = _text(request, "node_id", 170)
    kind, separator, ref_id = node_id.partition("/")
    if not separator or kind not in KINDS:
        raise ContractError("PANEL_INVALID_REQUEST", "Use a typed node_id from the graph")
    validate_id(ref_id)
    root = db.execute("SELECT * FROM panel_graph_nodes WHERE id=?", (node_id,)).fetchone()
    if root is None:
        raise ContractError("PANEL_NODE_NOT_FOUND", node_id)
    kinds = _graph_kinds(request)
    limit, after, scope = _page(request, ["graph-neighbors", revision, node_id, kinds], 50, width=3)
    rows = []
    for endpoint, peer, direction in (("source", "target", "out"), ("target", "source", "in")):
        comparison = ">=" if direction > after[2] else ">"
        for kind in kinds:
            # A typed ID starts with kind followed by a slash. Bound the range
            # in the same adjacency index used for the keyset cursor.
            rows.extend(db.execute(f"""
                SELECT source,target,kind,{peer} AS peer,? AS direction FROM panel_graph_edges
                WHERE {endpoint}=? AND {peer}>=? AND {peer}<? AND ({peer},kind) {comparison} (?,?)
                ORDER BY {peer},kind LIMIT ?
            """, (direction, node_id, kind + "/", kind + "0", *after[:2], limit + 1)))
    key = lambda row: [row["peer"], row["kind"], row["direction"]]
    rows.sort(key=key)
    page = rows[:limit]
    nodes = [dict(root)]
    if page:
        peers = sorted({row["peer"] for row in page})
        marks = ",".join("?" for _ in peers)
        nodes.extend(map(dict, db.execute(f"SELECT * FROM panel_graph_nodes WHERE id IN ({marks}) ORDER BY id", peers)))
    return {"view_revision": revision, "nodes": nodes,
            "edges": [{column: row[column] for column in ("source", "target", "kind")} for row in page],
            "next_cursor": _next(rows, limit, scope, key)}


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
    if action == "raw-mkdir":
        _check(request, ("path",))
        return raw_materials.mkdir(root, _text(request, "path", 1024)), "created"
    if action == "raw-rmdir":
        _check(request, ("path",))
        return raw_materials.rmdir(root, _text(request, "path", 1024)), "removed"
    if action == "intake-categories":
        _check(request, ())
        return {"categories": raw_materials.categories(root)}, "listed"
    if action == "intake-preflight":
        _check(request, ("files",))
        return intake.preflight(root, request), "checked"
    if action == "intake-save":
        _check(request, ("category", "document_path", "files"))
        return intake.save(root, request), "saved"
    if action == "read":
        _check(request, ("card_id", "view_revision"))
        return read_card(root, validate_id(request.get("card_id")), request.get("view_revision")), "read"
    if action not in {"overview", "cards", "graph", "search"}:
        raise ContractError("INVALID_ACTION", "Unknown knowledge panel action")
    with _published(root, request.get("view_revision")) as (db, overview):
        if action == "overview":
            _check(request, ("view_revision",))
            return overview, "listed"
        revision = overview["view_revision"]
        if action == "cards":
            return _cards(db, revision, request), "listed"
        if action == "search":
            return _search(db, revision, request), "searched"
        if "scope" not in request:
            return _graph(db, revision, request), "listed"
        graph_scope = request["scope"]
        if graph_scope not in ("global", "neighbors"):
            raise ContractError("PANEL_INVALID_REQUEST", "scope must be global or neighbors")
        if db.execute("""SELECT COUNT(*) FROM sqlite_master WHERE type='table'
                        AND name IN ('panel_graph_nodes','panel_graph_edges')""").fetchone()[0] != 2:
            raise ContractError("PANEL_VIEW_UNAVAILABLE", "Build the graph view with maintain reindex")
        graph = _graph_global if graph_scope == "global" else _graph_neighbors
        return graph(db, revision, request), "listed"
