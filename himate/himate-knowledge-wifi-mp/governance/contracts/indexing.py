"""Exact lexical terms and portable read-only SQLite paths."""

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import unicodedata
from urllib.parse import quote


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
