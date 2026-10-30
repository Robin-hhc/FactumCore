"""Behavioral cases; shared synthetic materials live under evals/support."""

from support.stages.apply_dbox_pipeline import (
    assert_no_private_directory,
    batch,
    copy,
    existing,
    json,
    os,
    pending,
    pytest,
    resume_environment,
    stop_environment,
)


def test_dbox_public_journey_retains_portable_evidence_and_cleans_only_stage(tmp_path):
    pipeline, source, request = pending(tmp_path)
    local = pipeline.root / "docs-raw/sources/dbox.local.yml"
    local_bytes, original = local.read_bytes(), (source / "manual.md").read_bytes()
    result = batch(pipeline, request)
    assert result["data"]["batch_complete"] is True, result
    manifest = pipeline.record(result["data"]["publication_ref"])
    assert manifest["protocol_version"] == "1.2"
    assert [row["path"] for row in manifest["dbox_execution_scope"]] == ["docs-raw/sources/dbox/manual.md"]
    assert all(row.get("kind") != "external_raw" for row in manifest["index_inputs"]["input_snapshot"]["current_files"].values())
    assert local.read_bytes() == local_bytes and (source / "manual.md").read_bytes() == original
    assert not (pipeline.root / request["view_ref"]).exists()
    assert not any("dbox.local.yml" in path for path in result["data"]["commit_files"])
    with pytest.raises(AssertionError, match="private source directory"):
        assert_no_private_directory(json.dumps({"path": str(source)}).encode(), source)
    for path in result["data"]["commit_files"]:
        raw = (pipeline.root / path).read_bytes()
        assert_no_private_directory(raw, source)
    local.unlink()
    assert batch(pipeline, {"operation_id": request["operation_id"]})["data"]["batch_complete"] is True
    status = pipeline.call("knowledge-source", {"operation_id": "status", "target_operation_id": request["operation_id"]}, "status")
    assert status["status"] == "ok"
    lint = pipeline.call("knowledge-lint", {"operation_id": "independent-formal-check"})
    assert lint["status"] == "passed" and lint["data"]["full_scope"] is True
    original_pointer = pipeline.record("artifacts/indexes/local/active.json")
    rebuilt = pipeline.call("knowledge-apply", {"operation_id": "independent-rebuild"}, "index-build")["data"]
    generation = pipeline.record(rebuilt["generation_ref"])
    assert generation["index_verification"]["complete"] is True
    assert all(row.get("kind") != "external_raw" for row in generation["input_snapshot"]["current_files"].values())
    assert rebuilt["expected_active"] == original_pointer["digest"]
    activated = pipeline.call("knowledge-apply", {"operation_id": "independent-activate",
        "generation_ref": rebuilt["generation_ref"], "expected_active": rebuilt["expected_active"]}, "index-activate")
    assert activated["data"]["activated"] is True
    assert not local.exists() and not (pipeline.root / request["view_ref"]).exists()
    query = pipeline.call("knowledge-query", {"operation_id": "historical", "query": "dbox rule", "purpose": "historical"}, "search")
    assert query["data"]["matches"][0]["card_id"] == "dbox-rule"
    assert query["data"]["generation_ref"] == rebuilt["generation_ref"]


@pytest.mark.parametrize("stop", ["build", "activate"])
def test_unfinished_batch_keeps_original_directory_binding(tmp_path, stop):
    pipeline, source, request = pending(tmp_path)
    local = pipeline.root / "docs-raw/sources/dbox.local.yml"
    original_config = local.read_bytes()
    stopped = batch(pipeline, request, environment=stop_environment(tmp_path, stop), expected=2)
    assert stopped["status"] != "ok"
    published = pipeline.root / f"logs/publications/{request['operation_id']}/manifest.json"
    assert published.exists()
    formal = published.read_bytes()
    manifest = pipeline.record(published.relative_to(pipeline.root).as_posix())
    published_files = {row["path"]: (pipeline.root / row["path"]).read_bytes() for row in manifest["files"]}
    intent_ref = f".build/operations/{request['operation_id']}/batch-intent.json"
    intent_bytes = (pipeline.root / intent_ref).read_bytes()
    original_intent = pipeline.record(intent_ref)
    journal = pipeline.record(f".build/operations/{request['operation_id']}/transaction/journal.json")
    assert journal["status"] == "committed"
    built_ref = f".build/operations/{request['operation_id']}/batch-build.json"
    original_generation = pipeline.record(built_ref)["generation_ref"] if stop == "activate" else None
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    (replacement / "manual.md").write_bytes((source / "manual.md").read_bytes())
    pipeline.call("knowledge-source", {"operation_id": "move", "path": str(replacement)}, "configure")
    failed = batch(pipeline, {"operation_id": request["operation_id"]}, expected=2)
    assert failed["status"] != "ok"
    assert published.read_bytes() == formal
    assert not (pipeline.root / "artifacts/indexes/local/active.json").exists()
    assert (pipeline.root / intent_ref).read_bytes() == intent_bytes
    pipeline.call("knowledge-source", {"operation_id": "restore-original", "path": str(source)}, "configure")
    assert local.read_bytes() == original_config
    assert (pipeline.root / intent_ref).read_bytes() == intent_bytes
    environment, marker = resume_environment(tmp_path)
    resumed = batch(pipeline, {"operation_id": request["operation_id"]}, environment=environment)
    assert marker.read_text(encoding="utf-8") == "loaded"
    assert resumed["data"]["batch_complete"] is True and resumed["data"]["activated"] is True
    assert resumed["data"]["expected_active"] == original_intent["expected_active"]
    assert published.read_bytes() == formal
    assert published_files == {ref: (pipeline.root / ref).read_bytes() for ref in published_files}
    if original_generation is not None:
        assert resumed["data"]["generation_ref"] == original_generation
    pointer = pipeline.record("artifacts/indexes/local/active.json")
    assert pointer["generation_ref"] == resumed["data"]["generation_ref"]
    assert pointer["previous_active_digest"] == original_intent["expected_active"]
    completion = pipeline.record(f"logs/publications/{request['operation_id']}/completion.json")
    assert completion["retrieval"]["complete"] is True and completion["cleanup"]["status"] == "done"
    assert not (pipeline.root / request["view_ref"]).exists()


def test_dbox_cleanup_pending_retry_after_directory_change_only_cleans_owned_files(tmp_path):
    pipeline, source, request = pending(tmp_path)
    operation = request["operation_id"]
    retained_ref = f".build/operations/{operation}/unregistered.txt"
    pipeline.write(retained_ref, b"Unregistered scratch must remain\n")
    probe = tmp_path / "probe-cleanup-denial"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text('''from pathlib import Path
original = Path.unlink
def denied(path, *args, **kwargs):
    if path.as_posix().endswith(SUFFIX):
        raise PermissionError("SYNTHETIC_DBOX_EXACT_CLEANUP_DENIAL")
    return original(path, *args, **kwargs)
Path.unlink = denied
'''.replace("SUFFIX", repr("/" + request["view_ref"])), encoding="utf-8")
    failed = batch(pipeline, request, environment={**os.environ, "PYTHONPATH": str(probe)})
    assert failed["data"]["published"] is True and failed["data"]["batch_complete"] is False
    assert failed["data"]["cleanup"]["status"] == "cleanup_pending"
    assert {row["path"] for row in failed["data"]["cleanup"]["failed"]} == {request["view_ref"]}
    completion_ref = f"logs/publications/{operation}/completion.json"
    before = pipeline.record(completion_ref)
    assert before["retrieval"]["complete"] is True
    publication = pipeline.root / failed["data"]["publication_ref"]
    formal = publication.read_bytes()
    manifest = pipeline.record(failed["data"]["publication_ref"])
    published_files = {row["path"]: (pipeline.root / row["path"]).read_bytes() for row in manifest["files"]}
    index_files = {path.relative_to(pipeline.root).as_posix(): path.read_bytes()
                   for path in (pipeline.root / "artifacts/indexes").rglob("*") if path.is_file()}
    replacement = tmp_path / "different-directory-after-retrieval"
    replacement.mkdir()
    (replacement / "manual.md").write_bytes(b"# Later current bytes are unrelated to completed retrieval\n")
    original_source = (source / "manual.md").read_bytes()
    pipeline.call("knowledge-source", {"operation_id": "move-after-retrieval", "path": str(replacement)}, "configure")
    configured = (pipeline.root / "docs-raw/sources/dbox.local.yml").read_bytes()
    environment, marker = resume_environment(tmp_path, cleanup_only=True)
    retried = batch(pipeline, {"operation_id": operation}, environment=environment)
    assert marker.read_text(encoding="utf-8") == "loaded"
    assert retried["data"]["batch_complete"] is True and retried["data"]["cleanup"]["status"] == "done"
    assert not (pipeline.root / request["view_ref"]).exists()
    assert (pipeline.root / retained_ref).read_bytes() == b"Unregistered scratch must remain\n"
    assert publication.read_bytes() == formal
    assert published_files == {ref: (pipeline.root / ref).read_bytes() for ref in published_files}
    assert index_files == {path.relative_to(pipeline.root).as_posix(): path.read_bytes()
                           for path in (pipeline.root / "artifacts/indexes").rglob("*") if path.is_file()}
    after = pipeline.record(completion_ref)
    assert after["retrieval"] == before["retrieval"] and after["data"] == before["data"]
    assert (pipeline.root / "docs-raw/sources/dbox.local.yml").read_bytes() == configured
    assert (source / "manual.md").read_bytes() == original_source
    assert (replacement / "manual.md").read_bytes() == b"# Later current bytes are unrelated to completed retrieval\n"


def test_missing_execution_intent_cannot_silently_finish_published_batch(tmp_path):
    pipeline, _, request = pending(tmp_path)
    batch(pipeline, request, environment=stop_environment(tmp_path, "build"), expected=2)
    (pipeline.root / f".build/operations/{request['operation_id']}/batch-intent.json").unlink()
    failed = batch(pipeline, {"operation_id": request["operation_id"]}, expected=2)
    assert any(row["code"] == "EXECUTION_INPUTS_UNAVAILABLE" for row in failed["diagnostics"])
    assert not (pipeline.root / "artifacts/indexes/local/active.json").exists()


def test_legacy_run_rejects_dbox_before_writing(tmp_path):
    pipeline, _, request = pending(tmp_path)
    failed = batch(pipeline, request, action="run", expected=2)
    assert "EXTERNAL_LEGACY_APPLY_UNSUPPORTED" in json.dumps(failed)
    assert not (pipeline.root / "knowledge/rules/dbox-rule.md").exists()


def test_empty_public_scope_cannot_bypass_retained_execution_bindings(tmp_path):
    pipeline, _, request = pending(tmp_path)
    batch(pipeline, request, environment=stop_environment(tmp_path, "build"), expected=2)
    ref = f"logs/publications/{request['operation_id']}/manifest.json"
    manifest = copy.deepcopy(pipeline.record(ref))
    manifest["dbox_execution_scope"] = []
    manifest = existing.P7.HELPER.load_contract("records").seal(manifest)
    pipeline.write(ref, existing.P7.HELPER.canonical(manifest))
    failed = batch(pipeline, {"operation_id": request["operation_id"]}, expected=2)
    assert any(row["code"] == "EXECUTION_INPUTS_UNAVAILABLE" for row in failed["diagnostics"])
    assert not (pipeline.root / "artifacts/indexes/local/active.json").exists()
