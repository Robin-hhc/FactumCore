"""Load digest-locked local declarative contracts, without plugins or remote resolution."""

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing.exceptions import Unresolvable

from . import CONTRACT_FAMILY, __version__, receipts


class ContractError(ValueError):
    def __init__(self, code, message, path=""):
        super().__init__(message)
        self.code, self.message, self.path = code, message, str(path)


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError("Mapping keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_document(path):
    path = Path(path)
    try:
        return load_document_bytes(path.read_bytes(), path)
    except OSError as exc:
        raise ContractError("INVALID_DOCUMENT", str(exc), path) from exc


def load_document_bytes(data, path=""):
    """Parse the very same immutable byte string that the caller hashes."""
    try:
        value = yaml.load(data.decode("utf-8-sig"), Loader=_UniqueLoader)
        if not isinstance(value, dict):
            raise ValueError("Expected an object")
        json.dumps(value, allow_nan=False)
        return value
    except (OSError, UnicodeError, yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        raise ContractError("INVALID_DOCUMENT", str(exc), path) from exc


def _deny_external_refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and (
                not isinstance(child, str) or not child.startswith("#")
            ):
                raise ContractError(
                    "REMOTE_SCHEMA_REFERENCE", "Only in-document references are allowed"
                )
            _deny_external_refs(child)
    elif isinstance(value, list):
        for child in value:
            _deny_external_refs(child)


def load_bundle(knowledge_root):
    root = Path(knowledge_root).resolve(strict=True)
    lock_path = root / "governance/framework.lock.yaml"
    lock_bytes = lock_path.read_bytes()
    lock = load_document_bytes(lock_bytes, lock_path)
    captured = {lock_path: lock_bytes}
    if (
        lock.get("schema_version") != "1.0"
        or lock.get("contract_family") != CONTRACT_FAMILY
        or lock.get("tool_version") != __version__
    ):
        raise ContractError("CONTRACT_INCOMPATIBLE", "Unsupported contract/tool version")
    files = lock.get("files")
    names = {"workspace", "card", "sources", "record", "profiles", "registries"}
    if not isinstance(files, dict) or set(files) != names:
        raise ContractError(
            "INVALID_CONTRACT_LOCK", "Expected four schemas, profiles and registries"
        )
    bundle = {}
    for name in sorted(names):
        ref = files[name]
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            raise ContractError("INVALID_CONTRACT_LOCK", "Invalid file entry", name)
        if not isinstance(ref["path"], str) or Path(ref["path"]).is_absolute():
            raise ContractError("CONTRACT_PATH_ESCAPE", "Contract paths must be relative", name)
        path = (root / ref["path"]).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ContractError(
                "CONTRACT_PATH_ESCAPE", "Contract path escapes knowledge root", name
            )
        data = path.read_bytes()
        if receipts.digest_bytes(data) != ref["sha256"]:
            raise ContractError("LOCK_DIGEST_MISMATCH", "Contract bytes differ from lock", name)
        item = load_document_bytes(data, path)
        captured[path] = data
        if path.read_bytes() != data:
            raise ContractError("CONTRACT_CHANGED", "Contract changed during load", name)
        if name in {"workspace", "card", "sources", "record"}:
            _deny_external_refs(item)
            try:
                Draft202012Validator.check_schema(item)
            except SchemaError as exc:
                raise ContractError("INVALID_SCHEMA", exc.message, name) from exc
        elif item.get("schema_version") != "1.0":
            raise ContractError("CONTRACT_INCOMPATIBLE", "Unsupported declarations", name)
        bundle[name] = item
    expected_profiles = {"entity", "flow", "protocol", "rule", "command", "runbook", "glossary"}
    if set(bundle["profiles"].get("profiles", {})) != expected_profiles:
        raise ContractError("INVALID_PROFILES", "Exactly seven profiles are required")
    for path, data in captured.items():
        if path.read_bytes() != data:
            raise ContractError("CONTRACT_CHANGED", "Contract bundle changed during load", path)
    return bundle


def validate_document(kind, document, knowledge_root):
    if kind not in {"workspace", "card", "sources", "record"}:
        raise ContractError("INVALID_CONTRACT_KIND", "Unknown validation kind", kind)
    bundle = load_bundle(knowledge_root)
    errors = []
    try:
        for error in Draft202012Validator(bundle[kind]).iter_errors(document):
            path = "/" + "/".join(str(part) for part in error.absolute_path)
            errors.append({"code": "SCHEMA_VALIDATION", "message": error.message, "path": path})
    except Unresolvable as exc:
        raise ContractError("INVALID_SCHEMA_REFERENCE", str(exc), kind) from exc
    if not errors and kind == "workspace":
        from .scope import validate_configuration

        errors.extend(validate_configuration(document))
    return sorted(errors, key=lambda item: (item["path"], item["code"], item["message"]))
