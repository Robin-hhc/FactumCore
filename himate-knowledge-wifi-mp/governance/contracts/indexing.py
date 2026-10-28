"""Shared SQLite format, deterministic lexical rows and complete verification.

The caller chooses the card collection and supplies parsed, exact-byte cards.
These functions neither qualify knowledge nor publish an active generation.
"""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sqlite3
import tempfile
import unicodedata
from urllib.parse import quote

from .validation import ContractError, canonical_bytes, sha256_bytes

INDEX_SCHEMA_VERSION = "3.0"


@dataclass(frozen=True)
class VerifiedDatabase:
    """In-process full-row observation bound to exact database bytes and inputs."""

    rules_digest: str
    database_digest: str
    rows_digest: str
    summary: tuple


def reuse_database(cards, rules_digest, path, observed):
    if (not isinstance(observed, VerifiedDatabase)
            or observed.rules_digest != rules_digest
            or observed.rows_digest != sha256_bytes(canonical_bytes(_rows(cards, rules_digest)))
            or observed.database_digest != sha256_bytes(Path(_native(path)).read_bytes())):
        raise ContractError("INDEX_OBSERVATION_CHANGED", "Verified database bytes or input rows changed", path)
    return dict(observed.summary)
TOKENIZER_VERSION = "2.0"
_DDL = (
    "CREATE TABLE documents(card_id TEXT PRIMARY KEY,path TEXT,metadata TEXT);"
    "CREATE TABLE claims(card_id TEXT,claim_id TEXT,metadata TEXT,PRIMARY KEY(card_id,claim_id));"
    "CREATE TABLE postings(token TEXT,card_id TEXT,claim_id TEXT,field TEXT,PRIMARY KEY(token,card_id,claim_id,field));"
    "CREATE INDEX postings_token ON postings(token);"
    "CREATE TABLE relations(card_id TEXT,target_id TEXT,kind TEXT);"
    "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);"
)
_COLUMNS = {
    "documents": ("card_id", "path", "metadata"),
    "claims": ("card_id", "claim_id", "metadata"),
    "postings": ("token", "card_id", "claim_id", "field"),
    "relations": ("card_id", "target_id", "kind"),
    "metadata": ("key", "value"),
}


def term_groups(text):
    result = []
    for word in re.findall(r"[\u3400-\u9fff]+|[^\W\u3400-\u9fff]+", unicodedata.normalize("NFKC", text)):
        if re.fullmatch(r"[\u3400-\u9fff]+", word):
            chunks = [word] if len(word) == 1 else [word[i:i + 2] for i in range(len(word) - 1)]
            result.extend({chunk} for chunk in chunks)
        else:
            result.append({word.casefold(), "=" + word})
    return [set(group) for group in sorted({tuple(sorted(group)) for group in result})]


def lexical(text):
    return sorted(set().union(*term_groups(text))) if text else []


def _native(path):
    value = str(Path(path).absolute())
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        return "\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value
    return value


def sqlite_readonly_uri(path):
    """Open an absolute, immutable generation without a SQLite URI authority.

    SQLite normally rejects file://server/share; a UNC name belongs in the
    URI path (file:////server/share). Extended Windows namespaces also stay
    in the path, with their ? escaped; dropping them breaks long filenames.
    Escape the filename, never an already constructed URI.
    Callers still validate the authorized path and generation fingerprint.
    """
    value = os.fspath(path)
    windows = isinstance(path, PureWindowsPath) or (
        not isinstance(path, PurePosixPath)
        and (os.name == "nt" or value.startswith(("\\\\", "//?/"))
             or re.match(r"^[A-Za-z]:", value))
    )
    if windows:
        normalized = PureWindowsPath(value)
        value = normalized.as_posix()
        if not normalized.is_absolute() or value.startswith("//./"):
            raise ValueError("An absolute filesystem path is required for SQLite")
        if len(str(normalized)) >= 260 and not value.startswith("//?/"):
            value = "//?/UNC/" + value[2:] if value.startswith("//") else "//?/" + value
        uri = ("file://" + quote(value, safe="/:")
               if value.startswith("//") else normalized.as_uri())
    else:
        normalized = path if isinstance(path, PurePosixPath) else Path(path)
        uri = normalized.as_uri()
    return uri + "?mode=ro&immutable=1"


def _rows(cards, rules_digest):
    rows = {name: [] for name in _COLUMNS}
    ids, paths = set(), set()
    for card in cards:
        meta, path = card["metadata"], card["path"]
        card_id = meta["id"]
        if card_id in ids or path in paths:
            raise ContractError("INDEX_DUPLICATE_CARD", card_id, path)
        ids.add(card_id)
        paths.add(path)
        rows["documents"].append((card_id, path, canonical_bytes(meta).decode("utf-8")))
        fields = {"title": meta["title"], "aliases": " ".join(meta.get("aliases", [])),
                  "summary": meta["summary"], "search_terms": " ".join(meta.get("search_terms", []))}
        for name, text in fields.items():
            rows["postings"].extend((token, card_id, "*", name) for token in lexical(text))
        claim_ids = set()
        for claim in card["claims"]:
            if claim["id"] in claim_ids:
                raise ContractError("INDEX_DUPLICATE_CLAIM", claim["id"], path)
            claim_ids.add(claim["id"])
            rows["claims"].append((card_id, claim["id"], canonical_bytes(claim).decode("utf-8")))
            for name, text in (("body", claim["text"]), ("search_terms", " ".join(claim.get("search_terms", [])))):
                rows["postings"].extend((token, card_id, claim["id"], name) for token in lexical(text))
        rows["relations"].extend((card_id, row["target_card_id"], row["type"]) for row in meta["relations"])
    rows["metadata"] = [("rules_digest", rules_digest), ("schema_version", INDEX_SCHEMA_VERSION),
                        ("tokenizer_version", TOKENIZER_VERSION)]
    return {name: sorted(values) for name, values in rows.items()}


def build_database(cards, rules_digest, path, *, verified=False):
    """Create a new database; never overwrite an existing generation."""
    rows = _rows(cards, rules_digest)
    path = Path(_native(path))
    if path.exists():
        raise ContractError("INDEX_OUTPUT_EXISTS", "A fresh output path is required", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(str(path))) as connection:
            connection.executescript(_DDL)
            for table, values in rows.items():
                slots = ",".join("?" for _ in _COLUMNS[table])
                connection.executemany(f"INSERT INTO {table} VALUES({slots})", values)
            connection.commit()
    except (OSError, sqlite3.Error) as exc:
        path.unlink(missing_ok=True)
        raise ContractError("INDEX_BUILD_FAILED", exc, path) from exc
    return (verify_database(cards, rules_digest, path, observed=True) if verified
            else verify_database(cards, rules_digest, path))


def verify_database(cards, rules_digest, path, *, observed=False):
    """Compare full logical rows, schema and versions against the exact collection."""
    expected = _rows(cards, rules_digest)
    path = Path(_native(path))
    if not path.is_file():
        raise ContractError("INDEX_MISSING", "Database does not exist", path)
    before = sha256_bytes(path.read_bytes()) if observed else None
    # Opening the existing file with mode=ro also prevents a missing input becoming an empty DB.
    uri = sqlite_readonly_uri(path)
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ContractError("INDEX_INTEGRITY", "SQLite integrity check failed", path)
            schema = connection.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            with closing(sqlite3.connect(":memory:")) as reference:
                reference.executescript(_DDL)
                wanted = reference.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            if schema != wanted:
                raise ContractError("INDEX_SCHEMA_MISMATCH", "Unexpected database schema", path)
            for table, values in expected.items():
                actual = connection.execute(f"SELECT {','.join(_COLUMNS[table])} FROM {table}").fetchall()
                if Counter(actual) != Counter(values):
                    raise ContractError("INDEX_ROWS_MISMATCH", f"Full {table} rows differ", path)
    except (OSError, sqlite3.Error) as exc:
        raise ContractError("INDEX_READ_FAILED", exc, path) from exc
    summary = {"complete": True, "documents": len(expected["documents"]),
            "claims": len(expected["claims"]), "postings": len(expected["postings"]),
            "schema_version": INDEX_SCHEMA_VERSION, "tokenizer_version": TOKENIZER_VERSION,
            "rules_digest": rules_digest, "rows_digest": sha256_bytes(canonical_bytes(expected))}
    if observed:
        if sha256_bytes(path.read_bytes()) != before:
            raise ContractError("INDEX_CHANGED", "Database changed during full verification", path)
        return VerifiedDatabase(rules_digest, before, summary["rows_digest"], tuple(sorted(summary.items())))
    return summary


def check(cards, rules, temp_dir):
    """Build and verify a temporary index without leaving artifacts or switching active."""
    with tempfile.TemporaryDirectory(prefix="index-check-", dir=_native(temp_dir)) as temporary:
        return build_database(cards, rules["rules_digest"], Path(temporary) / "index.sqlite")


def read_document(raw, path, rules, *, card_id, sha256):
    from .knowledge import decode_card

    if sha256_bytes(raw) != sha256:
        raise ContractError("INDEX_BODY_MISMATCH", "Frozen body fingerprint differs", path)
    card = decode_card(raw, path, rules)
    if card["metadata"]["id"] != card_id:
        raise ContractError("INDEX_CARD_ID_MISMATCH", card_id, path)
    return card
