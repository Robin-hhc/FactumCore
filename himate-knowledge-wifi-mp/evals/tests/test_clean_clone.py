"""A consumer receives only committed assets, never a producer's runtime tree."""

import importlib.util
import io
import os
from pathlib import Path
import subprocess

import pytest
import yaml


SPEC = importlib.util.spec_from_file_location(
    "clean_clone_manual", Path(__file__).with_name("test_manual_skills.py")
)
MANUAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MANUAL)


def git(repository, *arguments):
    return subprocess.check_output([
        "git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.autocrlf=false",
        "-c", "user.name=Isolated fixture", "-c", "user.email=fixture@example.invalid",
        "-C", str(repository), *arguments,
    ], stderr=subprocess.STDOUT).decode().strip()


def document_bytes(kind):
    text = "Capture marker is a documented rule."
    if kind == "md":
        return ("# Source\n" + text + "\n").encode(), {"kind": "lines", "start": 1, "end": 2}
    if kind == "docx":
        import docx
        document = docx.Document()
        document.add_paragraph(text)
        stream = io.BytesIO()
        document.save(stream)
        return stream.getvalue(), {"kind": "paragraph", "paragraph": 1}
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=100)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(("BT /F1 12 Tf 10 50 Td (" + text + ") Tj ET").encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue(), {"kind": "page", "page": 1}


@pytest.mark.parametrize("committed_original", [False, True])
@pytest.mark.parametrize("kind", ["md", "pdf", "docx"])
def test_document_ingest_survives_git_clone_without_private_runtime(tmp_path, committed_original, kind):
    p = MANUAL.ManualPipeline(tmp_path / "producer")
    assert not any((p.skills / name).exists() for name in MANUAL.FIXTURE.RETIRED_SKILLS)
    p.catalog_path.unlink()
    (p.root / ".isolated-knowledge-fixture").unlink()
    workspace = p.root.parent
    config = {"schema_version": "2.0", "workspace_id": "clone-fixture",
              "knowledge_roots": {"wifi": p.root.name}, "code_root": "main", "modules": []}
    (workspace / "config.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (workspace / "main").mkdir()
    (workspace / ".gitignore").write_bytes((MANUAL.FIXTURE.REPO / ".gitignore").read_bytes())
    original, locator = document_bytes(kind)
    source_path = "docs-raw/specs/wifi/clone-source." + kind
    p.write(source_path, original)
    git(workspace, "init", "-b", "main")
    if committed_original:
        git(workspace, "add", "config.yml", p.root.name + "/docs-raw")
        git(workspace, "commit", "-m", "Isolated original")
    operation = "clone-ingest"
    scan_ref = p.call("knowledge-source-scan", {"operation_id": operation}, "scan")["data"]["scan_ref"]
    unit = p.record(scan_ref)["units"][0]
    assert unit["path"] == source_path
    material_ref = p.call("knowledge-source-prepare", {"operation_id": operation, "scan_ref": scan_ref},
                          "prepare")["data"]["material_ref"]
    bundle_ref = p.record(material_ref)["bundle_ref"]
    bundle = p.record(bundle_ref)
    _, front, body = p.card("clone-rule", bundle).decode().split("---", 2)
    metadata = yaml.safe_load(front)
    metadata["sources"][0]["locator"] = locator
    card = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
    view_ref = p.view(operation, bundle_ref, "clone-rule", card, scan_ref=scan_ref, material_ref=material_ref)
    p.review(operation, view_ref)
    record_ref = p.call("knowledge-source-scan", {
        "operation_id": operation, "scan_ref": scan_ref, "view_ref": view_ref,
        "disposition_preview_ref": p.record(view_ref)["disposition_preview_ref"],
    }, "record")["data"]["ingest_record_ref"]
    published = p.call("knowledge-apply", {"operation_id": operation, "view_ref": view_ref,
                                            "ingest_record_ref": record_ref}, "batch")
    assert published["phase"] == "completed" and published["data"]["batch_complete"] is True
    assert not (p.root / view_ref).exists()
    ready = p.call("knowledge-apply", {"operation_id": operation,
        "publication_ref": published["data"]["publication_ref"]}, "prepare-submission")["data"]
    assert not any(ref.startswith(".build/") for ref in ready["commit_files"])
    assert any(ref.startswith("logs/evidence/published/") for ref in ready["commit_files"])
    assert "logs/publications/" + operation + "/manifest.json" in ready["commit_files"]
    # Commit the actual formal closure. No producer stage or private cache is
    # copied into the consumer to compensate for a missing publication object.
    git(workspace, "add", ".gitignore", "config.yml", p.root.name + "/governance",
        p.root.name + "/docs-raw", *[p.root.name + "/" + ref for ref in ready["commit_files"]])
    git(workspace, "commit", "-m", "Isolated formal knowledge")
    cloned = tmp_path / "consumer-workspace"
    git(tmp_path, "clone", "--no-hardlinks", str(workspace), str(cloned))
    consumer = MANUAL.ManualPipeline.__new__(MANUAL.ManualPipeline)
    consumer.base = tmp_path / "consumer-io"
    consumer.base.mkdir()
    consumer.root, consumer.skills, consumer.sequence = cloned / p.root.name, p.skills, 0
    assert not any((consumer.skills / name).exists() for name in MANUAL.FIXTURE.RETIRED_SKILLS)
    assert not (consumer.root / ".build").exists()
    assert not (consumer.root / "artifacts").exists()
    assert (consumer.root / "logs/evidence/published").is_dir()
    assert (consumer.root / "logs/publications" / operation / "manifest.json").is_file()
    for cache in ("objects", "checked-code", "extractions", "locators"):
        assert not (consumer.root / "logs/evidence" / cache).exists()
    assert not (consumer.root / "logs/operations").exists()
    assert consumer.call("knowledge-lint", {})["status"] == "passed"
    built = consumer.call("knowledge-index-build", {"operation_id": "consumer-build"})["data"]
    assert consumer.call("knowledge-query-regression", {
        "operation_id": "consumer-regression", "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"],
        "cases": [{"id": "clone", "query": "capture", "required": ["clone-rule"]}],
    })["data"]["activated"]
    found = consumer.call("knowledge-query", {"operation_id": "consumer-search", "query": "capture"}, "search")["data"]
    assert [row["card_id"] for row in found["matches"]] == ["clone-rule"]
    hit = found["matches"][0]
    assert "sources" not in hit
    link = hit["source_links"][0]
    assert link["kind"] == "raw" and link["current"]["base"] == "knowledge_root"
    assert link["current"]["path"] == source_path and link["current"]["locator"] == locator
    assert (consumer.root / hit["card_ref"]).is_file()
    linked = consumer.call("knowledge-source-capture", {
        "operation_id": "consumer-linked-source", "source_ref": metadata["sources"][0],
    }, "resolve-source")["data"]
    assert "Capture marker is a documented rule." in linked["text"]
    assert link["evidence"]["sha256"] == linked["sha256"]
    assert link["evidence"]["locator"] == linked["locator"]
    if link["evidence"]["base"] == "git":
        assert linked["original_ref"] == "git:" + link["evidence"]["commit"] + ":" + link["evidence"]["path"]
    else:
        assert link["evidence"]["base"] == "knowledge_root"
        assert link["evidence"]["path"] == linked["original_ref"]
    read = consumer.call("knowledge-query", {"operation_id": "consumer-read", "card_id": "clone-rule",
                                           "receipt_ref": found["receipt_ref"]}, "read")["data"]
    assert read["card_digest"] == found["matches"][0]["card_digest"]
    assert read["source_links"][0]["current_source_matches"] is True
    assert read["card_ref"] == hit["card_ref"] and read["path"] == hit["path"]
    scan = consumer.call("knowledge-source-scan", {"operation_id": "consumer-scan"}, "scan")["data"]
    assert consumer.record(scan["scan_ref"])["units"][0]["change"] == "unchanged"
    # Formal published objects remain; private source/extraction caches are not
    # silently recreated by ordinary consumption.
    for cache in ("objects", "checked-code", "extractions", "locators"):
        assert not (consumer.root / "logs/evidence" / cache).exists()
    target = consumer.call("knowledge-source-scan", {"operation_id": "consumer-status",
        "target_operation_id": operation}, "status")["data"]["operations"][0]
    assert target["completion"]["status"] == "complete"
    if kind == "md" and not committed_original:
        # A semantic restriction is durable shared state, not disposable logs.
        state = {"schema_version": "2.0", "record_kind": "maintenance_state", "validity_epoch": 1,
                 "blocked_claims": [{"card_id": "clone-rule", "claim_id": "c1", "reason": "semantic_review_required"}]}
        state["digest"] = MANUAL.FIXTURE.sha(MANUAL.FIXTURE.canonical(state))
        consumer.write("logs/events/state.json", MANUAL.FIXTURE.canonical(state))
        git(cloned, "add", consumer.root.name + "/logs/events/state.json")
        git(cloned, "commit", "-m", "Isolated shared semantic restriction")
        restricted_root = tmp_path / "restricted-consumer-workspace"
        git(tmp_path, "clone", "--no-hardlinks", str(cloned), str(restricted_root))
        restricted = MANUAL.ManualPipeline.__new__(MANUAL.ManualPipeline)
        restricted.base = tmp_path / "restricted-consumer-io"
        restricted.base.mkdir()
        restricted.root, restricted.skills, restricted.sequence = restricted_root / consumer.root.name, p.skills, 0
        generation = restricted.call("knowledge-index-build", {"operation_id": "restricted-build"})["data"]
        assert restricted.call("knowledge-query-regression", {
            "operation_id": "restricted-regression", "generation_ref": generation["generation_ref"],
            "expected_active": generation["expected_active"],
            "cases": [{"id": "restricted", "query": "capture", "forbidden": ["clone-rule"]}],
        })["data"]["activated"]
        blocked = restricted.call("knowledge-query", {"operation_id": "restricted-search", "query": "capture"}, "search")["data"]
        assert blocked["matches"] == []
        assert blocked["validity_epoch"] == 1
    (consumer.root / source_path).write_bytes(document_bytes(kind)[0].replace(b"documented", b"modified--") if kind == "md" else b"newer unrelated original")
    git(cloned, "add", consumer.root.name + "/" + source_path)
    git(cloned, "commit", "-m", "Isolated newer original")
    recovered = consumer.call("knowledge-source-capture", {
        "operation_id": "consumer-history", "source_ref": metadata["sources"][0],
    }, "resolve-source")
    assert "Capture marker is a documented rule." in recovered["data"]["text"]
    assert recovered["data"]["current_source_matches"] is False
    assert recovered["data"]["original_ref"].startswith("git:" if committed_original else "logs/evidence/published/")
    stale = consumer.call("knowledge-query", {"operation_id": "consumer-stale", "query": "capture"}, "search")["data"]
    assert stale["matches"] == []
    historical = consumer.call("knowledge-query", {
        "operation_id": "consumer-historical", "query": "capture", "purpose": "historical",
    }, "search")["data"]
    assert historical["matches"][0]["card_id"] == "clone-rule"
    historical_link = historical["matches"][0]["source_links"][0]
    assert historical_link["evidence"]["sha256"] == recovered["data"]["sha256"]
    assert historical_link["evidence"]["locator"] == metadata["sources"][0]["locator"]
    assert historical_link["current_source_matches"] is False
    assert historical_link["current"]["locator"] is None
    if kind == "md" and not committed_original:
        shallow_root = tmp_path / "shallow-consumer-workspace"
        git(tmp_path, "clone", "--depth=1", "--no-local", str(cloned), str(shallow_root))
        shallow = MANUAL.ManualPipeline.__new__(MANUAL.ManualPipeline)
        shallow.base = tmp_path / "shallow-consumer-io"
        shallow.base.mkdir()
        shallow.root, shallow.skills, shallow.sequence = shallow_root / consumer.root.name, p.skills, 0
        retained = shallow.call("knowledge-source-capture", {
            "operation_id": "published-history", "source_ref": metadata["sources"][0],
        }, "resolve-source")
        assert "Capture marker is a documented rule." in retained["data"]["text"]
        assert retained["data"]["current_source_matches"] is False
        # A shallow clone is sufficient while its exact published original is
        # retained. Removing that one formal original exposes the real gap;
        # neither the changed working file nor truncated Git history replaces it.
        original_ref = bundle["snapshots"][0]["recovery"]["path"]
        assert original_ref.startswith("logs/evidence/published/objects/")
        retained_original = shallow.root / original_ref
        assert retained_original.resolve().is_relative_to(shallow.root.resolve())
        retained_original.unlink()
        missing = shallow.call("knowledge-source-capture", {
            "operation_id": "missing-history", "source_ref": metadata["sources"][0],
        }, "resolve-source", expected=2)
        assert missing["diagnostics"][0]["code"] == "SOURCE_INPUT_UNAVAILABLE"


def test_static_code_card_survives_clean_clone_with_configured_module_bytes(tmp_path):
    p = MANUAL.ManualPipeline(tmp_path / "code-producer")
    p.catalog_path.unlink()
    (p.root / ".isolated-knowledge-fixture").unlink()
    workspace = p.root.parent
    config = {"schema_version": "2.0", "workspace_id": "code-clone-fixture",
              "knowledge_roots": {"wifi": p.root.name}, "code_root": "main",
              "modules": [{"path": "wifi", "chips": ["chip12"], "sides": ["host"]}]}
    (workspace / "config.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    module = workspace / "main/wifi"
    module.mkdir(parents=True)
    raw = b"int capture_marker(void) { return 1; }\n"
    (module / "wifi.c").write_bytes(raw)
    repo_id = "repo-" + MANUAL.FIXTURE.sha(b"main/wifi")[:16]
    bundle_ref = p.call("knowledge-source-prepare", {
        "operation_id": "code-clone", "kind": "code", "repo_id": repo_id,
        "relative_path": "wifi.c", "source_id": "clone-code",
    }, "capture")["data"]["bundle_ref"]
    bundle = p.record(bundle_ref)
    _, front, body = p.card("clone-code-rule", bundle, "Capture marker returns the literal one.").decode().split("---", 2)
    metadata = yaml.safe_load(front)
    metadata["review_mode"] = "code_gate"
    scope = {"context_id": "chip12-host-static", "target_id": "chip12-host", "chip": "chip12", "side": "host",
             "build_profile": None, "features_all": [], "features_none": [], "protocol_versions": [],
             "revision_policy": "revalidate"}
    metadata["scope"] = {"applicability": "constrained", "contexts": [scope]}
    metadata["claims"][0].update(evidence_kind="implementation", context_ids=[scope["context_id"]],
                                 verification_requirements=["semantic-support"])
    metadata["sources"][0]["locator"] = {"kind": "lines", "start": 1, "end": 1, "repo_id": repo_id, "path": "wifi.c"}
    metadata["sources"][0]["code_ref"] = {
        "kind": "function", "name": "capture_marker", "scope": [],
        "parameter_types": [], "role": "definition",
    }
    card = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
    view_ref = p.view("code-clone", bundle_ref, "clone-code-rule", card, semantic=False)
    assert p.call("knowledge-apply", {"operation_id": "code-clone", "view_ref": view_ref})["phase"] == "committed"
    (workspace / ".gitignore").write_bytes((MANUAL.FIXTURE.REPO / ".gitignore").read_bytes())
    git(workspace, "init", "-b", "main")
    git(workspace, "add", ".gitignore", "config.yml", p.root.name + "/governance", p.root.name + "/knowledge")
    git(workspace, "commit", "-m", "Isolated static code knowledge")
    cloned = tmp_path / "code-consumer-workspace"
    git(tmp_path, "clone", "--no-hardlinks", str(workspace), str(cloned))
    # Business modules are separately supplied, exactly as config.yml declares.
    destination = cloned / "main/wifi"
    destination.mkdir(parents=True)
    (destination / "wifi.c").write_bytes(raw)
    consumer = MANUAL.ManualPipeline.__new__(MANUAL.ManualPipeline)
    consumer.base = tmp_path / "code-consumer-io"
    consumer.base.mkdir()
    consumer.root, consumer.skills, consumer.sequence = cloned / p.root.name, p.skills, 0
    for path in (".build", "artifacts", "logs/evidence", "logs/operations"):
        assert not (consumer.root / path).exists()
    built = consumer.call("knowledge-index-build", {"operation_id": "consumer-code-build"})["data"]
    target = {"target_id": "chip12-host", "chip": "chip12", "side": "host"}
    assert consumer.call("knowledge-query-regression", {
        "operation_id": "consumer-code-regression", "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"], "cases": [{"id": "static-code", "query": "Capture",
            "purpose": "current", "context": target, "required": ["clone-code-rule"]}],
    })["data"]["activated"]
    found = consumer.call("knowledge-query", {"operation_id": "consumer-code-search", "query": "Capture",
        "purpose": "current", "context": target}, "search")["data"]
    code_link = found["matches"][0]["source_links"][0]
    assert code_link["evidence"] == {"base": "workspace", "path": "main/wifi/wifi.c",
        "locator": {"kind": "lines", "start": 1, "end": 1}, "sha256": MANUAL.FIXTURE.sha(raw)}
    assert code_link["current"]["path"] == "main/wifi/wifi.c"
    assert (cloned / code_link["evidence"]["path"]).read_bytes() == raw
    assert code_link["navigation_status"] == "resolved" and code_link["current_source_matches"] is True
    read = consumer.call("knowledge-query", {"operation_id": "consumer-code-read", "card_id": "clone-code-rule",
        "receipt_ref": found["receipt_ref"]}, "read")["data"]
    assert read["card_digest"] == found["matches"][0]["card_digest"]
    (destination / "wifi.c").write_bytes(b"int capture_marker(void) { return 2; }\n")
    changed = consumer.call("knowledge-query", {"operation_id": "consumer-code-changed", "query": "Capture",
        "purpose": "current", "context": target}, "search")["data"]
    assert changed["matches"] == []
