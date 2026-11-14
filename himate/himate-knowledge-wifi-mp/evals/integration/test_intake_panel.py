"""Public panel intake and P1 using only synthetic files in an isolated root."""

from hashlib import sha256
from io import BytesIO
import json

import pytest
from PIL import Image

from integration import test_single_file_cli as cli_support


knowledge = cli_support.knowledge
invoke = cli_support.invoke


def _stage(directory, path, data):
    target = directory / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": path, "staged_path": str(target), "size": len(data), "sha256": sha256(data).hexdigest()}


def _save_request(document, *files, category="specs"):
    return {"category": category, "document_path": document["path"], "files": [
        {"path": row["path"], "staged_path": row["staged_path"],
         "expected_size": row["size"], "expected_sha256": row["sha256"]}
        for row in (document, *files)
    ]}


def _panel(root, action, request, *, error=None):
    status, report = invoke(root, "panel", action, request=request)
    if error is not None:
        assert status == 2 and report["diagnostics"][0]["code"] == error, report
        return
    phase = {"intake-preflight": "checked", "intake-save": "saved", "raw-path": "resolved",
             "intake-categories": "listed", "raw-list": "listed",
             "raw-mkdir": "created", "raw-rmdir": "removed"}[action]
    assert status == 0 and report["phase"] == phase, report
    return report["data"]


def _no_ingest_mutation(root, registry):
    assert (root / "governance/sources.lock.yaml").read_bytes() == registry
    assert not (root / "artifacts/knowledge.sqlite").exists()
    assert not (root / ".build").exists()
    assert list((root / "knowledge").iterdir()) == []


@pytest.fixture
def package(tmp_path):
    staged = tmp_path / "uploads"
    markdown = b"# WLAN receive design\n\n![Receive timing](figures/receive%20timing.png)\n"
    image = BytesIO()
    Image.new("RGB", (12, 8), "navy").save(image, format="PNG")
    return (
        _stage(staged, "chapter/receive.md", markdown),
        _stage(staged, "chapter/figures/receive timing.png", image.getvalue()),
        _stage(staged, "unrelated.zip", b"Unsupported input"),
    )


def test_preflight_reports_exact_relative_attachment_without_writing(knowledge, package):
    document, image, unsupported = package
    registry = (knowledge / "governance/sources.lock.yaml").read_bytes()
    (knowledge / "docs-raw/sources").mkdir()
    wrong = {**image, "path": "different/receive timing.png"}

    result = _panel(knowledge, "intake-preflight", {"files": [document, wrong, unsupported]})
    assert [category["id"] for category in result["categories"]] == ["specs"]
    primary = next(row for row in result["items"] if row["path"] == document["path"])
    assert primary["title"] == "WLAN receive design"
    assert [(row["path"], row["status"]) for row in primary["attachments"]] == [(image["path"], "missing")]
    assert [row["path"] for row in result["ignored"]] == [unsupported["path"]]
    _panel(knowledge, "intake-save", _save_request(document, wrong), error="INTAKE_ATTACHMENTS_INVALID")

    result = _panel(knowledge, "intake-preflight", {"files": [document, image, unsupported]})
    assert [row["path"] for row in result["items"]] == [document["path"]]
    assert [(row["path"], row["status"]) for row in result["items"][0]["attachments"]] == [(image["path"], "present")]
    assert list((knowledge / "docs-raw/specs").iterdir()) == []
    _no_ingest_mutation(knowledge, registry)


def test_package_save_checks_hashes_replays_and_preserves_p1_path(knowledge, package):
    document, image, _unsupported = package
    registry = (knowledge / "governance/sources.lock.yaml").read_bytes()
    request = _save_request(document, image)
    category = knowledge / "docs-raw/specs"

    mismatched = _save_request(document, {**image, "sha256": "0" * 64})
    _panel(knowledge, "intake-save", mismatched, error="RAW_STAGE_MISMATCH")
    assert list(category.iterdir()) == []
    _no_ingest_mutation(knowledge, registry)

    receipt = _panel(knowledge, "intake-save", request)
    assert receipt["path"] == "specs/receive/chapter/receive.md"
    assert receipt["sha256"] == document["sha256"]
    archived = knowledge / "docs-raw" / receipt["path"]
    image_path = category / "receive" / image["path"]
    assert sha256(archived.read_bytes()).hexdigest() == document["sha256"]
    assert sha256(image_path.read_bytes()).hexdigest() == image["sha256"]
    _no_ingest_mutation(knowledge, registry)
    resolved = _panel(knowledge, "raw-path", {"path": receipt["path"]})
    assert resolved["path"] == receipt["path"]
    assert resolved["absolute_path"] == str(archived)
    assert _panel(knowledge, "intake-save", request) == receipt
    replacement = BytesIO()
    Image.new("RGB", (12, 8), "red").save(replacement, format="PNG")
    replacement_image = _stage(knowledge.parent / "revised-uploads", image["path"], replacement.getvalue())
    _panel(knowledge, "intake-save", _save_request(document, replacement_image), error="RAW_TARGET_EXISTS")
    assert sha256(image_path.read_bytes()).hexdigest() == image["sha256"]
    assert sorted(child.name for child in category.iterdir()) == ["receive"]
    _no_ingest_mutation(knowledge, registry)

    status, report = invoke(knowledge, "ingest", "scan", request={"source": "docs-raw/specs"})
    assert status == 0 and report["phase"] == "prepared", report
    assert report["data"]["pending_at_least"] == 1
    source = report["data"]["source"]
    assert source["path"] == "docs-raw/" + receipt["path"]
    assert source["hash"] == document["sha256"]
    parsed = source["parsed"]
    assert parsed["parse_status"] == "parsed", parsed["gaps"]
    assert len(parsed["images"]) == 1
    assert sha256((knowledge / parsed["images"][0]["ref"]).read_bytes()).hexdigest() == image["sha256"]
    markdown = (knowledge / parsed["markdown_ref"]).read_text(encoding="utf-8")
    assert "![Receive timing](images/" in markdown
    assert "figures/receive%20timing.png" not in markdown
    manifest = json.loads((knowledge / parsed["manifest_ref"]).read_bytes())
    assert manifest["source_path"] == source["path"]
    assert any(row["ref"] == parsed["images"][0]["ref"] and row["sha256"] == image["sha256"]
               for row in manifest["files"])


def test_unsupported_file_is_reported_but_cannot_be_saved(knowledge, package):
    _document, _image, unsupported = package
    registry = (knowledge / "governance/sources.lock.yaml").read_bytes()
    result = _panel(knowledge, "intake-preflight", {"files": [unsupported]})
    assert result["items"] == []
    assert [row["path"] for row in result["ignored"]] == [unsupported["path"]]
    _panel(knowledge, "intake-save", _save_request(unsupported), error="RAW_UNSUPPORTED_TARGET")
    assert list((knowledge / "docs-raw/specs").iterdir()) == []
    _no_ingest_mutation(knowledge, registry)


def test_intake_uses_live_nested_folders_and_excludes_packages_and_special_tree(knowledge, package):
    document, image, _unsupported = package
    raw = knowledge / "docs-raw"
    (raw / "sources/remote").mkdir(parents=True)
    (raw / "specs/.hidden/nested").mkdir(parents=True)
    (raw / "protocols/2026").mkdir(parents=True)
    receipt = _panel(knowledge, "intake-save", _save_request(document, image, category="protocols/2026"))
    assert receipt["path"] == "protocols/2026/receive/chapter/receive.md"
    expected = [{"id": path, "label": path, "description": ""}
                for path in ("protocols", "protocols/2026", "specs")]
    assert _panel(knowledge, "intake-categories", {})["categories"] == expected
    assert _panel(knowledge, "intake-preflight", {"files": [document]})["categories"] == expected
    package = _panel(knowledge, "raw-list", {"path": "protocols/2026"})["items"][0]
    assert package["path"] == "protocols/2026/receive"
    assert package["category"] is False and package["empty"] is False
    _panel(knowledge, "intake-save", _save_request(document, image, category="sources/remote"),
           error="INTAKE_CATEGORY_INVALID")
    _panel(knowledge, "intake-save", _save_request(document, image, category="protocols/2026/receive/chapter"),
           error="INTAKE_CATEGORY_INVALID")


def test_folder_operations_are_single_level_case_safe_and_require_physical_emptiness(knowledge, package):
    document, image, _unsupported = package
    raw = knowledge / "docs-raw"
    registry = (knowledge / "governance/sources.lock.yaml").read_bytes()
    assert _panel(knowledge, "raw-mkdir", {"path": "protocols"}) == {"path": "protocols"}
    _panel(knowledge, "raw-mkdir", {"path": "Protocols"}, error="RAW_TARGET_EXISTS")
    _panel(knowledge, "raw-mkdir", {"path": "protocols/absent/2026"}, error="RAW_NOT_FOUND")
    _panel(knowledge, "raw-mkdir", {"path": "protocols/../outside"}, error="RAW_UNSAFE_PATH")
    assert _panel(knowledge, "raw-mkdir", {"path": "protocols/2026"}) == {"path": "protocols/2026"}
    row = _panel(knowledge, "raw-list", {"path": "protocols"})["items"][0]
    assert row["category"] is True and row["empty"] is True
    _panel(knowledge, "raw-rmdir", {"path": "Protocols"}, error="RAW_UNSAFE_PATH")
    _panel(knowledge, "raw-rmdir", {"path": ""}, error="RAW_UNSAFE_PATH")
    _panel(knowledge, "raw-rmdir", {"path": "protocols"}, error="RAW_DIRECTORY_NOT_EMPTY")

    hidden = raw / "protocols/2026/.gitkeep"
    hidden.write_bytes(b"")
    row = _panel(knowledge, "raw-list", {"path": "protocols"})["items"][0]
    assert row["category"] is True and row["empty"] is False
    _panel(knowledge, "raw-rmdir", {"path": "protocols/2026"}, error="RAW_DIRECTORY_NOT_EMPTY")
    assert hidden.is_file()
    hidden.unlink()
    assert _panel(knowledge, "raw-rmdir", {"path": "protocols/2026"}) == {"path": "protocols/2026"}

    (raw / "sources/remote").mkdir(parents=True)
    _panel(knowledge, "raw-mkdir", {"path": "sources/remote/child"}, error="RAW_UNSAFE_PATH")
    _panel(knowledge, "raw-rmdir", {"path": "sources/remote"}, error="RAW_UNSAFE_PATH")
    _panel(knowledge, "intake-save", _save_request(document, image))
    (raw / "specs/receive/chapter/empty").mkdir()
    _panel(knowledge, "raw-mkdir", {"path": "specs/receive/chapter/new"}, error="RAW_UNSAFE_PATH")
    _panel(knowledge, "raw-rmdir", {"path": "specs/receive/chapter/empty"}, error="RAW_UNSAFE_PATH")
    _panel(knowledge, "raw-rmdir", {"path": "specs/receive"}, error="RAW_UNSAFE_PATH")
    assert _panel(knowledge, "raw-rmdir", {"path": "protocols"}) == {"path": "protocols"}
    _no_ingest_mutation(knowledge, registry)
