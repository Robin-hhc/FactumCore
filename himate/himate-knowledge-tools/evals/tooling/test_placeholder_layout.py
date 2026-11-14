"""Directory explanations remain versioned while local material stays ignored."""

import os
from pathlib import Path
import subprocess

import pytest


DOMAIN = "himate/himate-knowledge-wifi-mp"
SLOTS = [
    "main",
    f"{DOMAIN}/.build",
    f"{DOMAIN}/artifacts",
    f"{DOMAIN}/docs-raw/chips",
    f"{DOMAIN}/docs-raw/conventions",
    f"{DOMAIN}/docs-raw/protocols",
    f"{DOMAIN}/docs-raw/sources/3ms",
    f"{DOMAIN}/docs-raw/sources/dbox",
    f"{DOMAIN}/docs-raw/sources/wiki",
    f"{DOMAIN}/docs-raw/specs",
    f"{DOMAIN}/docs-raw/storys",
    f"{DOMAIN}/docs-raw/troubleshooting",
]


def git(workspace, *arguments):
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    return subprocess.run(["git", *arguments], cwd=workspace, env=environment,
                          capture_output=True, text=True, timeout=15)


@pytest.fixture
def workspace(tmp_path):
    from support.contracts import KNOWLEDGE_ROOT, ROOT, copy_workspace_metadata

    root = tmp_path / "workspace"
    root.mkdir()
    copy_workspace_metadata(root, root / KNOWLEDGE_ROOT.relative_to(ROOT))
    result = git(root, "init", "--quiet")
    assert result.returncode == 0, result.stderr
    return root


def is_ignored(workspace, relative):
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Synthetic local material.\n", encoding="utf-8")
    result = git(workspace, "check-ignore", "--no-index", "--quiet", "--", Path(relative).as_posix())
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


@pytest.mark.parametrize("slot", SLOTS)
def test_local_content_slots_only_allow_their_root_readme(workspace, slot):
    assert not is_ignored(workspace, f"{slot}/README.md")
    for relative in ("material.txt", ".local-state", "nested/material.txt", "nested/README.md"):
        assert is_ignored(workspace, f"{slot}/{relative}"), f"Unexpectedly versionable: {slot}/{relative}"


@pytest.mark.parametrize("relative", [
    "docs-raw/AGENTS.md", "docs-raw/index.md", "docs-raw/sources/dbox.example.yml",
])
def test_raw_routing_and_configuration_examples_remain_versionable(workspace, relative):
    assert not is_ignored(workspace, f"{DOMAIN}/{relative}")
