"""Behavioral cases; shared synthetic materials live under evals/support."""

from support.stages.apply_formats import (
    CLAIM,
    DBOX,
    base64,
    document_bytes,
    invalid_document,
    json,
    json_bytes,
    no_private_path,
    primary_card,
    pytest,
    sha,
    yaml,
)


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
