"""Behavioral cases; shared synthetic materials live under evals/support."""

import base64
import json
import os
from unittest.mock import patch
import pathlib
import tempfile
import yaml
from support.stages.lint_code import (
    canonical,
    digest,
    seal,
    PublicCodeGateTests as _PublicCodeGateTestsFixture,
)


class PublicCodeGateTests(_PublicCodeGateTestsFixture):
    def test_cleanup_rejects_changed_target_outside_its_scratch_root(self):
        owned = self.workspace
        with tempfile.TemporaryDirectory(prefix="cleanup-control-", dir=str(self._fixture_scratch.parent)) as control:
            try:
                # Even a future guard regression can touch only this empty,
                # separately owned control directory, never the scratch root.
                self.workspace = pathlib.Path(control)
                with self.assertRaisesRegex(RuntimeError, "escaped"):
                    self.cleanup_fixture()
            finally:
                self.workspace = owned

    def test_committed_code_capture_reaches_v3_apply_index_and_target_queries(self):
        self.prepare_committed_code_publication()

    def test_mixed_view_applies_with_its_own_checks_without_upstream_proofs(self):
        original = base64.b64decode(self.view["writes"][0]["bytes_b64"]).decode()
        _, front, body = original.split("---", 2)
        meta = yaml.safe_load(front)
        meta.update(id="fixture-document", title="Fixture document", review_mode="manual_document",
                    scope={"applicability": "unknown", "contexts": []})
        meta["sources"] = [{"evidence_ref": "doc", "source_id": "fixture-document", "snapshot_id": "document-v1",
                            "locator": {"kind": "lines", "start": 1, "end": 1}}]
        meta["claims"][0].update(evidence_kind="design", usage="guidance", context_ids=[], source_refs=["doc"], verification_requirements=[])
        document = ("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body.replace("The fixture function returns one.", "Synthetic document requirement.")).encode()
        raw = b"Synthetic document requirement.\n"
        object_ref = "logs/evidence/objects/" + digest(raw) + ".bin"
        for ref in ("docs-raw/specs/document.md", object_ref):
            path = self.root / ref
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        registry = json.loads(base64.b64decode(self.view["writes"][1]["bytes_b64"]))
        registry["resources"].append({"source_id": "fixture-document", "kind": "raw", "path": "docs-raw/specs/document.md"})
        registry["snapshots"].append({"source_id": "fixture-document", "snapshot_id": "document-v1", "sha256": digest(raw),
                                     "bytes": len(raw), "recovery": {"method": "evidence_object", "path": object_ref}})
        registry_bytes = canonical(registry)
        (self.root / "governance/sources.lock.yaml").write_bytes(registry_bytes)
        self.view["writes"][1].update(expected_old_digest=digest(registry_bytes), final_digest=digest(registry_bytes),
                                      bytes_b64=base64.b64encode(registry_bytes).decode())
        self.view["writes"].append({"path": "knowledge/flows/fixture-document.md", "expected_old_digest": None,
                                     "final_digest": digest(document), "bytes_b64": base64.b64encode(document).decode()})
        index = next(row for row in self.view["writes"] if row["path"] == "knowledge/flows/index.md")
        navigation = base64.b64decode(index["bytes_b64"]) + b"[Fixture document](fixture-document.md)\n"
        index.update(final_digest=digest(navigation), bytes_b64=base64.b64encode(navigation).decode())
        snapshots = sorted(registry["snapshots"], key=lambda item: item["snapshot_id"])
        self.view.update(source_refs=snapshots, source_set_digest=digest(snapshots))
        self.view.update(rules_digest=self.rules_digest, review_mode="mixed",
                         review_requirements={"manual_document": ["knowledge/flows/fixture-document.md"], "code_gate": ["knowledge/flows/fixture-code-flow.md"]},
                         baseline_digest=digest({"files": {r["path"]: r["expected_old_digest"] for r in self.view["writes"]}}))
        plan = self.record("change_plan", bundle_ref=".build/operations/op/fixture-bundle.json",
                           bundle_digest="0" * 64, candidate_ids=["document", "code"], decisions=[],
                           writes=self.view["writes"], deletes=[], baseline={}, review_mode="mixed")
        self.save(self.view["plan_ref"], plan)
        self.view["plan_digest"] = plan["digest"]
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        self.sign_report("local")
        self.catalog_path.write_bytes(canonical(self.catalog))
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        applied = self.invoke("hs-knowledge-apply", request={"operation_id": "op", "view_ref": self.view_ref,
                              "workflow": {"attempt_id": "ignored"}})
        self.assertEqual(applied["phase"], "committed")

    def test_review_report_only_changes_current_operation_staging(self):
        def formal():
            return {p.relative_to(self.root).as_posix(): digest(p.read_bytes())
                    for p in self.root.rglob("*") if p.is_file()
                    and not p.relative_to(self.root).as_posix().startswith(".build/")}
        before = formal()
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        self.assertTrue(checked["data"]["local_check_ref"].startswith(".build/operations/op/"))
        self.assertEqual(formal(), before)

    def test_signed_positive_support_then_apply_and_verify(self):
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        request = {
            "operation_id": "op",
            "view_ref": self.view_ref,
            "proof_ref": checked["data"]["local_check_ref"],
        }
        verified = self.invoke(action="verify-proof", request=request)
        self.assertTrue(verified["data"]["proof_verified"])
        before = self.code.joinpath("src/wifi.c").read_bytes()
        applied = self.invoke(skill="hs-knowledge-apply", request=request)
        self.assertEqual(applied["data"]["transaction_status"], "committed")
        self.assertEqual(self.code.joinpath("src/wifi.c").read_bytes(), before)

    def test_independent_agent_review_needs_no_registered_key_or_signature(self):
        self.catalog.pop("semantic_reviewers", None)
        self.catalog_path.write_bytes(canonical(self.catalog))
        report = json.loads((self.root / self.report_ref).read_bytes())
        report.pop("signature_b64", None)
        report["reviewer_id"] = "fixture-independent-reviewer"
        report["payload"].update(author_id="fixture", independent_context="fresh-code-reading-context", findings=[])
        report["payload"]["claims"][0]["reason"] = "Read the exact function body and verified its return value."
        self.save(self.report_ref, report)
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        proof = json.loads((self.root / checked["data"]["local_check_ref"]).read_bytes())
        self.assertEqual(proof["verification_tier"], "agent_content_review")

    def test_manual_check_uses_project_config_without_catalog_or_workflow_metadata(self):
        checked = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref,
            "context_ref": self.context_ref, "semantic_report_ref": self.report_ref,
            "workflow": "managed-by-openflow"}, use_catalog=False)
        self.assertEqual(checked["data"]["check_status"], "passed")
        self.assertNotIn("artifact_manifest_ref", checked["data"])

    def test_agent_review_rejects_unresolved_findings_and_missing_claim_reasons(self):
        self.catalog.pop("semantic_reviewers", None)
        self.catalog_path.write_bytes(canonical(self.catalog))
        baseline = json.loads((self.root / self.report_ref).read_bytes())
        baseline.pop("signature_b64", None)
        baseline["reviewer_id"] = "fixture-independent-reviewer"
        baseline["payload"].update(author_id="fixture", independent_context="fresh-context", findings=[])
        baseline["payload"]["claims"][0]["reason"] = "Read the actual return statement."
        for defect, message in (("findings", "findings"), ("reason", "reason")):
            with self.subTest(defect=defect):
                report = json.loads(json.dumps(baseline))
                if defect == "findings":
                    report["payload"]["findings"] = [{"reason": "Unresolved source contradiction"}]
                else:
                    report["payload"]["claims"][0]["reason"] = ""
                self.save(self.report_ref, report)
                result = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref,
                    "semantic_report_ref": self.report_ref,
                    "workflow": {"run_id": "review-guards", "node_id": "local_check", "attempt_id": defect}})
                self.assertIn(result["data"]["check_status"], {"incomplete", "failed"})
                record = json.loads((self.root / result["data"]["local_check_ref"]).read_bytes())
                self.assertIn(message, " ".join(record["gaps"]))

    def test_report_author_roles_are_not_checked_by_the_code_business_skill(self):
        row = self.view["writes"][0]
        _, front, body = base64.b64decode(row["bytes_b64"]).decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata.update(id="fixture-document", owner="document-author", review_mode="manual_document")
        raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        document_path = "knowledge/flows/fixture-document.md"
        self.view["writes"].append({"path": document_path, "expected_old_digest": None,
            "final_digest": digest(raw), "bytes_b64": base64.b64encode(raw).decode()})
        self.view.update(review_mode="mixed", review_requirements={
            "code_gate": [row["path"]], "manual_document": [document_path]},
            baseline_digest=digest({"files": {item["path"]: item["expected_old_digest"] for item in self.view["writes"]}}))
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        self.sign_report("local")
        report = json.loads((self.root / self.report_ref).read_bytes())
        report["reviewer_id"] = "document-author"
        self.save(self.report_ref, report)
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")

    def test_report_needs_no_author_identity_or_independent_context_declaration(self):
        report = json.loads((self.root / self.report_ref).read_bytes())
        report["payload"].pop("author_id")
        report["payload"].pop("independent_context")
        report.pop("reviewer_id")
        self.save(self.report_ref, report)
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")

    def test_source_analysis_without_target_or_build_is_admitted_and_reverified(self):
        self.source_analysis_view()
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        proof_ref = checked["data"]["local_check_ref"]
        proof = json.loads((self.root / proof_ref).read_bytes())
        self.assertEqual(proof["code_identity"]["basis"], "source")
        self.assertIsNone(proof["code_identity"]["target"])
        request = {"operation_id": "op", "view_ref": self.view_ref, "proof_ref": proof_ref}
        applied = self.invoke(skill="hs-knowledge-apply", request=request)
        self.assertEqual(applied["data"]["transaction_status"], "committed")
        verified = self.invoke(action="verify-proof", request={**request, "purpose": "historical"})
        self.assertTrue(verified["data"]["proof_verified"])
        self.code.joinpath("src/wifi.c").write_bytes(b"changed source\n")
        self.invoke(action="verify-proof", request=request, expected=3)

    def test_source_analysis_with_registered_target_does_not_require_build_artifacts(self):
        self.source_analysis_view(usage="guidance", with_target=True)
        self.assertEqual(self.invoke()["data"]["check_status"], "passed")

    def test_current_static_source_claim_does_not_require_build_artifacts(self):
        context = json.loads((self.root / self.context_ref).read_bytes())
        context.pop("build_evidence")
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "passed")

    def test_current_static_source_still_requires_target_conditions(self):
        context = json.loads((self.root / self.context_ref).read_bytes())
        context.pop("build_evidence")
        context["target"].pop("features")
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "incomplete")

    def test_current_static_source_still_requires_actual_target_code_mapping(self):
        config_path = self.workspace / "config.yml"
        config = yaml.safe_load(config_path.read_bytes())
        config["targets"][0].update(module_roots=[], source_bindings=[])
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        context = json.loads((self.root / self.context_ref).read_bytes())
        context.pop("build_evidence")
        context["config_digest"] = digest(config_path.read_bytes())
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "incomplete")

    def test_build_requirement_needs_signed_per_claim_artifact_support(self):
        row = self.view["writes"][0]
        _, front, body = base64.b64decode(row["bytes_b64"]).decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["claims"][0]["verification_requirements"] = ["semantic-support", "build-support"]
        raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        row.update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_signed_build_and_runtime_artifacts_are_checked_without_running_builds(self):
        runtime_ref = "logs/evidence/runtime.log"
        runtime = b"synthetic fixture runtime observation only\n"
        (self.root / runtime_ref).write_bytes(runtime)
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["build_evidence"]["artifacts"].append({"path": runtime_ref, "sha256": digest(runtime)})
        self.save(self.context_ref, seal(context))
        row = self.view["writes"][0]
        _, front, body = base64.b64decode(row["bytes_b64"]).decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["claims"][0]["verification_requirements"] = ["build-support", "runtime-support"]
        raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        row.update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        self.evidence[0]["verification_evidence"] = [
            {"requirement": "build-support", "path": "logs/evidence/build.bin",
             "sha256": digest(b"synthetic fixture build only\n")},
            {"requirement": "runtime-support", "path": runtime_ref, "sha256": digest(runtime)},
        ]
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "passed")
        (self.root / "logs/evidence/build.bin").write_bytes(b"changed build evidence\n")
        checked = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref,
            "semantic_report_ref": self.report_ref,
            "workflow": {"run_id": "artifact-check", "node_id": "local_check", "attempt_id": "changed-artifact"}})
        self.assertEqual(checked["data"]["check_status"], "incomplete")

    def test_current_claim_cannot_use_source_analysis_admission(self):
        self.source_analysis_view(usage="current")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_source_analysis_does_not_ignore_supplied_broken_build_evidence(self):
        self.source_analysis_view(with_target=True)
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["build_evidence"] = {"artifacts": []}
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_source_analysis_checks_conditions_of_a_supplied_build(self):
        original = json.loads((self.root / self.context_ref).read_bytes())
        self.source_analysis_view(with_target=True)
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["build_evidence"] = original["build_evidence"]
        context["target"]["features"] = []
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_code_gate_rechecks_authorized_git_with_a_different_owner(self):
        # Only ownership is simulated; Git objects, signatures and public calls
        # retain the existing explicitly synthetic fixture tier.
        with patch.dict(os.environ, {"GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}):
            checked = self.invoke()
            self.assertEqual(checked["data"]["check_status"], "passed")
            verified = self.invoke(action="verify-proof", request={"operation_id": "op", "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"]})
            self.assertTrue(verified["data"]["proof_verified"])

    def test_missing_signed_support_stays_incomplete(self):
        result = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref})
        self.assertEqual(result["data"]["check_status"], "incomplete")

    def test_official_context_receipt_state_and_location_are_supported(self):
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["state"] = "context_loaded"
        self.context_ref = ".build/project-context/fixture.json"
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "passed")

    def test_actual_git_origin_must_match_registered_identity(self):
        self.git("remote", "set-url", "origin", "different-fixture-repository")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_interrupted_apply_can_roll_back_after_code_revision_changes(self):
        self.catalog["test_fixture_root"] = str(self.root)
        self.catalog_path.write_bytes(canonical(self.catalog))
        checked = self.invoke()
        before_lock = (self.root / "governance/sources.lock.yaml").read_bytes()
        self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "op",
                "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"],
                "fault_after": 1,
            },
            expected=3,
        )
        self.assertTrue((self.root / "knowledge/flows/fixture-code-flow.md").is_file())
        self.code.joinpath("src/wifi.c").write_bytes(b"changed latest fixture code\n")
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "changed during recovery",
        )
        self.invoke(
            skill="hs-knowledge-apply",
            action="resume",
            request={"operation_id": "op"},
            expected=3,
        )
        recovered = self.invoke(
            skill="hs-knowledge-apply",
            action="rollback",
            request={"operation_id": "op"},
        )
        self.assertEqual(recovered["data"]["transaction_status"], "rolled_back")
        self.assertFalse((self.root / "knowledge/flows/fixture-code-flow.md").exists())
        self.assertEqual(
            (self.root / "governance/sources.lock.yaml").read_bytes(), before_lock
        )

    def test_tampered_signed_support_fails(self):
        report = json.loads((self.root / self.report_ref).read_text(encoding="utf-8"))
        report["payload"]["claims"][0]["status"] = "unsupported"
        self.save(self.report_ref, report)
        self.assertEqual(self.invoke()["data"]["check_status"], "failed")

    def test_latest_merge_ref_invalidates_stale_context_without_repairs(self):
        self.code.joinpath("src/wifi.c").write_bytes(
            b"int fixture_wifi_ready(void) { return 2; }\n"
        )
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "new latest",
        )
        view_before = (self.root / self.view_ref).read_bytes()
        lock_before = (self.root / "governance/sources.lock.yaml").read_bytes()
        self.assertEqual(
            self.invoke(action="merge")["data"]["check_status"], "incomplete"
        )
        self.assertEqual((self.root / self.view_ref).read_bytes(), view_before)
        self.assertEqual(
            (self.root / "governance/sources.lock.yaml").read_bytes(), lock_before
        )

    def test_independent_check_does_not_rebind_a_card_to_new_source_fingerprints(self):
        checked = self.invoke()
        applied = self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "op",
                "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"],
            },
        )
        card_path = "knowledge/flows/fixture-code-flow.md"
        card_digest = digest((self.root / card_path).read_bytes())
        newer = b"/* a harmless fixture comment */\n" + self.source
        self.code.joinpath("src/wifi.c").write_bytes(newer)
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "latest fixture comment",
        )
        latest = self.git("rev-parse", "HEAD").decode().strip()
        context = json.loads((self.root / self.context_ref).read_text(encoding="utf-8"))
        context["repos"]["wifi-code"].update(
            head=latest, files={"src/wifi.c": digest(newer)}
        )
        context["target"]["revision"] = latest
        context["build_evidence"]["source_revision"] = latest
        self.context_ref = ".build/operations/op/latest-context.json"
        self.save(self.context_ref, seal(context))
        self.evidence[0]["evidence"][0]["checked_snapshot"] = {
            "repo_id": "wifi-code",
            "path": "src/wifi.c",
            "sha256": digest(newer),
            "snapshot_id": "latest-check-snapshot",
            "locator": {"kind": "lines", "start": 2, "end": 2},
            "commit": latest,
            "bytes": len(newer),
        }
        self.report_ref = ".build/operations/op/latest-report.json"
        self.sign_report("merge")
        frozen = {
            ref: (self.root / ref).read_bytes()
            for ref in (
                self.view_ref,
                "governance/sources.lock.yaml",
                "logs/evidence/code.bin",
            )
        }
        result = self.invoke(skill="hs-knowledge-merge-check")
        self.assertEqual(result["data"]["check_status"], "passed")
        for ref, raw in frozen.items():
            self.assertEqual((self.root / ref).read_bytes(), raw)
        proof = json.loads((self.root / result["data"]["merge_check_ref"]).read_bytes())
        checked = next(row for row in proof["staged_objects"] if row["kind"] == "checked-code")
        self.assertEqual((self.root / checked["stage_ref"]).read_bytes(), newer)
        self.assertFalse((self.root / checked["final_ref"]).exists())
        qualification = {
            "operation_id": "op",
            "apply_result_ref": applied["data"]["apply_result_ref"],
            "current_code_proof_ref": result["data"]["merge_check_ref"],
            "card_path": card_path,
            "card_digest": card_digest,
        }
        self.invoke(skill="hs-knowledge-apply", action="verify-result", request=qualification, expected=3)
        self.code.joinpath("src/wifi.c").write_bytes(b"/* another change */\n" + newer)
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "a later unchecked commit",
        )
        self.invoke(
            skill="hs-knowledge-apply",
            action="verify-result",
            request=qualification,
            expected=3,
        )
        (self.root / card_path).write_bytes(b"a later working-tree replacement")
        history = self.invoke(
            skill="hs-knowledge-apply",
            action="verify-result",
            request={**qualification, "purpose": "historical"},
        )
        self.assertEqual(history["data"]["eligible_files"], [])
        self.assertEqual(
            history["data"]["historical_files"],
            [{"path": card_path, "sha256": card_digest}],
        )

    def test_historical_purpose_cannot_bypass_current_apply_gate(self):
        checked = self.invoke()
        self.code.joinpath("src/wifi.c").write_bytes(
            b"int fixture_wifi_ready(void) { return 2; }\n"
        )
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "changed before apply",
        )
        self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "op",
                "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"],
                "purpose": "historical",
            },
            expected=3,
        )
        self.assertFalse((self.root / "knowledge/flows/fixture-code-flow.md").exists())

    def test_signed_retirement_applies_without_claiming_obsolete_code_is_current(self):
        checked = self.invoke()
        self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "op",
                "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"],
            },
        )
        card_path = "knowledge/flows/fixture-code-flow.md"
        old_card = (self.root / card_path).read_bytes()
        self.code.joinpath("src/wifi.c").write_bytes(
            b"int fixture_wifi_ready(void) { return 2; }\n"
        )
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "obsolete fixture behavior",
        )
        latest = self.git("rev-parse", "HEAD").decode().strip()
        context = json.loads((self.root / self.context_ref).read_text(encoding="utf-8"))
        context["operation_id"] = "retire"
        context["repos"]["wifi-code"].update(
            head=latest,
            files={"src/wifi.c": digest(self.code.joinpath("src/wifi.c").read_bytes())},
        )
        context["target"]["revision"] = latest
        context["build_evidence"]["source_revision"] = latest
        self.context_ref = ".build/operations/retire/context.json"
        self.save(self.context_ref, seal(context))
        _, front, body = old_card.decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata.update(
            lifecycle="deprecated",
            replacement=[],
            deprecation_reason="Fixture implementation no longer returns one",
        )
        tombstone = (
            "---\n"
            + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
            + "---"
            + body
        ).encode()
        self.assertTrue(tombstone.endswith(body.encode()))
        writes = [
            {
                "path": card_path,
                "expected_old_digest": digest(old_card),
                "final_digest": digest(tombstone),
                "bytes_b64": base64.b64encode(tombstone).decode(),
            }
        ]
        view = dict(self.view)
        view.update(
            operation_id="retire",
            writes=writes,
            context_ref=self.context_ref,
            baseline_digest=digest({"files": {card_path: digest(old_card)}}),
        )
        self.view = seal(view)
        self.view_ref = ".build/operations/retire/view.json"
        self.save(self.view_ref, self.view)
        self.evidence[0].update(
            status="retired", reason=metadata["deprecation_reason"], replacement=[]
        )
        self.report_ref = ".build/operations/retire/semantic-report.json"
        self.sign_report("local")
        request = {
            "operation_id": "retire",
            "view_ref": self.view_ref,
            "semantic_report_ref": self.report_ref,
        }
        retired = self.invoke(request=request)
        self.assertEqual(retired["data"]["check_status"], "passed")
        proof_ref = retired["data"]["local_check_ref"]
        proof = json.loads((self.root / proof_ref).read_text(encoding="utf-8"))
        self.assertEqual(proof["claims"][0]["status"], "retired")
        applied = self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "retire",
                "view_ref": self.view_ref,
                "proof_ref": proof_ref,
            },
        )
        self.assertEqual((self.root / card_path).read_bytes(), tombstone)
        qualified = self.invoke(
            skill="hs-knowledge-apply",
            action="verify-result",
            request={
                "operation_id": "retire",
                "apply_result_ref": applied["data"]["apply_result_ref"],
            },
        )
        self.assertEqual(qualified["data"]["eligible_files"], [])
        self.assertEqual(
            qualified["data"]["historical_files"],
            [{"path": card_path, "sha256": digest(tombstone)}],
        )
