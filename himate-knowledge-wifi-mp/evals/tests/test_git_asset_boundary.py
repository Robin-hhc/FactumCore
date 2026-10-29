"""Git distribution preserves business state and excludes machine writer data."""

from pathlib import Path
import shutil
import subprocess

import pytest


REPO = Path(__file__).resolve().parents[3]
K = "himate-knowledge-wifi-mp/"


@pytest.fixture
def checkout(tmp_path):
    shutil.copyfile(REPO / ".gitignore", tmp_path / ".gitignore")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    return tmp_path


@pytest.mark.parametrize("relative", [
    ".build/operations/ingest/view.json",
    ".build/operations/ingest/transaction/journal.json",
    ".build/runtime/writer.lock",
    ".build/project-context/context.json",
    "artifacts/indexes/local/active.json",
    "logs/operations/ingest/journal.json",
    "logs/operations/ingest/apply-result.json",
    "logs/operations/ingest/backups/old.bin",
    "logs/operations/.writer.lock",
    "logs/evidence/objects/source.bin",
    "logs/evidence/checked-code/wifi.c",
    "logs/evidence/extractions/source.txt",
    "logs/evidence/locators/source.json",
])
def test_machine_products_stay_out_of_git(checkout, relative):
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", K + relative], cwd=checkout, capture_output=True,
    )
    assert result.returncode == 0, relative


@pytest.mark.parametrize("relative", [
    "knowledge/rules/rule.md",
    "knowledge/rules/index.md",
    "governance/sources.lock.yaml",
    "docs-raw/specs/rule.md",
    "logs/ingest/ingest.yaml",
    "logs/events/state.json",
    "logs/events/event.json",
    "logs/evidence/published/objects/source.bin",
    "logs/evidence/published/cards/card.md",
    "logs/evidence/published/extractions/source.txt",
    "logs/evidence/published/locators/source.json",
    "logs/publications/ingest/manifest.json",
    "logs/publications/ingest/completion.json",
    "logs/evidence/build-support.bin",
    "logs/evidence/runtime-support.log",
    ".build/.gitkeep",
    "artifacts/.gitkeep",
    "logs/operations/.gitkeep",
])
def test_shared_assets_and_explicit_materials_remain_versionable(checkout, relative):
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", K + relative], cwd=checkout, capture_output=True,
    )
    assert result.returncode == 1, relative
