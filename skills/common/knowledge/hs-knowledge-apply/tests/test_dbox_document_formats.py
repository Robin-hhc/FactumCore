"""Real-format dbox journeys against a pinned, separately installed release."""

import hashlib
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest
import yaml


RELEASE = "f8a84153a1ce4c23082f70d7de55a2c1f65523f8"
DBOX = "docs-raw/sources/dbox"
CLAIM = "Capture marker is a documented rule."


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@pytest.fixture(scope="session")
def release_runtime(tmp_path_factory):
    checkout = os.environ.get("HIMATE_DBOX_RELEASE_CHECKOUT")
    manifest = {}
    if checkout:
        root = Path(checkout).resolve(strict=True)
        manifest_path = Path(os.environ.get("HIMATE_DBOX_RELEASE_MANIFEST", str(root.parent / "release-manifest.json")))
        manifest = json.loads(manifest_path.read_bytes())
        assert manifest.get("commit", manifest.get("baseline")) == RELEASE
        assert all(sha((root / ref).read_bytes()) == expected for ref, expected in manifest["files"].items())
    else:
        # Normal acceptance exercises this checkout; explicit audit runs may
        # select a separately frozen release with the environment above.
        root = Path(__file__).resolve().parents[5]
        manifest = {"revision": "current_checkout"}
    spec = importlib.util.spec_from_file_location("dbox_formats_head_manual",
        root / "himate-knowledge-wifi-mp/evals/tests/test_manual_skills.py")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    lock_bytes = (root / "himate-knowledge-wifi-mp/governance/framework.lock.yaml").read_bytes()
    identity = {"base_commit": RELEASE, "tool_version": yaml.safe_load(lock_bytes)["tool_version"],
                "rules_sha256": sha(lock_bytes), "revision": manifest.get("revision", "head")}
    if manifest.get("rules_sha256"):
        assert identity["rules_sha256"] == manifest["rules_sha256"]
    return root, module, identity


@pytest.fixture
def pipeline(tmp_path, release_runtime):
    release, manual, identity = release_runtime

    class AuditedPipeline(manual.ManualPipeline):
        def call(self, slug, request, action=None, expected=0):
            slug, request, action = manual.FIXTURE.target_call(slug, request, action)
            self.sequence += 1
            incoming = self.base / f"format-in-{self.sequence}.json"
            outgoing = self.base / f"format-out-{self.sequence}.json"
            incoming.write_bytes(json_bytes(request))
            script = self.skills / ("hs-" + slug) / "scripts/cli.py"
            assert script.read_bytes() == (release / "skills/common/knowledge" / ("hs-" + slug) / "scripts/cli.py").read_bytes()
            command = [sys.executable, str(script), "--input", str(incoming), "--output", str(outgoing),
                       "--knowledge-root", str(self.root)]
            if action:
                command += ["--action", action]
            started = time.perf_counter()
            process = subprocess.run(command, capture_output=True, timeout=180)
            elapsed = time.perf_counter() - started
            response = json.loads(outgoing.read_bytes()) if outgoing.exists() else {}
            stdout = self.base / f"format-stdout-{self.sequence}.txt"
            stderr = self.base / f"format-stderr-{self.sequence}.txt"
            stdout.write_bytes(process.stdout)
            stderr.write_bytes(process.stderr)
            self.audit.append({"release": self.release_identity, "skill": "hs-" + slug, "action": action,
                "input": incoming.name, "output": outgoing.name, "returncode": process.returncode,
                "seconds": elapsed, "status": response.get("status"), "phase": response.get("phase"),
                "diagnostics": response.get("diagnostics", []), "stderr": stderr.name})
            (self.base / "cli-audit.json").write_bytes(json_bytes({"release": self.release_identity, "calls": self.audit,
                "seconds": sum(row["seconds"] for row in self.audit)}))
            assert process.returncode == expected, (response, process.stderr.decode(errors="replace"))
            assert response.get("rules_digest") == self.release_identity["rules_sha256"]
            return response

    result = AuditedPipeline(tmp_path)
    result.audit = []
    result.release_identity = identity
    assert result.skills.parent == tmp_path and result.skills.name == "installed-skills"
    assert (result.root / "governance/framework.lock.yaml").read_bytes() == (release / "himate-knowledge-wifi-mp/governance/framework.lock.yaml").read_bytes()
    return result


def primary_card(pipeline, bundle, logical, card_id, locator):
    resource = next(row for row in bundle["resources"] if row["path"] == logical)
    actual = next(row for row in bundle["snapshots"] if row["source_id"] == resource["source_id"])
    # Select an actual captured snapshot for card authoring; never modify the
    # immutable bundle's format, extraction identity, bytes or native locators.
    card = pipeline.card(card_id, {"snapshots": [actual]}, text=CLAIM)
    _, front, body = card.decode().split("---", 2)
    metadata = yaml.safe_load(front)
    metadata["sources"][0]["locator"] = locator
    return ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---" + body).encode(), metadata


def no_private_path(raw, directory):
    decoded = raw.decode("utf-8", errors="replace")
    values = [decoded]
    serialized = [decoded]
    if decoded.startswith("---") and len(decoded.split("---", 2)) == 3:
        serialized.append(decoded.split("---", 2)[1])
    for text in serialized:
        for parser in (json.loads, yaml.safe_load):
            try:
                pending = [parser(text)]
            except (ValueError, yaml.YAMLError):
                continue
            while pending:
                value = pending.pop()
                if isinstance(value, str):
                    values.append(value)
                elif isinstance(value, dict):
                    pending.extend(value.keys())
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)
    private = re.sub(r"[\\/]+", "/", str(directory)).casefold()
    assert all(private not in re.sub(r"[\\/]+", "/", value).casefold() for value in values)


def document_bytes(kind):
    if kind == "md":
        return "md", ("# Source\n" + CLAIM + "\n").encode(), {"kind": "lines", "start": 1, "end": 2}
    if kind == "txt":
        return "txt", b"\xef\xbb\xbf# Source\r\n" + CLAIM.encode() + b"\r\n", {"kind": "lines", "start": 1, "end": 2}
    if kind.startswith("docx"):
        import docx
        document = docx.Document()
        document.add_heading("Synthetic format source", level=1)
        if kind == "docx-table":
            table = document.add_table(rows=1, cols=2)
            table.cell(0, 0).text = CLAIM
            table.cell(0, 1).text = "Explicit table evidence"
            locator = {"kind": "table_row", "table": 1, "row": 1}
        else:
            document.add_paragraph(CLAIM)
            locator = {"kind": "paragraph", "paragraph": 2}
        stream = io.BytesIO()
        document.save(stream)
        assert stream.getvalue().startswith(b"PK\x03\x04")
        return "docx", stream.getvalue(), locator
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    for text in ("Synthetic context page", CLAIM):
        page = writer.add_blank_page(width=300, height=100)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(("BT /F1 12 Tf 10 50 Td (" + text + ") Tj ET").encode())
        page[NameObject("/Contents")] = writer._add_object(content)
    stream = io.BytesIO()
    writer.write(stream)
    assert stream.getvalue().startswith(b"%PDF-")
    return "pdf", stream.getvalue(), {"kind": "page", "page": 2}


@pytest.mark.parametrize("kind", ["md", "txt", "pdf", "docx", "docx-table"])
def test_actual_document_format_completes_ingest_query_read_and_cleanup(pipeline, tmp_path, kind):
    source = tmp_path / "external originals"
    source.mkdir()
    extension, original, locator = document_bytes(kind)
    child = source / ("source." + extension)
    child.write_bytes(original)
    before = (child.stat().st_ino, child.stat().st_size, child.stat().st_mtime_ns, child.read_bytes())
    logical = DBOX + "/" + child.name
    pipeline.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
    pipeline.call("knowledge-source", {"operation_id": "configure", "path": str(source)}, "configure")
    operation, card_id = "format-ingest", "format-" + kind + "-rule"
    prepared = pipeline.call("knowledge-source", {"operation_id": operation}, "run")
    assert prepared["phase"] == "prepared"
    scan_ref, material_ref = prepared["data"]["scan_ref"], prepared["data"]["material_ref"]
    scan = pipeline.record(scan_ref)
    assert scan["complete"] is True
    assert [row["path"] for row in scan["units"]] == [logical]
    bundle_ref = pipeline.record(material_ref)["bundle_ref"]
    bundle = pipeline.record(bundle_ref)
    card, metadata = primary_card(pipeline, bundle, logical, card_id, locator)
    view = pipeline.view(operation, bundle_ref, card_id, card, scan_ref=scan_ref, material_ref=material_ref)
    pipeline.review(operation, view)
    record_ref = pipeline.pending_record(operation, view)
    applied = pipeline.call("knowledge-apply", {"operation_id": operation, "view_ref": view,
                                               "ingest_record_ref": record_ref}, "batch")
    assert applied["phase"] == "completed" and applied["data"]["batch_complete"] is True
    assert applied["data"]["cleanup"]["status"] == "done"
    assert not (pipeline.root / view).exists() and not (pipeline.root / material_ref).exists()
    lock = yaml.safe_load((pipeline.root / "governance/sources.lock.yaml").read_bytes())
    resource = next(row for row in lock["resources"] if row["path"] == logical)
    snapshot = next(row for row in lock["snapshots"] if row["source_id"] == resource["source_id"])
    assert snapshot["format"] == "." + extension and snapshot["sha256"] == sha(original) and snapshot["bytes"] == len(original)
    retained = pipeline.root / snapshot["recovery"]["path"]
    assert retained.read_bytes() == original
    resolved = pipeline.call("knowledge-source", {"operation_id": "resolve-format", "source_ref": metadata["sources"][0]}, "resolve-source")["data"]
    assert resolved["sha256"] == sha(original) and resolved["locator"] == locator and CLAIM in resolved["text"]
    found = pipeline.call("knowledge-query", {"operation_id": "find-format", "query": card_id.replace("-", " ")}, "search")["data"]
    assert [row["card_id"] for row in found["matches"]] == [card_id]
    hit = found["matches"][0]
    assert hit["source_links"][0]["current"]["base"] == "absolute"
    assert hit["source_links"][0]["current"]["path"] == str(child)
    assert hit["source_links"][0]["evidence"]["locator"] == locator
    read = pipeline.call("knowledge-query", {"operation_id": "read-format", "card_id": card_id,
                                             "receipt_ref": found["receipt_ref"]}, "read")["data"]
    assert read["card_digest"] == hit["card_digest"] and read["generation_ref"] == found["generation_ref"]
    assert read["source_links"][0]["evidence"]["locator"] == locator
    assert (child.stat().st_ino, child.stat().st_size, child.stat().st_mtime_ns, child.read_bytes()) == before
    for ref in applied["data"]["commit_files"]:
        assert "dbox.local.yml" not in ref
        no_private_path((pipeline.root / ref).read_bytes(), source)
    (tmp_path / "case-evidence.json").write_bytes(json_bytes({"release": pipeline.release_identity, "format": kind,
        "logical_path": logical, "source_sha256": sha(original), "bytes": len(original), "locator": locator,
        "publication_ref": applied["data"]["publication_ref"], "generation_ref": found["generation_ref"],
        "cli_calls": len(pipeline.audit), "cli_seconds": sum(row["seconds"] for row in pipeline.audit)}))


def test_chinese_nested_markdown_and_relative_image_attachment_complete_ingest(pipeline, tmp_path):
    source = tmp_path / "外部 资料"
    child = source / "第一层 组" / "第二层 设计" / "说明 文档.md"
    attachment = source / "附件 图.png"
    child.parent.mkdir(parents=True)
    child.write_text("# 文档\n" + CLAIM + "\n![Attachment](<../../附件 图.png>)\n", encoding="utf-8")
    attachment.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+Y4a8AAAAASUVORK5CYII="))
    before = {path.relative_to(source).as_posix(): (path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes())
              for path in (child, attachment)}
    logical = DBOX + "/第一层 组/第二层 设计/说明 文档.md"
    attachment_logical = DBOX + "/附件 图.png"
    pipeline.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
    pipeline.call("knowledge-source", {"operation_id": "configure", "path": str(source)}, "configure")
    local_bytes = (pipeline.root / "docs-raw/sources/dbox.local.yml").read_bytes()
    operation = "nested-attachment"
    selected_folder = DBOX + "/第一层 组"
    prepared = pipeline.call("knowledge-source", {"operation_id": operation, "source": selected_folder,
                                                  "collect_local_attachments": True}, "run")
    assert prepared["phase"] == "prepared"
    scan_ref, material_ref = prepared["data"]["scan_ref"], prepared["data"]["material_ref"]
    inventory = pipeline.record(scan_ref)
    assert inventory["scope"] == [selected_folder] and inventory["complete"] is True
    assert [row["path"] for row in inventory["units"]] == [logical]
    material = pipeline.record(material_ref)
    assert any(row["code"] == "EXTRACTION_LIMITATION" and "not interpreted" in row["reason"] for row in material["gaps"])
    bundle_ref, locator = material["bundle_ref"], {"kind": "lines", "start": 1, "end": 2}
    bundle = pipeline.record(bundle_ref)
    assert {row["path"]: row["kind"] for row in bundle["resources"]} == {logical: "raw", attachment_logical: "attachment"}
    card, metadata = primary_card(pipeline, bundle, logical, "nested-attachment-rule", locator)
    view = pipeline.view(operation, bundle_ref, "nested-attachment-rule", card, scan_ref=scan_ref, material_ref=material_ref)
    pipeline.review(operation, view)
    record_ref = pipeline.pending_record(operation, view)
    applied = pipeline.call("knowledge-apply", {"operation_id": operation, "view_ref": view,
                                               "ingest_record_ref": record_ref}, "batch")
    assert applied["data"]["batch_complete"] is True and applied["data"]["cleanup"]["status"] == "done"
    assert not (pipeline.root / view).exists() and not (pipeline.root / material_ref).exists()
    lock = yaml.safe_load((pipeline.root / "governance/sources.lock.yaml").read_bytes())
    assert {row["path"] for row in lock["resources"]} == {logical, attachment_logical}
    for resource in lock["resources"]:
        snapshot = next(row for row in lock["snapshots"] if row["source_id"] == resource["source_id"])
        original = child.read_bytes() if resource["path"] == logical else attachment.read_bytes()
        assert snapshot["sha256"] == sha(original)
        assert (pipeline.root / snapshot["recovery"]["path"]).read_bytes() == original
        if resource["kind"] == "attachment":
            assert snapshot["format"] == ".png" and "extraction" not in snapshot
            opaque = pipeline.call("knowledge-source", {"operation_id": "read-opaque", "source_ref": {
                "source_id": resource["source_id"], "snapshot_id": snapshot["snapshot_id"], "locator": {}}}, "resolve-source")["data"]
            assert opaque["text"] is None and base64.b64decode(opaque["bytes_b64"]) == original
    resolved = pipeline.call("knowledge-source", {"operation_id": "read-nested", "source_ref": metadata["sources"][0]}, "resolve-source")["data"]
    assert resolved["locator"] == locator and CLAIM in resolved["text"]
    found = pipeline.call("knowledge-query", {"operation_id": "find-nested", "query": "nested attachment rule"}, "search")["data"]
    assert [row["card_id"] for row in found["matches"]] == ["nested-attachment-rule"]
    assert found["matches"][0]["source_links"][0]["current"]["path"] == str(child)
    read = pipeline.call("knowledge-query", {"operation_id": "read-nested-card", "card_id": "nested-attachment-rule",
                                             "receipt_ref": found["receipt_ref"]}, "read")["data"]
    assert read["card_digest"] == found["matches"][0]["card_digest"] and read["generation_ref"] == found["generation_ref"]
    assert (pipeline.root / "docs-raw/sources/dbox.local.yml").read_bytes() == local_bytes
    assert before == {path.relative_to(source).as_posix(): (path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes())
                      for path in (child, attachment)}
    with pytest.raises(AssertionError):
        no_private_path(json.dumps({"path": str(source)}, ensure_ascii=True).encode(), source)
    for ref in applied["data"]["commit_files"]:
        assert "dbox.local.yml" not in ref
        no_private_path((pipeline.root / ref).read_bytes(), source)
    (tmp_path / "case-evidence.json").write_bytes(json_bytes({"release": pipeline.release_identity, "format": "md+png",
        "logical_path": logical, "attachment": attachment_logical, "locator": locator,
        "source_sha256": sha(child.read_bytes()), "attachment_sha256": sha(attachment.read_bytes()),
        "publication_ref": applied["data"]["publication_ref"], "generation_ref": found["generation_ref"],
        "cli_calls": len(pipeline.audit), "cli_seconds": sum(row["seconds"] for row in pipeline.audit)}))


def invalid_document(kind):
    if kind == "unsupported-csv":
        return "csv", b"column,value\ncapture,marker\n", 2, "UNSUPPORTED_DOCUMENT_FORMAT", "UNSUPPORTED_DOCUMENT_FORMAT"
    if kind == "empty-text":
        return "txt", b"", 2, "UNREADABLE_DOCUMENT", "UNREADABLE_DOCUMENT"
    if kind == "invalid-utf8":
        return "txt", b"\xff\xfe\x00broken UTF8", 2, "UNREADABLE_DOCUMENT", "UNREADABLE_DOCUMENT"
    if kind == "broken-docx":
        return "docx", b"This is not a ZIP document container", 2, "UNREADABLE_DOCUMENT", "UNREADABLE_DOCUMENT"
    if kind == "broken-pdf":
        return "pdf", b"%PDF-1.7\nInvalid synthetic PDF contents\n%%EOF", 2, "UNREADABLE_DOCUMENT", "UNREADABLE_DOCUMENT"
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=100)
    if kind == "encrypted-pdf":
        writer.encrypt("synthetic-test-password")
        code, expected = "ENCRYPTED_DOCUMENT", 2
    else:
        code, expected = "PARTIAL_DOCUMENT", 3
    stream = io.BytesIO()
    writer.write(stream)
    return "pdf", stream.getvalue(), expected, code, code


@pytest.mark.parametrize("kind", ["unsupported-csv", "empty-text", "invalid-utf8", "broken-docx",
                                  "broken-pdf", "blank-pdf", "encrypted-pdf"])
def test_unsupported_or_unreadable_documents_keep_explicit_gaps_without_publication(pipeline, tmp_path, kind):
    source = tmp_path / "unreadable synthetic originals"
    source.mkdir()
    extension, raw, capture_exit, capture_code, material_code = invalid_document(kind)
    child = source / ("source." + extension)
    child.write_bytes(raw)
    logical = DBOX + "/" + child.name
    baseline = (pipeline.root / "governance/sources.lock.yaml").read_bytes()
    before = child.stat().st_mtime_ns, child.read_bytes()
    pipeline.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
    pipeline.call("knowledge-source", {"operation_id": "configure", "path": str(source)}, "configure")
    scan = pipeline.call("knowledge-source", {"operation_id": "invalid-observation", "source": logical}, "scan")
    inventory = pipeline.record(scan["data"]["scan_ref"])
    assert inventory["complete"] is True and inventory["units"][0]["observed_fingerprint"] == sha(raw)
    failed = pipeline.call("knowledge-source", {"operation_id": "invalid-capture", "source_id": "invalid-format",
        "source_path": logical}, "capture", expected=capture_exit)
    assert failed["diagnostics"][0]["code"] == capture_code
    assert failed["phase"] in {"invalid", "blocked"} and "bundle_ref" not in failed["data"]
    prepared = pipeline.call("knowledge-source", {"operation_id": "invalid-observation", "scan_ref": scan["data"]["scan_ref"],
        "tolerate_source_errors": True}, "prepare")
    assert prepared["phase"] == "prepared"
    material = pipeline.record(prepared["data"]["material_ref"])
    assert any(row["code"] == "CURRENT_ORIGINAL_UNAVAILABLE" and row.get("error_code") == material_code
               and row["path"] == logical for row in material["gaps"])
    assert pipeline.record(material["bundle_ref"])["snapshots"] == []
    assert (pipeline.root / "governance/sources.lock.yaml").read_bytes() == baseline
    assert not (pipeline.root / "logs/publications").exists()
    assert not (pipeline.root / "artifacts/indexes/local/active.json").exists()
    assert (child.stat().st_mtime_ns, child.read_bytes()) == before
    (tmp_path / "case-evidence.json").write_bytes(json_bytes({"release": pipeline.release_identity, "format": kind,
        "logical_path": logical, "source_sha256": sha(raw), "capture_diagnostics": failed["diagnostics"],
        "material_gaps": material["gaps"], "published": False, "cli_calls": len(pipeline.audit),
        "cli_seconds": sum(row["seconds"] for row in pipeline.audit)}))
