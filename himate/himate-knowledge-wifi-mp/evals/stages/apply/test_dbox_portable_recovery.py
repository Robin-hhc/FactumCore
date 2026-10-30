"""Behavioral cases; shared synthetic materials live under evals/support."""

from support.stages.apply_portable import (
    base64,
    canonical,
    consumer_pipeline,
    copy,
    document,
    git,
    json,
    one_match,
    pending,
    pytest,
    search,
    sha,
    shutil,
    stop_before_activation,
)


@pytest.mark.parametrize("kind", ["md", "pdf", "docx"])
def test_formal_git_clone_recovers_without_producer_then_rebinds_current_directory(tmp_path, kind):
    pipeline, external, relative, original, locator, source_ref, bundle, request = pending(
        tmp_path / "p", kind)
    publication = pipeline.call("knowledge-apply", request, "batch")["data"]
    assert publication["batch_complete"] is True and publication["activated"] is True
    assert not (pipeline.root / request["view_ref"]).exists()
    ready = pipeline.call("knowledge-apply", {"operation_id": request["operation_id"],
        "publication_ref": publication["publication_ref"]}, "prepare-submission")["data"]
    commit_files = ready["commit_files"]
    assert commit_files == publication["commit_files"]
    assert any(path.startswith("logs/evidence/published/") for path in commit_files)
    assert all(not path.startswith((".build/", "artifacts/", "logs/operations/")) for path in commit_files)
    assert not any("dbox.local.yml" in path for path in commit_files)
    formal_bytes = {path: (pipeline.root / path).read_bytes() for path in commit_files}
    native_path = str(external).replace("\\", "/").casefold()
    for raw in formal_bytes.values():
        assert native_path not in raw.decode(errors="replace").replace("\\\\", "/").casefold()
    workspace = pipeline.root.parent
    expected_paths = {pipeline.root.name + "/" + path for path in commit_files}
    git(workspace, "add", "--", *sorted(expected_paths))
    git(workspace, "commit", "-m", "Exact synthetic dbox publication")
    assert set(git(workspace, "diff", "--name-only", "HEAD^", "HEAD").splitlines()) == expected_paths
    commit = git(workspace, "rev-parse", "HEAD")
    submitted = pipeline.call("knowledge-apply", {"operation_id": request["operation_id"],
        "publication_ref": publication["publication_ref"], "commit_sha": commit}, "verify-submission")
    assert submitted["phase"] == "submitted"
    clone = tmp_path / "c"
    git(tmp_path, "clone", "--no-hardlinks", str(workspace), str(clone))
    consumer = consumer_pipeline(tmp_path / "c-io", clone / pipeline.root.name, pipeline.skills)
    assert git(clone, "rev-parse", "HEAD") == commit
    assert all((consumer.root / path).read_bytes() == raw for path, raw in formal_bytes.items())
    for private in (".build", "artifacts", "logs/operations", "docs-raw/sources/dbox.local.yml",
                    "logs/evidence/objects", "logs/evidence/extractions", "logs/evidence/locators"):
        assert not (consumer.root / private).exists(), private
    assert not (consumer.root / "docs-raw/sources/dbox").exists()
    assert external.resolve().is_relative_to(tmp_path.resolve())
    shutil.rmtree(external)
    assert not external.exists()
    # Make the whole producer knowledge root unavailable, in addition to its source.
    workspace.rename(workspace.with_name("producer-workspace-offline"))
    assert not pipeline.root.exists()
    assert consumer.call("knowledge-lint", {"operation_id": "consumer-lint"})["status"] == "passed"
    built = consumer.call("knowledge-apply", {"operation_id": "consumer-build"}, "index-build")["data"]
    generation = consumer.record(built["generation_ref"])
    assert generation["index_verification"]["complete"] is True
    assert not any(row.get("kind") == "external_raw"
                   for row in generation["input_snapshot"]["current_files"].values())
    verified = consumer.call("knowledge-apply", {"operation_id": "consumer-verify",
        "generation_ref": built["generation_ref"]}, "index-verify")
    assert verified["data"]["verified"] is True
    activated = consumer.call("knowledge-apply", {"operation_id": "consumer-activate",
        "generation_ref": built["generation_ref"], "expected_active": built["expected_active"]}, "index-activate")
    assert activated["data"]["activated"] is True
    historical = search(consumer, "consumer-history-no-config", "historical")
    hit = one_match(historical)
    link = hit["source_links"][0]
    assert historical["generation_ref"] == built["generation_ref"]
    assert link["current"] is None and link["current_source_matches"] is None
    assert link["evidence"]["base"] == "knowledge_root"
    assert link["evidence"]["locator"] == locator and link["evidence"]["sha256"] == sha(original)
    assert (consumer.root / link["evidence"]["path"]).read_bytes() == original
    read = consumer.call("knowledge-query", {"operation_id": "consumer-read-no-config",
        "receipt_ref": historical["receipt_ref"], "card_id": hit["card_id"]}, "read")["data"]
    assert read["generation_ref"] == historical["generation_ref"]
    assert read["card_digest"] == hit["card_digest"] and read["source_links"][0] == link
    assert read["card_digest"] == sha(formal_bytes["knowledge/rules/portable-dbox-rule.md"])
    assert [claim["id"] for claim in read["claims"]] == ["c1"]
    assert "Capture marker is an explicit synthetic rule." in read["claims"][0]["text"]
    one_match(search(consumer, "consumer-guidance-no-config", "guidance"))
    for purpose in ("current", "implementation"):
        assert search(consumer, "consumer-no-config-" + purpose, purpose)["matches"] == []
    recovered = consumer.call("knowledge-source", {"operation_id": "consumer-exact-history",
        "source_ref": source_ref}, "resolve-source")["data"]
    assert recovered["sha256"] == sha(original) and recovered["locator"] == locator
    assert "Capture marker is a documented rule." in recovered["text"]
    assert recovered["current_source_matches"] is None
    status = consumer.call("knowledge-source", {"operation_id": "consumer-status",
        "target_operation_id": request["operation_id"]}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "complete"
    replacement = tmp_path / "消费者 不同目录"
    current = replacement / relative
    current.parent.mkdir(parents=True)
    current.write_bytes(original)
    shared_config = (clone / "config.yml").read_bytes()
    consumer.call("knowledge-source", {"operation_id": "consumer-configure",
        "path": str(replacement)}, "configure")
    scan = consumer.call("knowledge-source", {"operation_id": "consumer-new-scan"}, "scan")["data"]
    inventory = consumer.record(scan["scan_ref"])
    unit = inventory["units"][0]
    assert unit["path"] == "docs-raw/sources/dbox/" + relative
    assert unit["source_id"] == source_ref["source_id"] and unit["change"] == "unchanged"
    assert inventory["current_context"]["config_digest"] == sha(shared_config)
    assert (clone / "config.yml").read_bytes() == shared_config
    prepared = consumer.call("knowledge-source", {"operation_id": "consumer-new-scan",
        "scan_ref": scan["scan_ref"], "unit_ids": [unit["unit_id"]]}, "prepare")["data"]
    new_material = consumer.record(prepared["material_ref"])
    new_bundle = consumer.record(new_material["bundle_ref"])
    assert new_bundle["resources"][0]["source_id"] == source_ref["source_id"]
    assert new_bundle["snapshots"][0]["snapshot_id"] == source_ref["snapshot_id"]
    assert new_bundle["snapshots"][0]["sha256"] == bundle["snapshots"][0]["sha256"]
    for purpose in ("current", "implementation"):
        same = search(consumer, "consumer-same-root-" + purpose, purpose)
        native = one_match(same)["source_links"][0]
        assert native["current"] == {"base": "absolute", "path": str(current),
                                     "sha256": sha(original), "locator": locator}
        assert native["current_source_matches"] is True
    changed, _ = document("md")
    changed = changed.replace(b"documented", b"different-")
    current.write_bytes(changed)
    for purpose in ("current", "implementation"):
        assert search(consumer, "consumer-changed-" + purpose, purpose)["matches"] == []
    historical = search(consumer, "consumer-changed-history", "historical")
    changed_link = one_match(historical)["source_links"][0]
    assert changed_link["evidence"] == link["evidence"]
    assert changed_link["current_source_matches"] is False
    assert changed_link["current"]["path"] == str(current)
    assert changed_link["current"]["sha256"] == sha(changed)
    assert changed_link["current"]["locator"] is None
    exact = consumer.call("knowledge-source", {"operation_id": "consumer-history-after-change",
        "source_ref": source_ref}, "resolve-source")["data"]
    assert exact["sha256"] == sha(original) and exact["current_source_matches"] is False
    assert "Capture marker is a documented rule." in exact["text"]
    assert all((consumer.root / path).read_bytes() == raw for path, raw in formal_bytes.items())
    assert git(clone, "diff", "--name-only", "HEAD") == ""
    (consumer.base / "portable-summary.json").write_text(json.dumps({"kind": kind,
        "formal_commit": commit, "commit_files": commit_files,
        "generation_ref": built["generation_ref"], "source_id": source_ref["source_id"],
        "snapshot_id": source_ref["snapshot_id"], "original_sha256": sha(original),
        "producer_source_removed": True, "producer_workspace_offline": True,
        "consumer_current_rebound": True}, indent=2), encoding="utf-8")


@pytest.mark.parametrize("damage", ["missing-entry", "changed-binding", "extra-entry"])
def test_published_batch_rejects_resealed_private_generation_damage_then_recovers(tmp_path, damage):
    pipeline, _, _, _, _, _, _, request = pending(tmp_path / "p")
    environment, marker = stop_before_activation(tmp_path)
    stopped = pipeline.call("knowledge-apply", request, "batch", expected=2, environment=environment)
    assert marker.read_text(encoding="utf-8") == "stopped after generation and regression"
    assert "SYNTHETIC_PORTABLE_STOP_BEFORE_ACTIVATION" in json.dumps(stopped)
    operation = request["operation_id"]
    publication_ref = f"logs/publications/{operation}/manifest.json"
    manifest = pipeline.record(publication_ref)
    formal = {row["path"]: (pipeline.root / row["path"]).read_bytes() for row in manifest["files"]}
    formal[publication_ref] = (pipeline.root / publication_ref).read_bytes()
    intent = pipeline.root / f".build/operations/{operation}/batch-intent.json"
    intent_bytes = intent.read_bytes()
    build = pipeline.record(f".build/operations/{operation}/batch-build.json")
    generation_path = pipeline.root / build["generation_ref"]
    generation_bytes = generation_path.read_bytes()
    generation = copy.deepcopy(json.loads(generation_bytes))
    snapshot = generation["input_snapshot"]
    current = snapshot["current_files"]
    external_paths = [path for path, value in current.items() if value["kind"] == "external_raw"]
    assert len(external_paths) == 1
    selected = external_paths[0]
    if damage == "missing-entry":
        current.pop(selected)
    elif damage == "changed-binding":
        current[selected]["dbox_binding"]["root_token"] = "0" * 64
    else:
        other = "docs-raw/sources/dbox/not-adopted.md"
        current[other] = {**copy.deepcopy(current[selected]), "path": other}
    # Reseal both layers: test semantic scope/binding validation, not a stale digest.
    snapshot["snapshot_digest"] = sha(canonical({key: value for key, value in snapshot.items()
                                                if key != "snapshot_digest"}))
    generation["digest"] = sha(canonical({key: value for key, value in generation.items() if key != "digest"}))
    damaged_bytes = canonical(generation)
    generation_path.write_bytes(damaged_bytes)
    rejected = pipeline.call("knowledge-apply", {"operation_id": operation}, "batch", expected=2)
    assert any(row["code"] == "EXECUTION_INPUTS_UNAVAILABLE" for row in rejected["diagnostics"]), rejected
    assert not (pipeline.root / "artifacts/indexes/local/active.json").exists()
    assert not (pipeline.root / f"logs/publications/{operation}/completion.json").exists()
    assert intent.read_bytes() == intent_bytes and generation_path.read_bytes() == damaged_bytes
    assert all((pipeline.root / path).read_bytes() == raw for path, raw in formal.items())
    generation_path.write_bytes(generation_bytes)
    resumed = pipeline.call("knowledge-apply", {"operation_id": operation}, "batch")["data"]
    assert resumed["batch_complete"] is True and resumed["activated"] is True
    assert resumed["generation_ref"] == build["generation_ref"]
    assert all((pipeline.root / path).read_bytes() == raw for path, raw in formal.items())
    assert pipeline.record("artifacts/indexes/local/active.json")["generation_ref"] == build["generation_ref"]


def test_formal_lint_rejects_resealed_publication_binding_damage_before_current_card(tmp_path):
    """Current cards cannot mask tampering with the original publication basis."""
    pipeline, external, relative, original, _, _, _, request = pending(tmp_path / "p")
    published = pipeline.call("knowledge-apply", request, "batch")["data"]
    assert published["batch_complete"] is True
    reference = published["publication_ref"]
    path = pipeline.root / reference
    original_manifest_bytes = path.read_bytes()
    original_manifest = json.loads(original_manifest_bytes)
    record_path = pipeline.root / original_manifest["processing_record"]["path"]
    original_record_bytes = record_path.read_bytes()
    record = json.loads(original_record_bytes)
    assert original_manifest["protocol_version"] == record["publication_protocol"] == "1.2"
    assert sha(canonical(original_manifest["content_basis"])) == record["content_digest"]
    assert "acceptance" not in record
    assert record["dispositions"][0]["card_refs"] == ["portable-dbox-rule"]
    card_path = pipeline.root / "knowledge/rules/portable-dbox-rule.md"
    original_card = card_path.read_bytes()
    assert one_match(search(pipeline, "negative-control-current", "current"))["source_links"][0][
        "current_source_matches"] is True
    assert pipeline.call("knowledge-lint", {"operation_id": "negative-control-baseline"})["status"] == "passed"
    expected_codes = {
        "reviewed-view": "RECORD_PUBLICATION_MISMATCH",
        "processing-sha": "RECORD_PUBLICATION_MISMATCH",
        "processing-path": "RECORD_PUBLICATION_MISMATCH",
        "content-digest": "INVALID_PUBLICATION",
        "card-bytes": "FINAL_BYTES_CHANGED",
        "card-identity-resealed": "PUBLICATION_BYTES_CHANGED",
        "basis-identity-resealed": "RECORD_PUBLICATION_MISMATCH",
        "basis-stripped-current": "INVALID_PUBLICATION",
        "basis-stripped-downgrade": "RECORD_PUBLICATION_MISMATCH",
        "target-write-removed": "PUBLICATION_BYTES_CHANGED",
    }
    observations = []
    for damage, expected in expected_codes.items():
        manifest = copy.deepcopy(original_manifest)
        if damage == "reviewed-view":
            manifest["reviewed_view_digest"] = "0" * 64
            manifest["trace"]["view_digest"] = "0" * 64
        elif damage in {"processing-sha", "processing-path"}:
            processing = manifest["processing_record"]
            entry = next(row for row in manifest["files"] if row == processing)
            if damage == "processing-sha":
                # Keep the pointer and its declared file row equal, so the real
                # original record bytes, rather than row equality, reject this.
                processing["sha256"] = entry["sha256"] = "0" * 64
            else:
                processing["path"] = entry["path"] = "logs/ingest/unrelated.yaml"
        elif damage == "content-digest":
            manifest["content_digest"] = "0" * 64
        elif damage.startswith("basis-stripped-"):
            manifest.pop("content_basis")
            if damage == "basis-stripped-downgrade":
                manifest["protocol_version"] = "1.1"
        elif damage == "target-write-removed":
            manifest["published_view"]["writes"] = [row for row in manifest["published_view"]["writes"]
                if row["path"] != "knowledge/rules/portable-dbox-rule.md"]
            manifest["published_view_digest"] = sha(canonical(manifest["published_view"]))
        elif damage in {"card-bytes", "card-identity-resealed", "basis-identity-resealed"}:
            row = next(item for item in manifest["published_view"]["writes"]
                       if item["path"] == "knowledge/rules/portable-dbox-rule.md")
            frozen = base64.b64decode(row["bytes_b64"], validate=True)
            assert frozen == original_card
            changed = frozen.replace(b"explicit synthetic rule", b"explicit altered-- rule") + b"\nTampered body.\n"
            assert changed != frozen and row["final_digest"] == sha(original_card)
            row["bytes_b64"] = base64.b64encode(changed).decode()
            if damage != "card-bytes":
                row["final_digest"] = sha(changed)
                file_row = next(item for item in manifest["files"] if item["path"] == row["path"])
                file_row.update(sha256=sha(changed), bytes=len(changed))
                if damage == "basis-identity-resealed":
                    # Even a fully consistent invented basis cannot replace the
                    # content digest already frozen in the unchanged record.
                    payload = next(item for item in manifest["content_basis"]["payloads"]
                                   if item["path"] == row["path"])
                    payload.update(sha256=sha(changed), bytes=len(changed))
                    manifest["content_digest"] = sha(canonical(manifest["content_basis"]))
            manifest["published_view_digest"] = sha(canonical(manifest["published_view"]))
        manifest["digest"] = sha(canonical({key: value for key, value in manifest.items() if key != "digest"}))
        path.write_bytes(canonical(manifest))
        try:
            failed = pipeline.call("knowledge-lint", {"operation_id": "negative-" + damage}, expected=1)
            codes = {finding["code"] for finding in failed["findings"]}
            assert failed["status"] == "failed" and expected in codes, failed
            assert "RECORD_HISTORY_UNAVAILABLE" not in codes, failed
            assert card_path.read_bytes() == original_card
            assert record_path.read_bytes() == original_record_bytes
            assert (external / relative).read_bytes() == original
            observations.append({"damage": damage, "expected_code": expected,
                                 "actual_codes": sorted(codes), "status": failed["status"]})
        finally:
            path.write_bytes(original_manifest_bytes)
        # Prove each error comes from the one damaged binding, while the same
        # current card and same source snapshot remain present throughout.
        restored = pipeline.call("knowledge-lint", {"operation_id": "restored-" + damage})
        assert restored["status"] == "passed", restored
    assert path.read_bytes() == original_manifest_bytes
    (pipeline.base / "portable-publication-negative-controls.json").write_text(
        json.dumps(observations, indent=2), encoding="utf-8")
