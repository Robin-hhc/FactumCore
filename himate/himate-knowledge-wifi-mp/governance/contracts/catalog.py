"""SQLite file/card lookups, rebuilt from cards and the source registry.

The source registry stores only persistent source identity and latest complete
processing facts. SQLite contains derived relationships and local scheduling
metadata; it does not introduce workflow phases or recovery journals.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import sys
from uuid import uuid4

import yaml

from .cards_v3 import parse_card
from .validation import ContractError, load_yaml, safe_path, validate_id


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or value.startswith("/") or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ContractError("INVALID_SOURCE_PATH", "Use a relative POSIX path", value)
    return PurePosixPath(value).as_posix()


def atomic_write(path, data):
    """Replace one file without exposing truncated Markdown or YAML to readers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
        if path.exists():
            temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Catalog:
    """Public file/card relation queries and latest processed file versions."""

    def __init__(self, root, *, refresh=True):
        self.root = Path(root).resolve(strict=True)
        self.registry_path = safe_path(self.root, "governance/sources.lock.yaml")
        self.path = safe_path(self.root, "artifacts/knowledge.sqlite")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.db = self.connection
        self._savepoint = 0
        self._refresh_on_open = refresh
        try:
            # executescript commits implicitly; initialize schema before taking
            # the command transaction that protects source/card/index updates.
            self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL, repo TEXT NOT NULL,
                encoding TEXT,
                processed_hash TEXT, processed_exists INTEGER, processed_at TEXT,
                source_commit TEXT, last_attempt TEXT,
                UNIQUE(kind,path,repo)
            );
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
                sha256 TEXT NOT NULL, metadata TEXT NOT NULL, body TEXT NOT NULL, raw BLOB NOT NULL,
                size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS card_files (
                card_id TEXT NOT NULL, file_id TEXT NOT NULL, reference TEXT NOT NULL,
                PRIMARY KEY(card_id,file_id,reference)
            );
            CREATE INDEX IF NOT EXISTS card_files_file ON card_files(file_id,card_id);
            """)
            with self.transaction():
                if "encoding" not in {row["name"] for row in self.connection.execute("PRAGMA table_info(files)")}:
                    self.connection.execute("ALTER TABLE files ADD COLUMN encoding TEXT")
                self._load_registry()
                self._sync_resources()
                if self._refresh_on_open:
                    self.refresh()
        except Exception:
            self.connection.close()
            raise

    def __enter__(self):
        self._command = self.transaction()
        try:
            self._command.__enter__()
        except BaseException:
            self.close()
            raise
        try:
            # The registry may have changed between construction and entry.
            # Read it only after the same SQLite writer boundary is acquired.
            self._load_registry()
            self._sync_resources()
            if self._refresh_on_open:
                self.refresh()
        except BaseException:
            self._command.__exit__(*sys.exc_info())
            self.close()
            raise
        return self

    def __exit__(self, *exception):
        try:
            return self._command.__exit__(*exception)
        finally:
            self.close()

    def close(self):
        self.connection.close()

    @contextmanager
    def transaction(self):
        """One short command transaction; nested operations cannot commit it."""
        outer = not self.connection.in_transaction
        if outer:
            self.connection.execute("BEGIN IMMEDIATE")
        self._savepoint += 1
        name = f"catalog_{self._savepoint}"
        self.connection.execute("SAVEPOINT " + name)
        try:
            yield
        except BaseException:
            self.connection.execute("ROLLBACK TO " + name)
            self.connection.execute("RELEASE " + name)
            if outer:
                self.connection.rollback()
            raise
        else:
            self.connection.execute("RELEASE " + name)
            if outer:
                try:
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise

    def _load_registry(self):
        self.registry = (load_yaml(self.registry_path.read_bytes()) if self.registry_path.exists()
                         else {"schema_version": "2.0", "resources": [], "snapshots": []})
        if not isinstance(self.registry, dict) or not isinstance(self.registry.get("resources"), list):
            raise ContractError("INVALID_SOURCE_REGISTRY", "Expected resources", self.registry_path)

    def _sync_resources(self):
        identities = set()
        with self.transaction():
            for source in self.registry["resources"]:
                identity = validate_id(source.get("source_id"))
                if identity in identities:
                    raise ContractError("DUPLICATE_SOURCE_ID", identity)
                identities.add(identity)
                path = source.get("path", source.get("source_path"))
                if path is None:
                    continue  # Historical version-only resources remain untouched.
                self.connection.execute("""
                    INSERT INTO files(id,kind,path,repo,encoding,processed_hash,processed_exists,processed_at,source_commit)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    kind=excluded.kind,path=excluded.path,repo=excluded.repo,
                    encoding=excluded.encoding,
                    processed_hash=excluded.processed_hash,processed_exists=excluded.processed_exists,
                    processed_at=excluded.processed_at,source_commit=excluded.source_commit
                """, (identity, source["kind"], _relative(path), source.get("repo_id", source.get("repo", "")),
                      source.get("encoding"),
                      source.get("processed_hash"), source.get("processed_exists"), source.get("processed_at"),
                      source.get("source_commit")))
            for row in self.connection.execute("SELECT id FROM files").fetchall():
                if row["id"] not in identities:
                    self.connection.execute("DELETE FROM files WHERE id=?", (row["id"],))

    def _save_registry(self):
        atomic_write(self.registry_path, yaml.safe_dump(
            self.registry, allow_unicode=True, sort_keys=False).encode("utf-8"))

    def register(self, kind, path, repo=None, source_id=None, *, encoding=None):
        return self.register_many([{"kind": kind, "path": path, "repo": repo,
                                    "source_id": source_id, "encoding": encoding}])[0]

    def register_many(self, sources):
        """Register a discovered batch once, preserving existing source IDs."""
        existing = self.list_files()
        by_path = {(row["kind"], row["path"], row["repo"]): row["id"] for row in existing}
        by_id = {row["id"]: (row["kind"], row["path"], row["repo"]) for row in existing}
        added, identities, encodings = [], [], {}
        for source in sources:
            kind = "raw" if source.get("kind") == "doc" else source.get("kind")
            if kind not in {"raw", "code", "attachment"}:
                raise ContractError("INVALID_SOURCE_KIND", kind)
            encoding = source.get("encoding")
            if encoding is not None and (kind != "code" or not isinstance(encoding, str)
                                         or encoding not in {"utf-8", "gb18030"}):
                raise ContractError("INVALID_SOURCE_ENCODING", "Code encoding must be utf-8 or gb18030")
            path, repo = _relative(source.get("path")), source.get("repo", source.get("repo_id")) or ""
            if not isinstance(repo, str):
                raise ContractError("INVALID_SOURCE_REPO", "Repository identity must be text", path)
            key = kind, path, repo
            requested = source.get("source_id")
            identity = by_path.get(key)
            if identity is not None:
                if requested is not None and requested != identity:
                    raise ContractError("SOURCE_ID_CONFLICT", "The path already has a different ID", path)
            else:
                identity = validate_id(requested or (("code-" if kind == "code" else "doc-")
                                       + hashlib.sha256((kind + "\0" + repo + "\0" + path).encode()).hexdigest()[:20]))
                if identity in by_id and by_id[identity] != key:
                    raise ContractError("SOURCE_ID_CONFLICT", "The ID already identifies another file", identity)
                resource = {"source_id": identity, "kind": kind, "path": path}
                if repo:
                    resource["repo_id"] = repo
                added.append(resource)
                by_path[key], by_id[identity] = identity, key
            if encoding is not None:
                encodings[identity] = encoding
            identities.append(identity)
        self.registry["resources"].extend(added)
        changed = bool(added)
        for resource in self.registry["resources"]:
            if resource["source_id"] in encodings and resource.get("encoding") != encodings[resource["source_id"]]:
                resource["encoding"] = encodings[resource["source_id"]]
                changed = True
        if changed:
            self._save_registry()
            self._sync_resources()
        return [self.get_file(identity) for identity in identities]

    @staticmethod
    def _file(row):
        if row is None:
            return None
        value = dict(row)
        value["source_id"] = value["id"]
        if value["processed_exists"] is not None:
            value["processed_exists"] = bool(value["processed_exists"])
        value["processed"] = value["processed_exists"] is not None
        return value

    def get_file(self, file_id):
        return self._file(self.connection.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone())

    def list_files(self, kind=None, referenced=False):
        predicates, values = [], []
        if kind is not None:
            predicates.append("f.kind=?")
            values.append("raw" if kind == "doc" else kind)
        if referenced:
            predicates.append("EXISTS(SELECT 1 FROM card_files r WHERE r.file_id=f.id)")
        where = " WHERE " + " AND ".join(predicates) if predicates else ""
        return [self._file(row) for row in self.connection.execute("SELECT f.* FROM files f" + where + " ORDER BY f.id", values)]

    @staticmethod
    def _card(row):
        if row is None:
            return None
        value = dict(row)
        value["card_id"] = value["id"]
        value["metadata"] = json.loads(value["metadata"])
        return value

    def get_card(self, card_id):
        row = self.connection.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if row is None:
            return None
        return parse_card(row["raw"], row["path"], source_lookup={item["id"]: item for item in self.list_files()})

    def all_cards(self):
        lookup = {item["id"]: item for item in self.list_files()}
        return [parse_card(row["raw"], row["path"], source_lookup=lookup)
                for row in self.connection.execute("SELECT * FROM cards ORDER BY id")]

    def cards_for(self, file_id):
        return [self._card(row) for row in self.connection.execute("""
            SELECT DISTINCT c.* FROM cards c JOIN card_files r ON r.card_id=c.id
            WHERE r.file_id=? ORDER BY c.id
        """, (file_id,))]

    def files_for(self, card_id):
        rows = self.connection.execute("""
            SELECT DISTINCT f.* FROM files f JOIN card_files r ON r.file_id=f.id
            WHERE r.card_id=? ORDER BY f.id
        """, (card_id,))
        return [self._file(row) for row in rows]

    def refresh_cards(self, cards):
        cards = list(cards.values()) if isinstance(cards, dict) else list(cards)
        if len({card["id"] for card in cards}) != len(cards):
            raise ContractError("DUPLICATE_CARD_ID", "Card IDs must be unique")
        with self.transaction():
            for card in cards:
                references = [(reference["doc_id"], reference) for reference in card["doc_ref"]]
                references.extend((reference["code_id"], reference) for reference in card["code_ref"])
                for identity, reference in references:
                    source = self.get_file(identity)
                    if source is None:
                        raise ContractError("UNKNOWN_SOURCE_ID", identity, card["path"])
                    if (("code_id" in reference) != (source["kind"] == "code")):
                        raise ContractError("SOURCE_KIND_MISMATCH", identity, card["path"])
                target = safe_path(self.root, card["path"], ["knowledge"])
                stat = target.stat() if target.is_file() else None
                self.connection.execute("""
                    INSERT INTO cards(id,path,title,sha256,metadata,body,raw,size,mtime_ns)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET path=excluded.path,
                    title=excluded.title,sha256=excluded.sha256,metadata=excluded.metadata,
                    body=excluded.body,raw=excluded.raw,size=excluded.size,mtime_ns=excluded.mtime_ns
                """, (card["id"], card["path"], card["title"], card["sha256"], _json(card["metadata"]),
                      card["body"], card["raw"], stat.st_size if stat else len(card["raw"]),
                      stat.st_mtime_ns if stat else -1))
                self.connection.execute("DELETE FROM card_files WHERE card_id=?", (card["id"],))
                self.connection.executemany("INSERT INTO card_files(card_id,file_id,reference) VALUES(?,?,?)",
                                            [(card["id"], identity, _json(reference)) for identity, reference in references])

    def remove_cards(self, card_ids):
        with self.transaction():
            for identity in card_ids:
                self.connection.execute("DELETE FROM card_files WHERE card_id=?", (identity,))
                self.connection.execute("DELETE FROM cards WHERE id=?", (identity,))

    def refresh(self):
        """Refresh files edited or pulled outside this process; read changed cards."""
        with self.transaction():
            self._refresh()

    def _refresh(self):
        known = {row["path"]: row for row in self.connection.execute("SELECT id,path,size,mtime_ns FROM cards")}
        present, changed = set(), []
        lookup = {item["id"]: item for item in self.list_files()}
        directory = self.root / "knowledge"
        for target in sorted(directory.rglob("*.md")) if directory.is_dir() else []:
            if target.name in {"AGENTS.md", "index.md", "README.md"}:
                continue
            relative = target.relative_to(self.root).as_posix()
            target = safe_path(self.root, relative, ["knowledge"])
            present.add(relative)
            stat = target.stat()
            old = known.get(relative)
            if old is None or (stat.st_size, stat.st_mtime_ns) != (old["size"], old["mtime_ns"]):
                changed.append(parse_card(target.read_bytes(), relative, source_lookup=lookup))
        ids = [card["id"] for card in changed]
        if len(ids) != len(set(ids)):
            raise ContractError("DUPLICATE_CARD_ID", "Two formal paths contain the same card ID")
        for card in changed:
            old = self.connection.execute("SELECT path FROM cards WHERE id=?", (card["id"],)).fetchone()
            if old and old["path"] != card["path"] and old["path"] in present:
                raise ContractError("DUPLICATE_CARD_ID", card["id"])
        changed_ids = {card["path"]: card["id"] for card in changed}
        self.remove_cards([row["id"] for path, row in known.items()
                           if path not in present or path in changed_ids and row["id"] != changed_ids[path]])
        self.refresh_cards(changed)

    def rebuild(self):
        with self.transaction():
            self.connection.execute("DELETE FROM card_files")
            self.connection.execute("DELETE FROM cards")
            self.connection.execute("DELETE FROM files")
            self._sync_resources()
            self.refresh()
            return {"files": len(self.list_files()), "cards": len(self.all_cards())}

    def mark_processed(self, file_id, hash_or_none, exists=True, *, source_commit=None):
        if exists and (not isinstance(hash_or_none, str) or not re.fullmatch(r"[0-9a-f]{64}", hash_or_none)):
            raise ContractError("INVALID_PROCESSED_HASH", "Use SHA-256 for an existing file", file_id)
        if not exists and hash_or_none is not None:
            raise ContractError("INVALID_PROCESSED_HASH", "A handled missing file has no content hash", file_id)
        resource = next((item for item in self.registry["resources"] if item["source_id"] == file_id), None)
        if resource is None:
            raise ContractError("UNKNOWN_SOURCE_ID", file_id)
        value = {"processed_hash": hash_or_none, "processed_exists": bool(exists),
                 "processed_at": datetime.now(timezone.utc).isoformat(), "source_commit": source_commit}
        resource.update(value)
        self._sync_resources()
        self._save_registry()
        return self.get_file(file_id)

    def touch_attempt(self, file_id):
        with self.transaction():
            self.connection.execute("UPDATE files SET last_attempt=? WHERE id=?",
                                    (datetime.now(timezone.utc).isoformat(), file_id))
