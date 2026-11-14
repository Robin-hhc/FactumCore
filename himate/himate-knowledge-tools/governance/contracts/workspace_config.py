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


def code_root_parts(value, *, legacy=False):
    """Separate leading parent hops from the normal relative code directory."""
    parents = 0
    if isinstance(value, str) and not legacy:
        while value.startswith("../"):
            parents += 1
            value = value[3:]
        if value == "..":
            return parents + 1, "."
    if parents and value == ".":
        raise WorkspaceConfigError("UNSAFE_WORKSPACE_PATH", "Expected a directory after the parent hops", value)
    return parents, relative_path(value)


def code_location(config_directory, value, *, legacy=False):
    """Resolve the code path anchor without requiring a Git or code checkout."""
    parents, directory = code_root_parts(value, legacy=legacy)
    base = Path(config_directory)
    if parents > len(base.parents):
        raise WorkspaceConfigError("UNSAFE_WORKSPACE_PATH", "Code root goes above the filesystem root", value)
    return (base.parents[parents - 1] if parents else base), directory


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


def mapped_root(config, config_path, knowledge_root):
    """Match the actual knowledge directory without requiring a domain name."""
    path = Path(config_path)
    roots = config.get("knowledge_roots")
    if (not isinstance(roots, dict) or not roots
            or any(not isinstance(name, str) or not name.strip() for name in roots)):
        raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", "Expected named knowledge_roots mappings", path)
    matches = []
    root = Path(knowledge_root).resolve(strict=True)
    for relative in roots.values():
        relative_path(relative)
        mapped = workspace_path(path.parent, relative).resolve()
        if relative != "." and mapped == root:
            matches.append(relative)
    if len(matches) > 1:
        raise WorkspaceConfigError("WORKSPACE_CONFIG_AMBIGUOUS", "Multiple entries map to the selected knowledge root", path)
    return matches[0] if matches else None


def context(knowledge_root, registrations=None, expected_rules=None, *, config_path=None):
    """Read the local configuration, or a legacy mapping explicitly supplied by a caller."""
    root = Path(knowledge_root).absolute()
    no_links(root)
    root = root.resolve(strict=True)
    local = root / "config.yml"
    explicit = config_path is not None or registrations is not None
    if config_path is not None:
        candidates = [(None, {"config": str(config_path)})]
    elif registrations is not None:
        if not isinstance(registrations, dict):
            raise WorkspaceConfigError("WORKSPACE_CONFIG_UNAVAILABLE", "Installed workspace registrations must be a mapping")
        candidates = list(registrations.items())
    else:
        candidates = [(None, {"config": str(workspace_path(root, "config.yml"))})]
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
            if not stat.S_ISREG(candidate.lstat().st_mode):
                raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", "Expected a regular configuration file", candidate)
            raw = candidate.read_bytes()
        except OSError as error:
            raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", str(error), candidate) from error
        value = configuration(raw, candidate)
        if "knowledge_roots" in value:
            if not explicit:
                raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", "Migrate the configuration to the knowledge-root format", candidate)
            if mapped_root(value, candidate, root) is None:
                continue
        else:
            if candidate.resolve() != local:
                continue
            workspace_path(root, "config.yml")
            if (value.get("schema_version") != "2.0" or not isinstance(value.get("workspace_id"), str)
                    or not value["workspace_id"].strip() or not isinstance(value.get("modules"), list)
                    or set(value) - {"schema_version", "workspace_id", "code_root", "modules", "query", "toolchain"}):
                raise WorkspaceConfigError("WORKSPACE_CONFIG_INVALID", "Expected a version 2.0 knowledge-root module configuration", candidate)
            try:
                code_location(root, value.get("code_root"))
            except WorkspaceConfigError as error:
                raise WorkspaceConfigError(error.code, error.message, candidate) from error
        if identity is not None and (value.get("workspace_id") != identity
                or expected_rules is not None and entry.get("rules_digest") != expected_rules):
            continue
        try:
            unchanged = candidate.read_bytes() == raw
        except OSError:
            unchanged = False
        if not unchanged:
            raise WorkspaceConfigError("WORKSPACE_CONFIG_CHANGED", "Workspace config changed while selecting", candidate)
        matches.append((candidate.resolve(), raw, value))
    if len(matches) > 1:
        raise WorkspaceConfigError("WORKSPACE_CONFIG_AMBIGUOUS", "Multiple configs map to the selected knowledge root")
    if not matches:
        raise WorkspaceConfigError("WORKSPACE_CONFIG_UNAVAILABLE", "No exact configuration for the selected knowledge root",
                                   available[0] if available else local)
    return matches[0]


def select(knowledge_root, registrations=None, expected_rules=None, *, config_path=None):
    return context(knowledge_root, registrations, expected_rules, config_path=config_path)[0]
