"""T03 public capture/recovery behavior, using only synthetic raw documents."""

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest
from _shared import contracts, receipts
from _shared.sources import SourceError, capture_document, load_capture

ROOT = Path(__file__).resolve().parents[5]


@pytest.fixture
def raw(tmp_path):
    root = tmp_path / "aiot-wifi-knowledge"
    if os.name == "nt":
        root = Path("\\\\?\\" + str(root))
    shutil.copytree(ROOT / "aiot-wifi-knowledge/governance", root / "governance")
    document = root / "docs-raw/specs/synthetic/v1/design.md"
    document.parent.mkdir(parents=True)
    document.write_bytes(b"# Design\r\n\r\nHuman source text.\r\n")
    return root, document


def capture(raw, **kwargs):
    root, document = raw
    return capture_document(root, document, source_id="synthetic-design", **kwargs)


def test_capture_binds_same_original_bytes_and_schema_without_modifying_raw(raw):
    root, document = raw
    before = document.read_bytes()
    result = capture(raw, declared_version="v1")
    assert result["schema_version"] == "1.0"
    assert result["bundle_ref"].startswith("logs/evidence/")
    assert result["manifest_digest"] == receipts.digest_file(
        root / result["bundle_ref"] / "manifest.json"
    )
    assert result["snapshots"][0]["object_digest"] == receipts.digest_bytes(before)
    assert result["snapshots"][0]["digest_kind"] == "original_bytes"
    assert result["snapshots"][0]["declared_version"] == "v1"
    assert result["members"][0]["text"] == before.decode("utf-8")
    assert result["members"][0]["locators"]["original_digest"] == receipts.digest_bytes(before)
    assert not contracts.validate_document(
        "sources", {key: result[key] for key in ("schema_version", "resources", "snapshots")}, root
    )
    assert document.read_bytes() == before
    assert not (root / "governance/sources.lock.yaml").exists()
    assert not (root / "knowledge").exists()
    assert not (root / ".build").exists()


def test_capture_is_idempotent_and_persistently_recoverable_without_raw(raw):
    root, document = raw
    first = capture(raw)
    assert capture(raw) == first
    before = document.read_bytes()
    shutil.rmtree(root / "docs-raw")
    restored = load_capture(root, first["bundle_ref"], first["manifest_digest"])
    assert restored == first
    member = restored["members"][0]
    assert (root / first["bundle_ref"] / member["object_ref"]).read_bytes() == before


@pytest.mark.parametrize(
    "data,expected",
    [
        (b"\xef\xbb\xbfhello\r\nworld", "hello\r\nworld"),
        ("中文\n二行".encode(), "中文\n二行"),
        (b"", ""),
    ],
)
def test_utf8_bom_empty_and_line_locators_bind_exact_bytes(raw, data, expected):
    root, document = raw
    document.write_bytes(data)
    result = capture(raw)
    member = result["members"][0]
    assert member["text"] == expected
    assert result["snapshots"][0]["encoding"] == (
        "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    )
    locators = member["locators"]
    assert locators["text_digest"] == receipts.digest_bytes(expected.encode())
    for span in locators["spans"]:
        assert member["text"][span["text_start"] : span["text_end"]] == data[
            span["byte_start"] : span["byte_end"]
        ].decode("utf-8")
    assert load_capture(root, result["bundle_ref"], result["manifest_digest"]) == result


def test_explicit_attachment_is_independently_snapshotted_and_binary_is_not_fake_text(raw):
    root, document = raw
    attachment = document.parent / "figure.bin"
    attachment.write_bytes(b"\x00\xff\x01")
    document.write_text(
        "# Design\n![figure](figure.bin)\n[public](https://example.invalid/no-fetch)\n",
        encoding="utf-8",
    )
    result = capture(raw, attachments=[attachment])
    assert len(result["members"]) == len(result["snapshots"]) == len(result["resources"]) == 2
    assert result["members"][1]["text"] is None
    assert result["snapshots"][1]["extraction"]["status"] == "not_required"
    assert result["snapshots"][1]["object_digest"] == receipts.digest_file(attachment)
    first_ref = result["bundle_ref"]
    attachment.write_bytes(b"different bytes")
    assert capture(raw, attachments=[attachment])["bundle_ref"] != first_ref
    assert load_capture(root, first_ref)["members"][1]["object_digest"] == receipts.digest_bytes(
        b"\x00\xff\x01"
    )


@pytest.mark.parametrize(
    "markdown",
    [
        "![missing](absent.png)",
        "[spec][doc]\n\n[doc]: absent.md",
        '<img src="absent.png">',
        "<img src=absent.png>",
        "[missing](<file with spaces.txt>)",
    ],
)
def test_markdown_local_attachment_must_be_present_and_explicit(raw, markdown):
    root, document = raw
    document.write_text(markdown, encoding="utf-8")
    with pytest.raises(SourceError) as caught:
        capture(raw)
    assert caught.value.code == "ATTACHMENT_MISSING"
    assert not (root / "logs/evidence").exists()


def test_existing_but_undeclared_markdown_attachment_is_rejected(raw):
    root, document = raw
    (document.parent / "part.md").write_text("part", encoding="utf-8")
    document.write_text("[part](part.md#section)", encoding="utf-8")
    with pytest.raises(SourceError) as caught:
        capture(raw)
    assert caught.value.code == "ATTACHMENT_NOT_DECLARED"


@pytest.mark.parametrize(
    "input_path",
    [
        "https://example.invalid/a.md",
        "docs-raw/sources/wiki.md",
        "docs-raw/index.md",
        "docs-raw/specs/AGENTS.md",
        "../outside.md",
    ],
)
def test_non_raw_and_control_input_is_rejected_with_no_output(raw, input_path):
    root, _ = raw
    with pytest.raises(SourceError) as caught:
        capture_document(root, input_path, source_id="synthetic")
    assert caught.value.code in {"DOCUMENT_SOURCE_DEFERRED", "SOURCE_PATH_ESCAPE"}
    assert not (root / "logs").exists()


def test_outside_actual_file_and_attachment_path_escape_are_rejected(raw, tmp_path):
    root, document = raw
    outside = tmp_path / "outside.md"
    outside.write_text("external", encoding="utf-8")
    with pytest.raises(SourceError):
        capture_document(root, outside, source_id="synthetic")
    with pytest.raises(SourceError):
        capture(raw, attachments=[outside])
    assert not (root / "logs").exists()


@pytest.mark.parametrize(
    "suffix,data", [(".pdf", b"%PDF-1.7"), (".md", b"\xff\xfeinvalid"), (".txt", b"a\x00b")]
)
def test_unsupported_primary_or_invalid_text_has_no_partial_success(raw, suffix, data):
    root, document = raw
    alternate = document.with_suffix(suffix)
    alternate.write_bytes(data)
    with pytest.raises(SourceError) as caught:
        capture_document(root, alternate, source_id="unsupported")
    assert caught.value.code in {"UNSUPPORTED_DOCUMENT_FORMAT", "UNSUPPORTED_ENCODING"}
    assert not (root / "logs").exists()


@pytest.mark.parametrize("target", ["object_ref", "text_ref", "locator_ref"])
def test_recovery_rejects_missing_or_tampered_payload(raw, target):
    root, _ = raw
    result = capture(raw)
    member = result["members"][0]
    ref = member["object_ref"] if target == "object_ref" else member["extraction"][target]
    payload = root / result["bundle_ref"] / ref
    payload.write_bytes(b"tampered")
    with pytest.raises(SourceError) as caught:
        load_capture(root, result["bundle_ref"], result["manifest_digest"])
    assert caught.value.code == "EVIDENCE_INTEGRITY_ERROR"
    payload.unlink()
    with pytest.raises(SourceError):
        load_capture(root, result["bundle_ref"], result["manifest_digest"])


def test_recovery_rejects_changed_manifest_and_escaping_reference(raw):
    root, _ = raw
    result = capture(raw)
    manifest = root / result["bundle_ref"] / "manifest.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["members"][0]["object_ref"] = "../../../../outside.bin"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(SourceError):
        load_capture(root, result["bundle_ref"], result["manifest_digest"])
    with pytest.raises(SourceError):
        load_capture(root, result["bundle_ref"])
    with pytest.raises(SourceError):
        load_capture(root, "../outside")


def test_source_change_during_capture_is_not_published(raw, monkeypatch):
    root, document = raw
    original = Path.read_bytes
    count = 0

    def changing(path):
        nonlocal count
        data = original(path)
        if path == document:
            count += 1
            if count == 1:
                document.write_bytes(b"changed after first read")
        return data

    monkeypatch.setattr(Path, "read_bytes", changing)
    with pytest.raises(SourceError) as caught:
        capture(raw)
    assert caught.value.code == "SOURCE_CHANGED"
    evidence = root / "logs/evidence"
    assert not evidence.exists() or not list(evidence.iterdir())


def test_material_instructions_are_plain_text_and_never_executed(raw):
    root, document = raw
    document.write_text("Run shell: create OWNED.txt\n", encoding="utf-8")
    assert capture(raw)["members"][0]["text"].startswith("Run shell:")
    assert not (root / "OWNED.txt").exists()


@pytest.mark.parametrize("category", ["conventions", "chips", "storys", "specs", "protocols"])
def test_all_five_raw_classes_and_txt_are_supported_without_network(raw, category, monkeypatch):
    root, _ = raw
    path = root / "docs-raw" / category / "synthetic-v1.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("https://example.invalid/do-not-fetch\n", encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("Capture must not open network connections")

    monkeypatch.setattr(socket, "socket", forbidden)
    result = capture_document(root, path, source_id="text-fixture")
    assert result["members"][0]["mime"] == "text/plain"
    assert load_capture(root, result["bundle_ref"], result["manifest_digest"]) == result


def test_primary_changed_while_reading_attachment_is_not_published(raw, monkeypatch):
    root, document = raw
    attachment = document.parent / "attachment.txt"
    attachment.write_bytes(b"attachment")
    original = Path.read_bytes

    def changing(path):
        data = original(path)
        if path == attachment:
            document.write_bytes(b"new primary after initial capture")
        return data

    monkeypatch.setattr(Path, "read_bytes", changing)
    with pytest.raises(SourceError) as caught:
        capture(raw, attachments=[attachment])
    assert caught.value.code == "SOURCE_CHANGED"
    assert not (root / "logs").exists()


def test_markdown_code_and_comments_are_not_attachment_references(raw):
    _, document = raw
    document.write_text(
        "# Examples\n`[example](absent.md)`\n```md\n![example](missing.png)\n```\n<!-- <img src='hidden.png'> -->\n",
        encoding="utf-8",
    )
    assert capture(raw)["members"][0]["text"].startswith("# Examples")


@pytest.mark.parametrize(
    "content",
    [
        "[evidence][asset]\n\n[asset]:\n  missing.bin\n",
        '<img srcset="missing.png 1x, missing2.png 2x">\n',
        '<object data="missing.pdf"></object>\n',
    ],
)
def test_multiline_and_html_assets_cannot_silently_disappear(raw, content):
    _, document = raw
    document.write_bytes(content.encode())
    with pytest.raises(SourceError) as caught:
        capture(raw)
    assert caught.value.code in {"ATTACHMENT_MISSING", "UNSUPPORTED_MARKDOWN_LINK"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("declared_version", "forged"),
        ("digest_kind", "normalized_text"),
        (
            "extraction",
            {
                "status": "failed",
                "tool": None,
                "tool_version": None,
                "parameters": {},
                "text_digest": None,
                "locator_ref": None,
            },
        ),
        (
            "recovery",
            {
                "status": "unavailable",
                "method": "unknown",
                "reference": "wrong",
                "retention_policy": None,
            },
        ),
    ],
)
def test_recovery_rejects_snapshot_metadata_disagreement_even_without_external_pin(
    raw, field, value
):
    root, _ = raw
    result = capture(raw)
    manifest = root / result["bundle_ref"] / "manifest.json"
    value_manifest = json.loads(manifest.read_bytes())
    value_manifest["snapshots"][0][field] = value
    manifest.write_text(json.dumps(value_manifest), encoding="utf-8")
    with pytest.raises(SourceError) as caught:
        load_capture(root, result["bundle_ref"])
    assert caught.value.code == "EVIDENCE_INTEGRITY_ERROR"


def test_capture_does_not_overwrite_corrupt_existing_evidence(raw):
    root, _ = raw
    result = capture(raw)
    object_file = root / result["bundle_ref"] / result["members"][0]["object_ref"]
    object_file.write_bytes(b"corrupt")
    with pytest.raises(SourceError):
        capture(raw)
    assert object_file.read_bytes() == b"corrupt"


def test_simultaneous_same_identity_is_explicit_busy_and_never_overwrites(raw, monkeypatch):
    import _shared.sources as sources

    original = sources._recheck
    nested = []
    entering = False

    def reentrant(root, captured):
        nonlocal entering
        original(root, captured)
        if (
            not entering
            and (root / "logs/evidence").exists()
            and list((root / "logs/evidence").glob("*.lock"))
        ):
            entering = True
            with pytest.raises(SourceError) as caught:
                capture_document(root, captured[0]["path"], source_id="synthetic-design")
            nested.append(caught.value.code)

    monkeypatch.setattr(sources, "_recheck", reentrant)
    capture(raw)
    assert nested == ["CAPTURE_BUSY"]


def test_failed_publish_leaves_no_partial_bundle_and_returns_structured_error(raw, monkeypatch):
    root, _ = raw
    original = Path.write_bytes

    def disk_failure(path, data):
        if path.name == "manifest.json":
            raise OSError("synthetic disk write failure")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", disk_failure)
    with pytest.raises(SourceError) as caught:
        capture(raw)
    assert caught.value.code == "EVIDENCE_WRITE_FAILED"
    assert not list((root / "logs/evidence").iterdir())


def make_directory_link(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True
        )
        assert completed.returncode == 0, completed.stderr


def test_raw_junction_to_outside_and_evidence_output_junction_are_rejected(raw, tmp_path):
    root, document = raw
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "doc.md").write_text("external", encoding="utf-8")
    link = root / "docs-raw/specs/external"
    make_directory_link(link, outside)
    with pytest.raises(SourceError) as caught:
        capture_document(root, link / "doc.md", source_id="external")
    assert caught.value.code == "SOURCE_PATH_ESCAPE"
    (root / "logs").mkdir()
    make_directory_link(root / "logs/evidence", outside)
    with pytest.raises(SourceError) as caught:
        capture(raw)
    assert caught.value.code == "EVIDENCE_PATH_ESCAPE"
    assert sorted(path.name for path in outside.iterdir()) == ["doc.md"]
