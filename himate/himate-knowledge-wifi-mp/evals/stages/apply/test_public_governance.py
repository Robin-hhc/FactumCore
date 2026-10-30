"""Behavioral cases; shared synthetic materials live under evals/support."""

from support.stages.apply_governance import (
    base64,
    canonical,
    digest,
    importlib,
    json,
    marshal,
    pathlib,
    seal,
    struct,
    subprocess,
    PublicGovernanceTests as _PublicGovernanceTestsFixture,
)


class PublicGovernanceTests(_PublicGovernanceTestsFixture):
    def test_new_record_only_batch_skips_only_unrelated_old_terminal_liveness(self):
        for status in ("committed", "rolled_back"):
            with self.subTest(status=status):
                old = self.save_foreign_journal(status=status)
                before = old.read_bytes()
                request = self.record_only_request("facts-" + status.replace("_", "-"))
                result = self.invoke("hs-knowledge-apply", request)
                self.assertEqual(result["phase"], "committed")
                self.assertEqual(old.read_bytes(), before)
                self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")

    def test_old_rules_nonterminal_journal_keeps_the_writer_barrier(self):
        for number, status in enumerate(("prepared", "installing", "recovery_required", "unknown-terminal")):
            with self.subTest(status=status):
                old = self.save_foreign_journal(status=status)
                before = old.read_bytes()
                request = self.record_only_request("pending-facts-" + str(number))
                result = self.invoke("hs-knowledge-apply", request, expected=3)
                self.assertIn("requires recovery", result["diagnostics"][0]["message"])
                self.assertFalse((self.root / "logs/ingest" / (request["operation_id"] + ".yaml")).exists())
                self.assertEqual(old.read_bytes(), before)

    def test_old_terminal_journal_requires_valid_seal_supported_schema_and_identity(self):
        variants = [("seal", {}), ("schema", {"schema_version": "3.0"}),
                    ("operation", {"operation_id": "different-directory"}),
                    ("kind", {"record_kind": "apply_result"}), ("rules", {"rules_digest": "unknown"}),
                    ("shape", {"entries": {}})]
        for name, changes in variants:
            with self.subTest(name=name):
                old = self.save_foreign_journal(**changes)
                if name == "seal":
                    value = json.loads(old.read_bytes())
                    value["digest"] = "0" * 64
                    old.write_bytes(canonical(value))
                before = old.read_bytes()
                request = self.record_only_request("bad-old-" + name)
                result = self.invoke("hs-knowledge-apply", request, expected=2)
                self.assertEqual(result["phase"], "invalid")
                self.assertFalse((self.root / "logs/ingest" / (request["operation_id"] + ".yaml")).exists())
                self.assertEqual(old.read_bytes(), before)

    def test_same_operation_old_rules_journal_cannot_be_read_or_resumed_under_new_rules(self):
        old = self.save_foreign_journal()
        before = old.read_bytes()
        request = self.record_only_request("legacy")
        for action in ("run", "inspect", "resume", "rollback"):
            with self.subTest(action=action):
                result = self.invoke("hs-knowledge-apply", request, action=action, expected=2)
                self.assertIn("record rules identity mismatch", result["diagnostics"][0]["message"])
                self.assertEqual(old.read_bytes(), before)
        self.assertFalse((self.root / "logs/ingest/legacy.yaml").exists())

    def test_apply_does_not_certify_optional_review_authorship(self):
        request = self.prepare_reviewed("new-forged-proof")
        old = self.save_foreign_journal()
        frozen = old.read_bytes()
        proof_path = self.root / request["proof_ref"]
        proof = json.loads(proof_path.read_bytes())
        proof["reviewer_id"] = proof["author_id"]
        proof_path.write_bytes(canonical(seal(proof)))
        result = self.invoke("hs-knowledge-apply", request)
        applied = json.loads((self.root / result["data"]["apply_result_ref"]).read_bytes())
        self.assertEqual(applied["verification_tier"], "fixed_business_checks")
        self.assertEqual(old.read_bytes(), frozen)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"new navigation")

    def test_old_terminal_journal_does_not_accept_an_old_rules_current_proof(self):
        request = self.prepare_reviewed("new-old-proof")
        old = self.save_foreign_journal()
        frozen = old.read_bytes()
        proof_path = self.root / request["proof_ref"]
        proof = json.loads(proof_path.read_bytes())
        proof["rules_digest"] = "a" * 64
        proof_path.write_bytes(canonical(seal(proof)))
        result = self.invoke("hs-knowledge-apply", request, expected=2)
        self.assertIn("record rules identity mismatch", result["diagnostics"][0]["message"])
        self.assertEqual(old.read_bytes(), frozen)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")

    def test_old_terminal_journal_does_not_accept_an_invalid_new_view(self):
        request = self.prepare_reviewed("new-invalid-view")
        old = self.save_foreign_journal()
        frozen = old.read_bytes()
        view_path = self.root / request["view_ref"]
        view = json.loads(view_path.read_bytes())
        view["operation_id"] = "other-view-owner"
        view_path.write_bytes(canonical(seal(view)))
        result = self.invoke("hs-knowledge-apply", request, expected=2)
        self.assertIn("view identity", result["diagnostics"][0]["message"])
        self.assertEqual(old.read_bytes(), frozen)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")

    def test_handoff_describes_files_without_a_target_query_pass_gate(self):
        request = self.prepare_reviewed("gate")
        applied = self.invoke("hs-knowledge-apply", request)
        result = self.invoke("hs-knowledge-publish-handoff", {"operation_id": "gate", "v3_required": True,
                             "apply_result_ref": applied["data"]["apply_result_ref"]})
        self.assertEqual(result["phase"], "ready_to_submit")
        handoff = json.loads((self.root / result["data"]["publish_handoff_ref"]).read_bytes())
        self.assertEqual(handoff["commit_files"], ["knowledge/index.md"])
        self.assertNotIn("verification_tier", handoff)

    def test_record_only_batch_applies_shared_failure_fact_without_card_writes(self):
        common = {"schema_version": "2.0", "operation_id": "facts", "rules_digest": self.rules_digest,
                  "tool_identity": {"skill": "hs-fixture", "package_digest": "0" * 64,
                                    "runtime": "fixture", "requirements_digest": "0" * 64}}
        scan = seal({**common, "record_kind": "source_inventory", "scope": ["docs-raw/specs"],
                     "full_scan": True, "complete": False,
                     "units": [{"unit_id": "u1", "path": "docs-raw/specs/missing.md", "source_id": "source",
                                "observed_fingerprint": None, "previous_fingerprint": None, "change": "added",
                                "read_error": "unreadable", "progress": "blocked"}]})
        record = seal({**common, "record_kind": "ingest_record", "record_id": "facts",
                       "target_path": "logs/ingest/facts.yaml", "batch_kind": "record_only",
                       "scan_ref": ".build/operations/facts/scan.json", "scan_digest": scan["digest"],
                       "inventory": scan, "progress": {}, "dispositions": [{"unit_id": "u1", "action": "failed",
                       "reason": "unreadable", "observed_fingerprint": None, "adopted_fingerprint": None,
                       "progress": "blocked", "card_refs": [], "claim_refs": []}]})
        parent = self.root / ".build/operations/facts"
        parent.mkdir(parents=True)
        (parent / "record.yaml").write_bytes(canonical(record))
        before = (self.root / "knowledge/index.md").read_bytes()
        result = self.invoke("hs-knowledge-apply", {"operation_id": "facts", "v3_required": True,
                             "ingest_record_ref": ".build/operations/facts/record.yaml"})
        self.assertEqual(result["phase"], "committed")
        saved = json.loads((self.root / "logs/ingest/facts.yaml").read_bytes())
        self.assertEqual(saved["dispositions"][0]["progress"], "blocked")
        self.assertEqual(saved["progress"]["apply"]["status"], "recorded")
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), before)
        ready = self.invoke("hs-knowledge-publish-handoff", {"operation_id": "facts", "v3_required": True,
                            "apply_result_ref": result["data"]["apply_result_ref"]})
        self.assertEqual(ready["phase"], "record_only_ready")
        self.assertEqual(ready["data"]["commit_files"], ["logs/ingest/facts.yaml"])
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "add", "--", "logs/ingest/facts.yaml"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "record fact"], check=True, capture_output=True)
        commit = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        submitted = self.invoke("hs-knowledge-publish-handoff", {"operation_id": "facts", "v3_required": True,
                                "apply_result_ref": result["data"]["apply_result_ref"], "commit_sha": commit}, action="verify-submission")
        self.assertEqual(submitted["phase"], "submitted")
        self.assertEqual(submitted["data"]["commit_sha"], commit)

    def test_optional_review_does_not_require_an_upstream_plan_chain(self):
        request = self.prepare_reviewed("missing-plan-binding")
        path = self.root / request["content_review_ref"]
        review = json.loads(path.read_bytes())
        review.pop("plan_ref")
        path.write_bytes(canonical(seal(review)))
        self.invoke("hs-knowledge-apply", request)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"new navigation")

    def test_non_v3_document_runs_full_checks_before_admission(self):
        request = self.prepare_reviewed("invalid-full-view")
        view_path = self.root / request["view_ref"]
        view = json.loads(view_path.read_bytes())
        raw = b"[Broken navigation](absent.md)\n"
        view["writes"][0].update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        plan_path = self.root / view["plan_ref"]
        plan = json.loads(plan_path.read_bytes())
        plan["writes"] = view["writes"]
        plan = seal(plan)
        plan_path.write_bytes(canonical(plan))
        view["plan_digest"] = plan["digest"]
        view = seal(view)
        view_path.write_bytes(canonical(view))
        review_path = self.root / request["content_review_ref"]
        review = json.loads(review_path.read_bytes())
        review.update(view_digest=view["digest"], plan_digest=plan["digest"])
        review_path.write_bytes(canonical(seal(review)))
        request.pop("proof_ref")
        request.pop("content_review_ref")
        result = self.invoke("hs-knowledge-apply", request, expected=3)
        self.assertIn("full-view checks", result["diagnostics"][0]["message"])
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")
        self.assertFalse((self.root / ".build/operations/invalid-full-view/transaction/journal.json").exists())

    def test_non_v3_document_requires_exact_source_recovery_before_first_write(self):
        request = self.prepare_reviewed("unrecoverable", include_card=True)
        (self.root / self.fixture_original_ref).write_bytes(b"altered original")
        self.invoke("hs-knowledge-apply", request, expected=3)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")
        self.assertFalse((self.root / "knowledge/flows/fixture-flow.md").exists())

    def test_workflow_metadata_does_not_create_skill_handoff_manifests(self):
        workflow = {"run_id": "fixture-run", "node_id": "apply_view", "attempt_id": "first"}
        request = self.prepare_reviewed("workflow")
        applied = self.invoke("hs-knowledge-apply", {**request, "workflow": workflow})
        manifest_path = self.root / "logs/workflows/fixture-run/nodes/apply_view/first/result.json"
        self.assertFalse(manifest_path.exists())
        self.assertNotIn("artifact_manifest_ref", applied["data"])
        result_ref = applied["data"]["apply_result_ref"]
        self.assertEqual(json.loads((self.root / result_ref).read_bytes())["status"], "committed")

    def test_public_review_apply_verify_publish(self):
        request = self.prepare_reviewed("public")
        applied = self.invoke("hs-knowledge-apply", request)
        self.assertEqual(
            self.root.joinpath("knowledge/index.md").read_bytes(), b"new navigation"
        )
        # A committed transaction remains verifiable from its own exact bytes
        # even after optional upstream review material has disappeared.
        (self.root / request["proof_ref"]).unlink()
        verify_request = {
            "operation_id": "public",
            "apply_result_ref": applied["data"]["apply_result_ref"],
        }
        verified = self.invoke(
            "hs-knowledge-apply", verify_request, action="verify-result"
        )
        self.assertTrue(verified["data"]["result_verified"])
        handoff = self.invoke("hs-knowledge-publish-handoff", verify_request)
        record = json.loads(
            (self.root / handoff["data"]["publish_handoff_ref"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(record["git_merge_verified"])
        self.assertFalse(record["remote_push_verified"])
        self.assertNotIn("verification_tier", record)
        self.assertEqual(record["write_manifest"], [{"path": "knowledge/index.md", "sha256": digest(b"new navigation")}])

    def test_public_recover_delegates_to_single_apply_engine(self):
        request = self.prepare_reviewed("recover")
        self.invoke("hs-knowledge-apply", {**request, "fault_after": 1}, expected=3)
        inspected = self.invoke(
            "hs-knowledge-recover",
            {
                "operation_id": "recover",
                "workflow": {
                    "run_id": "recover-run",
                    "node_id": "recover_transaction",
                    "attempt_id": "inspect1",
                },
            },
            action="inspect",
        )
        self.assertEqual(inspected["data"]["transaction_status"], "recovery_required")
        resumed = self.invoke(
            "hs-knowledge-recover",
            {
                "operation_id": "recover",
                "workflow": {
                    "run_id": "recover-run",
                    "node_id": "recover_transaction",
                    "attempt_id": "resume1",
                },
            },
            action="resume",
        )
        self.assertEqual(resumed["data"]["transaction_status"], "committed")

    def test_workflow_metadata_is_ignored_by_apply(self):
        request = self.prepare_reviewed("workflow-metadata")
        request.pop("proof_ref")
        request.pop("content_review_ref")
        for workflow in ({"attempt_id": "partial"}, {}, None, []):
            result = self.invoke("hs-knowledge-apply", {**request, "workflow": workflow})
            self.assertEqual(result["data"]["transaction_status"], "committed")
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"new navigation")

    def test_manual_card_apply_needs_no_upstream_proofs(self):
        request = self.prepare_reviewed("manual-card", include_card=True)
        request.pop("proof_ref")
        request.pop("content_review_ref")
        result = self.invoke("hs-knowledge-apply", request)
        applied = json.loads((self.root / result["data"]["apply_result_ref"]).read_bytes())
        self.assertEqual(applied["verification_tier"], "fixed_business_checks")
        self.assertNotIn("proof_ref", applied)
        self.assertNotIn("proof_digest", applied)
        self.assertTrue((self.root / "knowledge/flows/fixture-flow.md").is_file())

    def test_manual_apply_still_rejects_malformed_card_before_writing(self):
        request = self.prepare_reviewed("manual-bad-card", include_card=True)
        request.pop("proof_ref")
        request.pop("content_review_ref")
        path = self.root / request["view_ref"]
        view = json.loads(path.read_bytes())
        for row in view["writes"]:
            if row["path"] == "knowledge/flows/fixture-flow.md":
                raw = b"# Missing required card frontmatter\n"
                row.update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        path.write_bytes(canonical(seal(view)))
        self.invoke("hs-knowledge-apply", request, expected=2)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")
        self.assertFalse((self.root / "knowledge/flows/fixture-flow.md").exists())
        self.assertFalse((self.root / ".build/operations/manual-bad-card/transaction/journal.json").exists())

    def test_card_eligibility_ignores_unrelated_navigation_and_source_append(self):
        request = self.prepare_reviewed("card", include_card=True)
        applied = self.invoke("hs-knowledge-apply", request)
        path = "knowledge/flows/fixture-flow.md"
        card_digest = digest((self.root / path).read_bytes())
        verify = {
            "operation_id": "card",
            "apply_result_ref": applied["data"]["apply_result_ref"],
            "card_path": path,
            "card_digest": card_digest,
        }
        self.root.joinpath("knowledge/index.md").write_bytes(
            b"later unrelated navigation"
        )
        source_lock_path = self.root / "governance/sources.lock.yaml"
        current = json.loads(source_lock_path.read_text(encoding="utf-8"))
        current["resources"].append({"source_id": "unrelated-source", "kind": "raw"})
        source_lock_path.write_bytes(canonical(current))
        verified = self.invoke("hs-knowledge-apply", verify, action="verify-result")
        self.assertEqual(
            verified["data"]["eligible_files"], [{"path": path, "sha256": card_digest}]
        )
        self.root.joinpath(self.fixture_original_ref).write_bytes(b"tampered")
        self.invoke("hs-knowledge-apply", verify, action="verify-result", expected=2)

    def test_timestamp_valid_unpinned_pyc_is_never_executed(self):
        source = self.root / "governance/contracts/validation.py"
        cached = pathlib.Path(importlib.util.cache_from_source(str(source)))
        cached.parent.mkdir(parents=True, exist_ok=True)
        code = compile(
            "raise RuntimeError('UNPINNED CACHE EXECUTED')", str(source), "exec"
        )
        metadata = source.stat()
        cached.write_bytes(
            importlib.util.MAGIC_NUMBER
            + struct.pack("<III", 0, int(metadata.st_mtime), metadata.st_size)
            + marshal.dumps(code)
        )
        request = self.prepare_reviewed("hostile-cache")
        self.invoke("hs-knowledge-apply", request)

    def test_own_support_and_business_pyc_are_never_executed(self):
        for module in ("support", "transaction"):
            source = self.root / "runtime/himate_knowledge/stages/apply" / (module + ".py")
            cached = pathlib.Path(importlib.util.cache_from_source(str(source)))
            cached.parent.mkdir(parents=True, exist_ok=True)
            code = compile(
                "raise RuntimeError('UNPINNED PACKAGE CACHE EXECUTED')",
                str(source),
                "exec",
            )
            metadata = source.stat()
            cached.write_bytes(
                importlib.util.MAGIC_NUMBER
                + struct.pack("<III", 0, int(metadata.st_mtime), metadata.st_size)
                + marshal.dumps(code)
            )
        request = self.prepare_reviewed("hostile-package-cache")
        self.invoke("hs-knowledge-apply", request)
