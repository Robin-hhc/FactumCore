"""SQLite file/card lookups, rebuilt from cards and the source registry.

The source registry stores persistent identity, partial PDF review coverage and
latest complete processing facts. SQLite contains derived relationships and local scheduling
metadata; it does not introduce workflow phases or recovery journals.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from fnmatch import fnmatch
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
from .validation import ContractError, load_yaml, portable_path_parts, safe_path, validate_id


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or value.startswith("/") or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ContractError("INVALID_SOURCE_PATH", "Use a relative POSIX path", value)
    return PurePosixPath(value).as_posix()


def normalize_page_ranges(ranges, total_pages=None):
    """Validate physical-page intervals and return their sorted, merged union."""
    if total_pages is not None and (type(total_pages) is not int or total_pages < 1):
        raise ContractError("INVALID_REVIEWED_PAGES", "total_pages must be a positive integer")
    if not isinstance(ranges, list):
        raise ContractError("INVALID_REVIEWED_PAGES", "Use an array of [start, end] page intervals")
    values = []
    for interval in ranges:
        if (not isinstance(interval, list) or len(interval) != 2
                or any(type(page) is not int for page in interval)
                or not 1 <= interval[0] <= interval[1]
                or (total_pages is not None and interval[1] > total_pages)):
            raise ContractError("INVALID_REVIEWED_PAGES", "Use positive integer page intervals within the PDF")
        values.append(list(interval))
    merged = []
    for first, last in sorted(values):
        if merged and first <= merged[-1][1] + 1:
            merged[-1][1] = max(last, merged[-1][1])
        else:
            merged.append([first, last])
    return merged


def remaining_page_ranges(total_pages, reviewed):
    """Return the physical-page complement of confirmed review coverage."""
    if type(total_pages) is not int or total_pages < 1:
        raise ContractError("INVALID_REVIEWED_PAGES", "total_pages must be a positive integer")
    remaining, first = [], 1
    for start, end in normalize_page_ranges(reviewed, total_pages):
        if first < start:
            remaining.append([first, start - 1])
        first = end + 1
    if first <= total_pages:
        remaining.append([first, total_pages])
    return remaining


def _raw_pdf(source):
    path = source.get("path", source.get("source_path"))
    return (source.get("kind") == "raw" and isinstance(path, str)
            and PurePosixPath(path).suffix.lower() == ".pdf")


def _processing(source):
    if "processing" not in source:
        return None
    value = source["processing"]
    if isinstance(value, dict) and set(value) == {"source_sha256", "review_sha256", "reviewed_units"}:
        path = source.get("path", source.get("source_path"))
        if (source.get("kind") == "raw" and isinstance(path, str)
                and PurePosixPath(path).suffix.lower() in {".pdf", ".docx", ".xlsx"}
                and all(isinstance(value[key], str) and re.fullmatch(r"[0-9a-f]{64}", value[key])
                        for key in ("source_sha256", "review_sha256"))):
            return {**value, "reviewed_units": normalize_page_ranges(value["reviewed_units"])}
        raise ContractError("INVALID_DOCUMENT_PROCESSING", "Review progress needs a source and reading material hash")
    if (not _raw_pdf(source) or not isinstance(value, dict)
            or set(value) - {"review_sha256"} != {"source_sha256", "reviewed_pages"}
            or not isinstance(value.get("source_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", value["source_sha256"])
            or "review_sha256" in value and (not isinstance(value["review_sha256"], str)
                                             or not re.fullmatch(r"[0-9a-f]{64}", value["review_sha256"]))):
        raise ContractError("INVALID_PDF_PROCESSING", "Use source_sha256 and reviewed_pages for a raw PDF", source.get("source_id", ""))
    try:
        reviewed = normalize_page_ranges(value["reviewed_pages"])
    except ContractError as error:
        raise ContractError("INVALID_PDF_PROCESSING", error.message, source.get("source_id", "")) from error
    return {**value, "reviewed_pages": reviewed}


def _reference_review(source):
    value = source.get("reference_review")
    if value is None:
        return None
    if (not isinstance(value, dict)
            or set(value) - {"last_present_sha256"} != {"source_sha256", "exists", "reviewed_at", "source_commit"}
            or type(value["exists"]) is not bool or not isinstance(value["reviewed_at"], str)
            or not value["reviewed_at"]
            or value["exists"] and not re.fullmatch(r"[0-9a-f]{64}", str(value["source_sha256"]))
            or not value["exists"] and value["source_sha256"] is not None
            or value["source_commit"] is not None and not re.fullmatch(r"[0-9a-f]{40,64}", str(value["source_commit"]))
            or "last_present_sha256" in value and not re.fullmatch(r"[0-9a-f]{64}", str(value["last_present_sha256"]))):
        raise ContractError("INVALID_REFERENCE_REVIEW", "Use a reviewed source version, existence and timestamp")
    return value


def _clear_deleted_document_review(source):
    if source.get("kind") == "raw" and source.get("reference_review", {}).get("exists") is False:
        source.pop("reference_review", None)


def pdf_review_result(source, source_hash, pages, total_pages, *, restart=False, review_sha256=None):
    """Project confirmed coverage without writing; None means complete coverage."""
    identity = source.get("source_id", source.get("id", "")) if isinstance(source, dict) else ""
    if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        raise ContractError("INVALID_SOURCE_HASH", "Use the original PDF SHA-256", identity)
    if type(restart) is not bool:
        raise ContractError("INVALID_PDF_PROCESSING", "restart must be a boolean", identity)
    if type(total_pages) is not int or total_pages < 1:
        raise ContractError("INVALID_REVIEWED_PAGES", "total_pages must be a positive integer", identity)
    reviewed = normalize_page_ranges(pages, total_pages)
    if not isinstance(source, dict) or not _raw_pdf(source):
        raise ContractError("PDF_SOURCE_REQUIRED", "Review coverage applies only to raw PDF sources", identity)
    previous = _processing(source)
    if (not restart and previous is None and source.get("processed_hash") == source_hash
            and source.get("processed_exists") is True):
        return None
    if (not restart and previous is not None and previous["source_sha256"] == source_hash
            and "reviewed_pages" in previous and previous.get("review_sha256", review_sha256) == review_sha256):
        reviewed = normalize_page_ranges(previous["reviewed_pages"] + reviewed, total_pages)
    if not remaining_page_ranges(total_pages, reviewed):
        return None
    processing = {"source_sha256": source_hash, "reviewed_pages": reviewed}
    if review_sha256 is not None:
        processing["review_sha256"] = review_sha256
    return processing


def atomic_write(path, data):
    """Replace one file without exposing truncated Markdown or YAML to readers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{uuid4().hex}.tmp")
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

    @classmethod
    def open(cls, root, *, refresh=True, rollback_registry=False):
        """Open as a context manager and load inputs under its write lock."""
        return cls(root, refresh=refresh, rollback_registry=rollback_registry, _load_on_enter=True)

    def __init__(self, root, *, refresh=True, rollback_registry=False, _load_on_enter=False):
        self.root = Path(root).resolve(strict=True)
        self.registry_path = safe_path(self.root, "governance/sources.lock.yaml")
        self.path = safe_path(self.root, "artifacts/knowledge.sqlite")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.db = self.connection
        self._savepoint = 0
        self._refresh_on_open = refresh
        self._rollback_registry = rollback_registry
        self._registry_backup = None
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
            CREATE INDEX IF NOT EXISTS cards_file_inputs ON cards(path,id,size,mtime_ns,sha256);
            CREATE TABLE IF NOT EXISTS card_files (
                card_id TEXT NOT NULL, file_id TEXT NOT NULL, reference TEXT NOT NULL,
                PRIMARY KEY(card_id,file_id,reference)
            );
            CREATE INDEX IF NOT EXISTS card_files_file ON card_files(file_id,card_id);
            CREATE TABLE IF NOT EXISTS checked_code_references (
                file_id TEXT PRIMARY KEY, input_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS maintenance_input (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL
            );
            """)
            with self.transaction():
                if "encoding" not in {row["name"] for row in self.connection.execute("PRAGMA table_info(files)")}:
                    self.connection.execute("ALTER TABLE files ADD COLUMN encoding TEXT")
                if not _load_on_enter:
                    self._load_registry()
                    self._sync_resources()
                    if self._refresh_on_open:
                        self.refresh()
        except Exception:
            self.connection.close()
            raise

    def __enter__(self):
        self._command = self.transaction(rollback_registry=self._rollback_registry)
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
    def transaction(self, *, rollback_registry=False):
        """One short command transaction; nested operations cannot commit it."""
        outer = not self.connection.in_transaction
        if outer:
            self.connection.execute("BEGIN IMMEDIATE")
        self._savepoint += 1
        name = f"catalog_{self._savepoint}"
        self.connection.execute("SAVEPOINT " + name)
        try:
            yield
            self.connection.execute("RELEASE " + name)
            if outer:
                self.connection.commit()
        except BaseException:
            if outer:
                try:
                    if rollback_registry:
                        # SQLITE_BUSY leaves the writer transaction open after COMMIT.
                        # Restore the file before letting the next catalog writer in.
                        self._restore_registry()
                finally:
                    self.connection.rollback()
            elif self.connection.in_transaction:
                self.connection.execute("ROLLBACK TO " + name)
                self.connection.execute("RELEASE " + name)
            raise

    def _load_registry(self):
        data = self._registry_bytes()
        self.registry_digest = hashlib.sha256(data or b"").hexdigest()
        self.registry = (load_yaml(data) if data is not None else
                         {"schema_version": "2.0", "resources": [], "snapshots": []})
        if not isinstance(self.registry, dict) or not isinstance(self.registry.get("resources"), list):
            raise ContractError("INVALID_SOURCE_REGISTRY", "Expected resources", self.registry_path)
        self._validate_processing()

    def _validate_processing(self):
        for source in self.registry["resources"]:
            if isinstance(source, dict):
                _processing(source)
                _reference_review(source)

    def _sync_resources(self):
        resources = {}
        desired = {}
        columns = ("id", "kind", "path", "repo", "encoding", "processed_hash",
                   "processed_exists", "processed_at", "source_commit")
        with self.transaction():
            for source in self.registry["resources"]:
                identity = validate_id(source.get("source_id"))
                if identity in resources:
                    raise ContractError("DUPLICATE_SOURCE_ID", identity)
                resources[identity] = source
                path = source.get("path", source.get("source_path"))
                if path is None:
                    continue  # Historical version-only resources have no current file.
                desired[identity] = (identity, source["kind"], _relative(path),
                                     source.get("repo_id", source.get("repo", "")), source.get("encoding"),
                                     source.get("processed_hash"), source.get("processed_exists"),
                                     source.get("processed_at"), source.get("source_commit"))
            existing = {row["id"]: tuple(row) for row in self.connection.execute(
                "SELECT " + ",".join(columns) + ",last_attempt FROM files")}
            # Free old paths before inserting updates so ledger renames can
            # exchange paths or transfer a path to a different identity.
            self.connection.executemany("DELETE FROM files WHERE id=?", (
                (identity,) for identity, old in existing.items()
                if identity not in desired or old[1:4] != desired[identity][1:4]
            ))
            self.connection.executemany("""
                INSERT INTO files(id,kind,path,repo,encoding,processed_hash,processed_exists,processed_at,source_commit,last_attempt)
                VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                encoding=excluded.encoding,processed_hash=excluded.processed_hash,
                processed_exists=excluded.processed_exists,processed_at=excluded.processed_at,
                source_commit=excluded.source_commit
            """, ((*row, existing[identity][-1] if identity in existing else None)
                  for identity, row in desired.items()
                  if identity not in existing or existing[identity][:-1] != row))
        self._resources_by_id = resources

    def _registry_bytes(self):
        try:
            return self.registry_path.read_bytes()
        except FileNotFoundError:
            return None

    def _save_registry(self):
        self._validate_processing()
        data = yaml.safe_dump(self.registry, allow_unicode=True, sort_keys=False).encode("utf-8")
        if self._rollback_registry:
            if self._registry_backup is None:
                original = previous = self._registry_bytes()
            else:
                original, (previous,) = self._registry_backup
            # Account for a write error either before or after the replacement.
            self._registry_backup = (original, (data, previous))
        atomic_write(self.registry_path, data)
        if self._rollback_registry:
            self._registry_backup = (original, (data,))

    def _restore_registry(self):
        if self._registry_backup is None:
            return
        original, writes = self._registry_backup
        try:
            current = self._registry_bytes()
            if current == original:
                return
            if current not in writes:
                raise ContractError("SOURCE_REGISTRY_ROLLBACK_CONFLICT",
                                    "Source registry changed during publication; inspect it before retrying",
                                    self.registry_path)
            if original is None:
                self.registry_path.unlink(missing_ok=True)
            else:
                atomic_write(self.registry_path, original)
        except OSError as error:
            raise ContractError("SOURCE_REGISTRY_ROLLBACK_FAILED",
                                "Could not restore the previous source registry", self.registry_path) from error

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

    def _file(self, row):
        if row is None:
            return None
        value = dict(row)
        value["source_id"] = value["id"]
        if value["processed_exists"] is not None:
            value["processed_exists"] = bool(value["processed_exists"])
        value["processed"] = value["processed_exists"] is not None
        processing = _processing(self._resources_by_id[value["id"]])
        if processing is not None:
            value["processing"] = processing
        review = _reference_review(self._resources_by_id[value["id"]])
        if review is not None:
            value["reference_review"] = review
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
        row = self.connection.execute("SELECT path,raw FROM cards WHERE id=?", (card_id,)).fetchone()
        if row is None:
            return None
        return parse_card(row["raw"], row["path"], source_lookup=self._resources_by_id)

    def all_cards(self):
        return [parse_card(row["raw"], row["path"], source_lookup=self._resources_by_id)
                for row in self.connection.execute("SELECT path,raw FROM cards ORDER BY id")]

    def cards_for(self, file_id):
        return [self._card(row) for row in self.connection.execute("""
            SELECT DISTINCT c.* FROM cards c JOIN card_files r ON r.card_id=c.id
            WHERE r.file_id=? ORDER BY c.id
        """, (file_id,))]

    def reference_rows(self, file_id):
        return [tuple(row) for row in self.connection.execute("""
            SELECT card_id,reference FROM card_files WHERE file_id=? ORDER BY card_id,reference
        """, (file_id,))]

    def code_references_checked(self, file_id, digest):
        return self.connection.execute("""
            SELECT 1 FROM checked_code_references WHERE file_id=? AND input_sha256=?
        """, (file_id, digest)).fetchone() is not None

    def record_code_reference_check(self, file_id, digest):
        self.connection.execute("""
            INSERT INTO checked_code_references VALUES(?,?)
            ON CONFLICT(file_id) DO UPDATE SET input_sha256=excluded.input_sha256
        """, (file_id, digest))

    def files_for(self, card_id):
        rows = self.connection.execute("""
            SELECT DISTINCT f.* FROM files f JOIN card_files r ON r.file_id=f.id
            WHERE r.card_id=? ORDER BY f.id
        """, (card_id,))
        return [self._file(row) for row in rows]

    def refresh_cards(self, cards, *, _scanned_stats=None):
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
                if _scanned_stats is None:
                    target = safe_path(self.root, card["path"], ["knowledge"])
                    info = target.stat() if target.is_file() else None
                else:
                    info = _scanned_stats[card["path"]]
                self.connection.execute("""
                    INSERT INTO cards(id,path,title,sha256,metadata,body,raw,size,mtime_ns)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET path=excluded.path,
                    title=excluded.title,sha256=excluded.sha256,metadata=excluded.metadata,
                    body=excluded.body,raw=excluded.raw,size=excluded.size,mtime_ns=excluded.mtime_ns
                """, (card["id"], card["path"], card["title"], card["sha256"], _json(card["metadata"]),
                       card["body"], card["raw"], info.st_size if info else len(card["raw"]),
                       info.st_mtime_ns if info else -1))
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
        present, changed, scanned_stats = {}, [], {}
        for target, relative, info in self._scan_cards():
            old = known.get(relative)
            # The same SMB directory can be indexed from Linux and from
            # Windows, where file times have 100 ns resolution.
            if (old is None or info.st_size != old["size"]
                    or info.st_mtime_ns // 100 != old["mtime_ns"] // 100):
                card = parse_card(target.read_bytes(), relative, source_lookup=self._resources_by_id)
                changed.append(card)
                scanned_stats[relative] = info
                present[relative] = card["id"]
            else:
                present[relative] = old["id"]
        if len(set(present.values())) != len(present):
            raise ContractError("DUPLICATE_CARD_ID", "Two formal paths contain the same card ID")
        self.remove_cards([row["id"] for path, row in known.items()
                           if present.get(path) != row["id"]])
        self.refresh_cards(changed, _scanned_stats=scanned_stats)

    def _scan_cards(self):
        directory = safe_path(self.root, "knowledge")
        if not directory.is_dir():
            return
        pending = [(directory, "knowledge", {directory.resolve()})]
        drive = directory.drive.lower()
        network = drive.startswith("\\\\") and (not drive.startswith("\\\\?\\") or drive.startswith("\\\\?\\unc\\"))
        if os.name == "nt" and network:
            # Independent directory queries can overlap SMB round trips. The
            # caller still parses cards and writes SQLite on its own thread.
            with ThreadPoolExecutor(max_workers=16) as pool:
                while pending:
                    next_level = []
                    for children, cards in pool.map(self._scan_directory, pending):
                        next_level.extend(children)
                        yield from cards
                    pending = next_level
            return
        while pending:
            children, cards = self._scan_directory(pending.pop())
            pending.extend(children)
            yield from cards

    def _scan_directory(self, location):
        parent, prefix, ancestors = location
        directories, cards = [], []
        # DirEntry carries file metadata on Windows, including mapped SMB
        # directories. Validate links on both platforms before following them.
        with os.scandir(parent) as entries:
            for entry in entries:
                relative = prefix + "/" + entry.name
                is_directory = entry.is_dir(follow_symlinks=False)
                if not is_directory and (entry.name in {"AGENTS.md", "index.md", "README.md"}
                                         or not fnmatch(entry.name, "*.md")):
                    continue
                portable_path_parts(relative)
                path = Path(entry.path)
                info = entry.stat(follow_symlinks=False)
                linked = stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                if linked:
                    path = safe_path(self.root, relative, ["knowledge"])
                    info = path.stat()
                if is_directory:
                    resolved = path.resolve() if linked else parent / entry.name
                    if resolved in ancestors:
                        raise ContractError("PATH_ESCAPE", "Linked directory points to an ancestor", relative)
                    directories.append((path, relative, ancestors | {resolved}))
                elif stat.S_ISREG(info.st_mode):
                    cards.append((path, relative, info))
        return directories, cards

    def rebuild(self):
        with self.transaction():
            self.connection.execute("DELETE FROM card_files")
            self.connection.execute("DELETE FROM cards")
            self.connection.execute("DELETE FROM files")
            self._sync_resources()
            self.refresh()
            return {"files": self.connection.execute("SELECT COUNT(*) FROM files").fetchone()[0],
                    "cards": self.connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]}

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
        if not exists:
            resource.pop("processing", None)
        else:
            _clear_deleted_document_review(resource)
        resource.update(value)
        self._sync_resources()
        self._save_registry()
        return self.get_file(file_id)

    def record_pdf_review(self, file_id, source_hash, pages, total_pages, *, source_commit=None, restart=False,
                          review_sha256=None):
        """Record a successfully published batch without prematurely completing its PDF."""
        with self.transaction():
            resource = next((item for item in self.registry["resources"] if item["source_id"] == file_id), None)
            if resource is None:
                raise ContractError("UNKNOWN_SOURCE_ID", file_id)
            processing = pdf_review_result(resource, source_hash, pages, total_pages, restart=restart,
                                           review_sha256=review_sha256)
            if (not restart and "processing" not in resource and resource.get("processed_hash") == source_hash
                    and resource.get("processed_exists") is True):
                return self.get_file(file_id)
            if processing is None:
                resource.pop("processing", None)
                return self.mark_processed(file_id, source_hash, source_commit=source_commit)
            resource["processing"] = processing
            _clear_deleted_document_review(resource)
            self._sync_resources()
            self._save_registry()
            return self.get_file(file_id)

    def record_document_review(self, file_id, source_hash, processing, *, source_commit=None):
        with self.transaction():
            resource = self._resources_by_id[file_id]
            if processing is None:
                resource.pop("processing", None)
                return self.mark_processed(file_id, source_hash, source_commit=source_commit)
            _processing({**resource, "processing": processing})
            resource["processing"] = processing
            _clear_deleted_document_review(resource)
            self._sync_resources()
            self._save_registry()
            return self.get_file(file_id)

    def touch_attempt(self, file_id):
        with self.transaction():
            self.connection.execute("UPDATE files SET last_attempt=? WHERE id=?",
                                    (datetime.now(timezone.utc).isoformat(), file_id))

    def maintenance_input(self):
        row = self.connection.execute("SELECT payload FROM maintenance_input WHERE singleton=1").fetchone()
        return json.loads(row[0]) if row else None

    def set_maintenance_input(self, value):
        self.connection.execute("DELETE FROM maintenance_input")
        if value is not None:
            self.connection.execute("INSERT INTO maintenance_input VALUES(1,?)", (_json(value),))

    def mark_reference_reviewed(self, file_id, source_hash, exists, *, source_commit=None):
        """Record existing-card review independently of whole-source ingestion."""
        if (type(exists) is not bool or (exists and not re.fullmatch(r"[0-9a-f]{64}", str(source_hash)))
                or (not exists and source_hash is not None)):
            raise ContractError("INVALID_REFERENCE_REVIEW", "Use the reviewed source hash and existence")
        resource = self._resources_by_id[file_id]
        previous = resource.get("reference_review", {})
        last_present = (previous.get("source_sha256") or previous.get("last_present_sha256")
                        or resource.get("processed_hash"))
        resource["reference_review"] = {
            "source_sha256": source_hash, "exists": exists,
            "reviewed_at": datetime.now(timezone.utc).isoformat(), "source_commit": source_commit,
        }
        if not exists and last_present is not None:
            resource["reference_review"]["last_present_sha256"] = last_present
        self._save_registry()
        return self.get_file(file_id)
