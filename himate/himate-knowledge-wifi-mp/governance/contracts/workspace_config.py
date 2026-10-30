"""Data-only workspace discovery shared by diagnostics and business contracts.

This module has no package imports or business-data access. Doctor may compile
its exact locked bytes without importing the governance package or its engines.
"""

from pathlib import Path
import json
import os
import re
import stat

import yaml


class WorkspaceConfigError(ValueError):
    def __init__(self, code, message, path=""):
        self.code, self.message, self.path = code, str(message), str(path)
        super().__init__(f"{code}: {message}" + (f" ({path})" if path else ""))


def relative_path(value):
    """Validate a portable workspace path without reading the filesystem."""
    if value == ".":
        return value
    if (not isinstance(value, str) or not value or value.startswith("/")
            or "\\" in value or ":" in value or "\x00" in value):
        raise WorkspaceConfigError("UNSAFE_WORKSPACE_PATH", "Expected a relative POSIX directory", value)
    for part in value.split("/"):
        if (part in {"", ".", ".."} or part != part.rstrip(" .")
                or any(char in part for char in '<>"|?*')
                or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)):
            raise WorkspaceConfigError("UNSAFE_WORKSPACE_PATH", "Invalid portable component", value)
    return value


def no_links(path):
    for item in (path, *path.parents):
        if item.is_symlink() or (os.path.lexists(item)
                and getattr(item.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise WorkspaceConfigError("WORKSPACE_LINKED_PATH", "Linked workspace paths are not allowed", item)


def workspace_path(root, relative):
    relative_path(relative)
    path = Path(root)
    for part in (() if relative == "." else relative.split("/")):
        no_links(path)
        if path.is_dir():
            aliases = [item.name for item in path.iterdir() if item.name.casefold() == part.casefold()]
            if aliases and aliases != [part]:
                raise WorkspaceConfigError("PATH_CASE_ALIAS", "Path spelling differs from actual file", relative)
        path /= part
    no_links(path)
    return path


def configuration(raw, path):
    """Parse only JSON-compatible YAML mappings, rejecting duplicate keys."""
    class Loader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        loader.flatten_mapping(node)
        value = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in value:
                raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", "Non-string or duplicate configuration key", path)
            value[key] = loader.construct_object(value_node, deep=deep)
        return value

    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        value = yaml.load(raw.decode("utf-8-sig"), Loader=Loader)
        if not isinstance(value, dict):
            raise ValueError("Workspace configuration must be a mapping")
        json.dumps(value, allow_nan=False)
    except (yaml.YAMLError, UnicodeError, RecursionError, TypeError, ValueError) as error:
        if isinstance(error, WorkspaceConfigError):
            raise
        raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", str(error), path) from error
    return value


def select(knowledge_root, registrations=None, expected_rules=None, *, config_path=None):
    """Select exactly one explicit safe mapping, never an arbitrary parent.

    Well-formed declarations for other knowledge roots are unrelated. Invalid,
    unreadable or unsafe declarations fail closed; multiple exact mappings are
    ambiguous. Explicit registrations restrict discovery to their own paths.
    """
    root = Path(knowledge_root).absolute()
    no_links(root)
    root = root.resolve(strict=True)
    if config_path is not None:
        candidates = [(None, {"config": str(config_path)})]
    elif registrations is not None:
        if not isinstance(registrations, dict):
            raise WorkspaceConfigError("WORKSPACE_CONFIG_UNAVAILABLE", "Installed workspace registrations must be a mapping")
        candidates = list(registrations.items())
    else:
        candidates = [(None, {"config": str(parent / "config.yml")}) for parent in (root, *root.parents)]
    matches, available = [], []
    for identity, entry in candidates:
        if not isinstance(entry, dict) or not isinstance(entry.get("config"), str):
            continue
        candidate = Path(entry["config"])
        if not candidate.is_absolute():
            raise WorkspaceConfigError("WORKSPACE_CONFIG_UNAVAILABLE", "Workspace config must be absolute", candidate)
        no_links(candidate)
        if not os.path.lexists(candidate):
            continue
        available.append(candidate)
        try:
            raw = candidate.read_bytes()
        except OSError as error:
            raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", str(error), candidate) from error
        value = configuration(raw, candidate)
        roots = value.get("knowledge_roots")
        if not isinstance(roots, dict) or set(roots) != {"wifi"}:
            raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", "Expected one knowledge_roots.wifi mapping", candidate)
        relative = relative_path(roots["wifi"])
        if relative == "." or workspace_path(candidate.parent, relative).resolve() != root:
            continue
        if identity is not None and (value.get("workspace_id") != identity
                or expected_rules is not None and entry.get("rules_digest") != expected_rules):
            continue
        try:
            unchanged = candidate.read_bytes() == raw
        except OSError:
            unchanged = False
        if not unchanged:
            raise WorkspaceConfigError("WORKSPACE_CONFIG_CHANGED", "Workspace config changed while selecting", candidate)
        matches.append(candidate.resolve())
    if len(matches) > 1:
        raise WorkspaceConfigError("WORKSPACE_CONFIG_AMBIGUOUS", "Multiple configs map to the selected WiFi root")
    if not matches:
        raise WorkspaceConfigError("WORKSPACE_CONFIG_UNAVAILABLE", "No exact workspace config maps to the selected WiFi root",
                                   available[0] if available else "")
    return matches[0]
