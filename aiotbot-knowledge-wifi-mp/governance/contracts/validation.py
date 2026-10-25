"""Pinned rules, strict parsing, diagnostics and portable relative paths."""

from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
import yaml
from jsonschema import Draft202012Validator


class ContractError(ValueError):
    def __init__(self, code, message, path=""):
        self.code, self.message, self.path = code, str(message), str(path)
        super().__init__(f"{code}: {message}" + (f" ({path})" if path else ""))


def diagnostic(code, path="", field="", message=""):
    return {"code": code, "path": str(path), "field": field, "message": message}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ContractError("INVALID_CANONICAL_VALUE", exc) from exc


def digest_payload(payload):
    return sha256_bytes(
        canonical_bytes({k: v for k, v in payload.items() if k != "digest"})
    )


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("DUPLICATE_KEY", key)
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8-sig"),
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda x: (_ for _ in ()).throw(
                ContractError("NONFINITE_NUMBER", x)
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("INVALID_JSON", exc, path) from exc


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    return _unique_pairs(
        [
            (
                loader.construct_object(k, deep=deep),
                loader.construct_object(v, deep=deep),
            )
            for k, v in node.value
        ]
    )


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(value):
    """Only a Path explicitly requests a file; text is never guessed to be a filename."""
    try:
        text = value.read_bytes() if isinstance(value, Path) else value
        if isinstance(text, bytes):
            text = text.decode("utf-8-sig")
        if "\x00" in text:
            raise ContractError("NUL_INPUT", "NUL is invalid source text")
        result = yaml.load(text, Loader=_UniqueLoader)
        canonical_bytes(result)
        return result
    except (yaml.YAMLError, UnicodeError, RecursionError, OSError) as exc:
        raise ContractError("INVALID_YAML", exc) from exc


def validate_id(value):
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}", value)
        or value in (".", "..")
    ):
        raise ContractError("INVALID_ID", "Expected a bounded identifier", value)
    return value


def safe_path(root, relative, allowed_prefixes=None):
    root = Path(root).resolve(strict=True)
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or ":" in relative
        or "\x00" in relative
    ):
        raise ContractError("UNSAFE_PATH", "Expected a relative POSIX path", relative)
    parts = PurePosixPath(relative).parts
    if (
        relative.startswith("/")
        or not parts
        or any(p in (".", "..", "") for p in relative.split("/"))
    ):
        raise ContractError(
            "UNSAFE_PATH", "Absolute/traversal/empty components forbidden", relative
        )
    for part in parts:
        if (
            part != part.rstrip(" .")
            or any(c in part for c in '<>"|?*')
            or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
        ):
            raise ContractError("UNSAFE_PATH", "Invalid portable component", relative)
    if allowed_prefixes and not any(
        relative == p.rstrip("/") or relative.startswith(p.rstrip("/") + "/")
        for p in allowed_prefixes
    ):
        raise ContractError(
            "PATH_OUTSIDE_ALLOWED_ROOT", "Not an allowed asset", relative
        )
    cursor = root
    for part in parts:
        if cursor.is_dir():
            aliases = [
                p.name for p in cursor.iterdir() if p.name.casefold() == part.casefold()
            ]
            if aliases and part not in aliases:
                raise ContractError(
                    "PATH_CASE_ALIAS",
                    "Path spelling differs from actual file",
                    relative,
                )
        cursor = cursor / part
        try:
            cursor.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise ContractError(
                "PATH_ESCAPE", "Link/junction leaves root", relative
            ) from exc
    return cursor


def _walk_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and (
                not isinstance(item, str) or not item.startswith("#/")
            ):
                raise ContractError("EXTERNAL_SCHEMA_REF", item)
            _walk_refs(item)
    elif isinstance(value, list):
        for item in value:
            _walk_refs(item)


def load_rules(knowledge_root, expected_digest):
    root = Path(knowledge_root).resolve(strict=True)
    lock_bytes = safe_path(root, "governance/framework.lock.yaml").read_bytes()
    if not expected_digest or sha256_bytes(lock_bytes) != expected_digest:
        raise ContractError("RULES_DIGEST_MISMATCH", "Caller-pinned lock differs")
    lock = load_yaml(lock_bytes)
    if (
        lock.get("schema_version") != "2.0"
        or lock.get("contract_family") != "aiot-wifi"
    ):
        raise ContractError("UNSUPPORTED_CONTRACT_VERSION", "Expected aiot-wifi 2.0")
    capabilities = lock.get("capabilities", {})
    if any(capabilities.get(name) != "1.0" for name in ("checks", "indexing", "ingest_records")):
        raise ContractError("RULE_CAPABILITY_UNAVAILABLE", "Compatible checks, indexing and ingest-record capabilities are required")
    entries = lock.get("files", {})
    if not isinstance(entries, dict):
        raise ContractError("INVALID_RULE_LOCK", "files must be an object")
    seen = set()
    for item in entries.values():
        path = item.get("path", "")
        if path in seen:
            raise ContractError("DUPLICATE_RULE_PATH", path)
        seen.add(path)
        if sha256_bytes(safe_path(root, path, ["governance"]).read_bytes()) != item.get(
            "sha256"
        ):
            raise ContractError("RULE_FILE_DIGEST_MISMATCH", "Rule bytes differ", path)
    code = {
        "governance/contracts/" + n
        for n in (
            "__init__.py",
            "validation.py",
            "knowledge.py",
            "source_resources.py",
            "records.py",
            "indexing.py",
            "checks.py",
        )
    }
    if not code.issubset(seen):
        raise ContractError(
            "UNPINNED_CONTRACT_CODE", "All domain modules must be pinned"
        )
    if not {
        "governance/schemas/profiles.yaml",
        "governance/schemas/registries.yaml",
    }.issubset(seen):
        raise ContractError(
            "UNPINNED_RULE_DECLARATION", "Profiles and registries must both be pinned"
        )
    schemas = {}
    for kind, name in (
        ("workspace", "workspace"),
        ("card", "frontmatter"),
        ("sources", "sources"),
        ("record", "records"),
    ):
        path = "governance/schemas/" + name + ".schema.json"
        if path not in seen:
            raise ContractError("UNPINNED_SCHEMA", path)
        schema = read_json(safe_path(root, path))
        _walk_refs(schema)
        Draft202012Validator.check_schema(schema)
        schemas[kind] = schema
    profiles = load_yaml(safe_path(root, "governance/schemas/profiles.yaml"))
    registries = load_yaml(safe_path(root, "governance/schemas/registries.yaml"))
    # Schema stores the executable shape; reject drift from its controlled
    # declarations instead of silently accepting either of two enum truths.
    for field in ("lifecycle", "review_mode"):
        if schemas["card"]["properties"][field]["enum"] != registries[field]:
            raise ContractError("RULE_DECLARATION_MISMATCH", field)
    for field in ("evidence_kind", "usage"):
        if schemas["card"]["$defs"]["claim"]["properties"][field]["enum"] != registries[field]:
            raise ContractError("RULE_DECLARATION_MISMATCH", field)
    if set(schemas["card"]["properties"]["profile"]["enum"]) != set(profiles["profiles"]):
        raise ContractError("RULE_DECLARATION_MISMATCH", "profile")
    return {
        "knowledge_root": root,
        "lock": lock,
        "rules_digest": expected_digest,
        "schemas": schemas,
        "profiles": profiles,
        "registries": registries,
    }


def validate_shape(kind, payload, rules):
    schema_kind = kind if kind in rules["schemas"] else "record"
    errors = sorted(
        Draft202012Validator(rules["schemas"][schema_kind]).iter_errors(payload),
        key=lambda e: str(list(e.path)),
    )
    if errors:
        error = errors[0]
        raise ContractError(
            "SCHEMA_INVALID", error.message, "/".join(map(str, error.path))
        )
    if (
        schema_kind == "record"
        and kind != "record"
        and payload.get("record_kind") != kind
    ):
        raise ContractError("RECORD_KIND_MISMATCH", f"Expected {kind}")
    if kind == "workspace":
        targets = payload["targets"]
        target_map = {item["target_id"]: item for item in targets}
        expected = {
            f"{chip}-{side}": (chip, side)
            for chip in ("chip12", "chip08", "chip07c")
            for side in ("host", "device")
        }
        if len(target_map) != len(targets) or set(target_map) != set(expected):
            raise ContractError(
                "TARGET_ID_SET_INVALID",
                "Exactly six distinct registered WiFi Targets are required",
            )
        for target_id, (chip, side) in expected.items():
            if (target_map[target_id]["chip"], target_map[target_id]["side"]) != (
                chip,
                side,
            ):
                raise ContractError("TARGET_IDENTITY_MISMATCH", target_id)
        pairs = payload["pairs"]
        if len({item["pairing_id"] for item in pairs}) != len(pairs) or {
            item["pairing_id"] for item in pairs
        } != {chip + "-host-device" for chip in ("chip12", "chip08", "chip07c")}:
            raise ContractError(
                "PAIR_ID_SET_INVALID", "Exactly three distinct WiFi pairs are required"
            )
        for pair in pairs:
            host, device = (
                target_map.get(pair["host_target"]),
                target_map.get(pair["device_target"]),
            )
            if (
                not host
                or not device
                or host["side"] != "host"
                or device["side"] != "device"
                or host["chip"] != device["chip"]
                or pair["pairing_id"] != host["chip"] + "-host-device"
            ):
                raise ContractError("PAIR_TARGET_MISMATCH", pair["pairing_id"])
    return payload


def markdown_structure(data):
    """Parse the governed Markdown subset while preserving original line numbers.

    Code examples never create headings or links. Heading fragments use a fixed
    Unicode, lower-case slug and occurrence suffix, shared by every checker.
    """
    import html
    import unicodedata

    text = data.decode("utf-8-sig") if isinstance(data, bytes) else str(data)
    result, fence, frontmatter = [], None, False
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        if number == 1 and line.strip() == "---":
            frontmatter = True
            result.append(" " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):])
            continue
        if frontmatter:
            if line.strip() == "---":
                frontmatter = False
            result.append(" " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):])
            continue
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        hidden = fence is not None or match is not None
        if match:
            token = match.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
        if hidden:
            line = " " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):]
        else:
            line = re.sub(r"(`+)(?!`)(.*?)\1(?!`)", lambda m: " " * len(m.group()), line)
        result.append(line)
    visible = "".join(result)
    anchors, counts, duplicate_anchors, links, conflicts = set(), {}, [], [], []
    definitions = {}
    for line in visible.splitlines():
        match = re.match(r"^ {0,3}\[([^]]+)\]:\s*<?([^\s>]+)>?", line)
        if match:
            definitions[match.group(1).casefold()] = match.group(2)
    for number, line in enumerate(visible.splitlines(), 1):
        if re.match(r"^(?:<{7}|={7}|>{7})(?:\s|$)", line):
            conflicts.append(number)
        for explicit in re.finditer(r"<a\s+(?:id|name)=[\"']([^\"']+)[\"'][^>]*>", line):
            anchor = html.unescape(explicit.group(1))
            if anchor in anchors:
                duplicate_anchors.append({"anchor": anchor, "line": number})
            anchors.add(anchor)
        heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            label = html.unescape(re.sub(r"<[^>]+>", "", heading.group(1))).lower()
            label = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", label)
            slug = "".join(ch for ch in label if ch.isspace() or ch in "_-" or unicodedata.category(ch)[0] in "LN")
            slug = re.sub(r"\s", "-", slug)
            occurrence = counts.get(slug, 0)
            counts[slug] = occurrence + 1
            anchor = slug if occurrence == 0 else f"{slug}-{occurrence}"
            if anchor in anchors:
                duplicate_anchors.append({"anchor": anchor, "line": number})
            anchors.add(anchor)
        if re.match(r"^ {0,3}\[[^]]+\]:", line):
            continue
        for match in re.finditer(r"!?\[[^]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)", line):
            links.append({"target": html.unescape(match.group(1) or match.group(2)), "line": number})
        for match in re.finditer(r"!?\[([^]\n]+)\]\[([^]\n]*)\]", line):
            key = (match.group(2) or match.group(1)).casefold()
            links.append({"target": definitions.get(key), "label": key, "line": number})
    return {"visible": visible, "anchors": anchors, "duplicate_anchors": duplicate_anchors, "links": links, "conflicts": conflicts}
