"""Read-only benchmark scheduling and comparison; no host connections in tests."""

import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys

import pytest
import yaml


TOOL = Path(__file__).resolve().parents[1] / "benchmark_execution.py"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@pytest.mark.parametrize("network_arg", ["--direct-profile", "--ssh-profile", "--cases", "--output"])
def test_cli_rejects_network_inputs_and_output_before_any_snapshot_read(tmp_path, monkeypatch, capsys, network_arg):
    spec = importlib.util.spec_from_file_location("network_benchmark_preflight", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    arguments = {}
    for flag in ("--direct-profile", "--ssh-profile", "--cases"):
        path = tmp_path / (flag[2:] + ".json")
        path.write_bytes(b"{}")
        arguments[flag] = str(path)
    arguments["--output"] = str(tmp_path / "new-report.json")
    arguments[network_arg] = r"\\server\share\blocked.json"

    def unexpected_read(path):
        pytest.fail("Snapshot bytes read before all caller paths were checked")

    original_resolve = Path.resolve

    def local_resolve(path, *args, **kwargs):
        if str(path).startswith(("\\\\", "//")):
            pytest.fail("Network path resolved before storage preflight")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", local_resolve)
    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    argv = [value for flag, path in arguments.items() for value in (flag, path)]
    assert module.main(argv + ["--environment-id", "synthetic-policy-check"]) == 2
    assert capsys.readouterr().err.strip() == "REMOTE_FILESYSTEM_REQUIRES_SSH"


@pytest.fixture
def benchmark(tmp_path):
    spec = importlib.util.spec_from_file_location("execution_benchmark_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "knowledge"
    root.mkdir()
    skills = ("hs-knowledge-query", "hs-knowledge-maintain", "hs-knowledge-source-capture", "hs-knowledge-source-scan")
    catalog = {"schema_version": "2.0", "skills": {
        name: {"root": str(tmp_path / name), "entry": "scripts/cli.py", "python": "unused-in-synthetic-test",
               "package_digest": hashlib.sha256(name.encode()).hexdigest()} for name in skills}}
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_bytes(canonical(catalog))
    pointer = {"schema_version": "2.0", "record_kind": "index_manifest", "rules_digest": "1" * 64,
               "generation_ref": "artifacts/indexes/local/gen-fixed/manifest.json", "generation_id": "gen-fixed"}
    pointer["digest"] = digest(pointer)
    active = root / "artifacts/indexes/local/active.json"
    active.parent.mkdir(parents=True)
    active.write_bytes(canonical(pointer))
    direct = {"schema_version": "1.0", "mode": "local", "knowledge_root": str(root),
              "catalog": str(catalog_path), "rules_digest": "1" * 64}
    remote = {"schema_version": "1.0", "mode": "ssh", "target": "not-connected",
              "remote_python": "/private/python", "remote_runner": "/private/run_node.py",
              "remote_profile": "/private/profile.json", "remote_profile_digest": "2" * 64,
              "expected_catalog": str(catalog_path), "rules_digest": "1" * 64}
    plan = {"schema_version": "1.0", "shared_project_id": "synthetic-project",
            "cases": [{"id": "background-query", "skill": "hs-knowledge-query", "action": "search",
                       "request": {"query": "synthetic", "purpose": "guidance"},
                       "expected": {"required_card_ids": ["rule"]}}]}
    return module, direct, remote, plan, catalog


class SyntheticNodes:
    """Known deterministic durations do not claim real SSH or SMB performance."""

    def __init__(self, catalog):
        self.catalog, self.now, self.calls = catalog, 0.0, []
        self.mutate = None

    def clock(self):
        return self.now

    def source(self):
        raw = b"synthetic original"
        sha = hashlib.sha256(raw).hexdigest()
        snapshot = {"snapshot_id": "raw:fixture", "source_id": "source", "sha256": sha, "bytes": len(raw)}
        return {"source_ref": {"source_id": "source", "snapshot_id": "raw:fixture", "locator": {"kind": "lines", "start": 1, "end": 1}},
                "snapshot": snapshot, "snapshot_digest": digest(snapshot), "sha256": sha, "bytes": len(raw),
                "bytes_b64": base64.b64encode(raw).decode(), "text": "synthetic original", "limitations": [],
                "current_source_matches": True, "current_source_sha256": sha}

    def __call__(self, profile, skill, request, action):
        side = "direct" if profile["mode"] == "local" else "ssh"
        self.calls.append((side, skill, action, copy.deepcopy(request)))
        self.now += 0.2 if side == "direct" else 0.05
        if skill == "hs-knowledge-maintain":
            data = {"complete": True, "affected_claims": [], "gaps": [], "rules_digest": "1" * 64,
                    "config_digest": "3" * 64, "state": {"validity_epoch": 1}}
            phase = "inspected"
        elif skill == "hs-knowledge-query":
            data = {"matches": [{"card_id": "rule", "card_digest": "4" * 64, "claim_ids": ["claim"],
                                 "sources": [self.source()], "score": 1}],
                    "candidate_scan_truncated": False, "gaps": [], "query": request["query"],
                    "generation_ref": "artifacts/indexes/local/gen-fixed/manifest.json", "generation_id": "gen-fixed",
                    "processing_digest": "5" * 64, "evaluation": False,
                    "receipt_ref": ".build/operations/" + request["operation_id"] + "/receipt.json"}
            phase = "queried"
        elif skill == "hs-knowledge-source-capture":
            data, phase = self.source(), "resolved"
        else:
            data, phase = {"knowledge_root": profile.get("knowledge_root", "/remote/knowledge"), "operations": [
                {"operation_id": request["target_operation_id"], "facts": [{"stage": "transaction", "digest": "6" * 64}], "gaps": []}]}, "status"
        result = {"schema_version": "2.0", "record_kind": "result", "rules_digest": "1" * 64,
                  "status": "ok", "phase": phase, "data": data, "diagnostics": [],
                  "tool_identity": {"skill": skill, "package_digest": self.catalog["skills"][skill]["package_digest"],
                                    "runtime": "3.11.9", "requirements_digest": "8" * 64}}
        if self.mutate:
            self.mutate(side, skill, result)
        result["digest"] = digest(result)
        return 0, canonical(result)


def run(module, direct, remote, plan, catalog, output, **options):
    nodes = SyntheticNodes(catalog)
    result = module.benchmark(direct, remote, plan, output, environment_id="synthetic-tests-only",
                              dispatch=nodes, clock=nodes.clock, rounds=5, **options)
    return result, nodes


def test_pairs_alternate_receipt_ids_do_not_break_semantic_comparison(benchmark, tmp_path):
    module, direct, remote, plan, catalog = benchmark
    report, nodes = run(module, direct, remote, plan, catalog, tmp_path / "report.json")
    assert report["complete"] and report["comparability"]
    assert len(report["samples"]) == 18  # first use + identity + warmup + 5 pairs
    warm = report["cases"][0]
    assert [row["order"] for row in warm["pairs"]] == [["direct", "ssh"], ["ssh", "direct"], ["direct", "ssh"], ["ssh", "direct"], ["direct", "ssh"]]
    assert len(warm["semantic_digests"]) == 1
    assert warm["assessment"]["recommendation"] == "no_route_change"  # local synthetic fixture is not SMB
    assert warm["assessment"]["direct_median_seconds"] == pytest.approx(0.2)
    assert warm["assessment"]["ssh_median_seconds"] == pytest.approx(0.05)
    operations = [call[3]["operation_id"] for call in nodes.calls]
    assert len(operations) == len(set(operations))
    assert {row["phase"] for row in report["samples"]} == {"first_use", "identity_before", "identity_after", "warmup", "warm"}
    assert report["digest"] == digest({key: value for key, value in report.items() if key != "digest"})
    for row in report["samples"]:
        assert hashlib.sha256(Path(row["response_path"]).read_bytes()).hexdigest() == row["raw_sha256"]


@pytest.mark.parametrize("mutation", ["hash", "runtime", "generation", "context", "limit", "source"])
def test_unequal_or_incomplete_results_cannot_recommend_ssh(benchmark, tmp_path, mutation):
    module, direct, remote, plan, catalog = benchmark
    nodes = SyntheticNodes(catalog)

    def mutate(side, skill, result):
        if side != "ssh":
            return
        if mutation == "runtime":
            result["tool_identity"]["runtime"] = "3.12.15"
        elif mutation == "context" and skill == "hs-knowledge-maintain":
            result["data"]["config_digest"] = "a" * 64
        elif skill == "hs-knowledge-query":
            if mutation == "hash":
                result["data"]["matches"][0]["card_digest"] = "a" * 64
            elif mutation == "generation":
                result["data"]["generation_id"] = "gen-other"
            elif mutation == "limit":
                result["data"]["candidate_scan_truncated"] = True
            elif mutation == "source":
                result["data"]["matches"][0]["sources"][0]["bytes_b64"] = "bad"

    nodes.mutate = mutate
    report = module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="synthetic",
                              dispatch=nodes, clock=nodes.clock, rounds=5)
    assert not report["comparability"]
    assert all(case.get("assessment", {}).get("recommendation") != "ssh_candidate_for_this_bound_case" for case in report["cases"])
    assert report["diagnostics"]


@pytest.mark.parametrize(("skill", "action"), [
    ("hs-knowledge-apply", "apply"), ("hs-knowledge-index-build", "activate"),
    ("hs-knowledge-source-capture", None), ("hs-knowledge-maintain", "advance"),
    ("hs-knowledge-recover", "resume"), ("hs-knowledge-source-scan", "record"),
])
def test_mutating_actions_are_rejected_before_dispatch(benchmark, tmp_path, skill, action):
    module, direct, remote, plan, catalog = benchmark
    plan["cases"][0].update(skill=skill, action=action)
    nodes = SyntheticNodes(catalog)
    with pytest.raises(module.BenchmarkError, match="READ_ONLY"):
        module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="synthetic", dispatch=nodes)
    assert not nodes.calls
    assert not (tmp_path / "report.json").exists()


def test_existing_report_is_never_overwritten_or_executed(benchmark, tmp_path):
    module, direct, remote, plan, catalog = benchmark
    output = tmp_path / "report.json"
    output.write_bytes(b"existing result")
    nodes = SyntheticNodes(catalog)
    with pytest.raises(module.BenchmarkError, match="OUTPUT_EXISTS"):
        module.benchmark(direct, remote, plan, output, environment_id="synthetic", dispatch=nodes)
    assert output.read_bytes() == b"existing result" and not nodes.calls


def test_registered_packages_must_match_before_dispatch(benchmark, tmp_path):
    module, direct, remote, plan, catalog = benchmark
    other = copy.deepcopy(catalog)
    other["skills"]["hs-knowledge-maintain"]["package_digest"] = "a" * 64
    changed = tmp_path / "other-catalog.json"
    changed.write_bytes(canonical(other))
    remote["expected_catalog"] = str(changed)
    nodes = SyntheticNodes(catalog)
    with pytest.raises(module.BenchmarkError, match="VERSIONS_DIFFER"):
        module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="synthetic", dispatch=nodes)
    assert not nodes.calls


def test_extended_local_drive_is_not_a_network_share(benchmark, monkeypatch):
    module, direct, _, _, _ = benchmark
    monkeypatch.setattr(module.runner, "absolute", lambda value: PureWindowsPath(r"\\?\C:\a-long-local-path"))
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")
    assert module.environment(direct)["direct_root_is_unc"] is False


def test_only_bound_field_data_with_separated_ranges_can_suggest_ssh(benchmark):
    module = benchmark[0]
    pairs = [{"direct_seconds": 1, "ssh_seconds": 0.1}] * 5
    assert module.assessment(pairs, comparable=True, field_scope=True)["recommendation"] == "ssh_candidate_for_this_bound_case"
    assert module.assessment(pairs, comparable=True, field_scope=False)["recommendation"] == "no_route_change"
    assert module.assessment(pairs[:3], comparable=True, field_scope=True)["recommendation"] == "no_route_change"


def test_profile_or_plan_changes_invalidate_the_saved_report(benchmark, tmp_path):
    module, direct, remote, plan, catalog = benchmark
    configuration = tmp_path / "trusted-plan.json"
    configuration.write_bytes(canonical(plan))
    original = configuration.read_bytes()
    nodes = SyntheticNodes(catalog)
    nodes.mutate = lambda *args: configuration.write_bytes(b"changed during measurement")
    report = module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="synthetic",
                              dispatch=nodes, clock=nodes.clock, rounds=5,
                              configuration_snapshots={configuration: original})
    assert not report["complete"] and not report["comparability"]
    assert report["diagnostics"][-1]["code"] == "BENCHMARK_CONFIGURATION_CHANGED"
    assert all(case.get("assessment", {}).get("recommendation") != "ssh_candidate_for_this_bound_case" for case in report["cases"])


def test_active_pointer_changes_invalidate_the_saved_report(benchmark, tmp_path):
    module, direct, remote, plan, catalog = benchmark
    active = Path(direct["knowledge_root"]) / "artifacts/indexes/local/active.json"
    nodes = SyntheticNodes(catalog)
    nodes.mutate = lambda *args: active.write_bytes(b"changed active pointer")
    report = module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="synthetic",
                              dispatch=nodes, clock=nodes.clock, rounds=5)
    assert not report["complete"] and not report["comparability"]
    assert report["diagnostics"][-1]["code"] == "BENCHMARK_ACTIVE_CHANGED"


def test_transport_failure_keeps_which_sample_failed_without_retry(benchmark, tmp_path):
    module, direct, remote, plan, _ = benchmark
    calls = []

    def unavailable(*args):
        calls.append(args)
        raise module.runner.ExecutionError("SSH_RESULT_UNAVAILABLE_REMOTE_STATE_UNKNOWN", blocked=True)

    report = module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="synthetic", dispatch=unavailable)
    assert len(calls) == 1 and not report["complete"]
    assert report["samples"][0]["case_id"] == "background-query"
    assert report["samples"][0]["side"] == "direct"
    assert report["samples"][0]["error_code"] == "SSH_RESULT_UNAVAILABLE_REMOTE_STATE_UNKNOWN"
    assert report["samples"][0]["seconds"] >= 0


@pytest.mark.parametrize("kind", ["source", "status"])
def test_exact_source_and_fixed_status_are_supported_without_domain_writes(benchmark, tmp_path, kind):
    module, direct, remote, plan, catalog = benchmark
    nodes = SyntheticNodes(catalog)
    if kind == "source":
        plan["cases"] = [{"id": "source", "skill": "hs-knowledge-source-capture", "action": "resolve-source",
                          "request": {"source_ref": nodes.source()["source_ref"]}, "expected": {"current_source_matches": True}}]
    else:
        plan["cases"] = [{"id": "status", "skill": "hs-knowledge-source-scan", "action": "status",
                          "request": {"target_operation_id": "fixed-existing-ingest"}, "expected": {"nonempty_facts": True}}]
    report = module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="synthetic",
                              dispatch=nodes, clock=nodes.clock, rounds=5)
    assert report["complete"] and report["comparability"]
    assert all(call[2] in {"inspect-context", "resolve-source", "status"} for call in nodes.calls)


@pytest.mark.parametrize("payload", [{}, {"target_operation_id": "target", "source": "docs-raw/specs"}])
def test_status_cannot_scan_benchmark_created_operations(benchmark, payload):
    module, _, _, plan, _ = benchmark
    plan["cases"] = [{"id": "status", "skill": "hs-knowledge-source-scan", "action": "status",
                      "request": payload, "expected": {"nonempty_facts": True}}]
    with pytest.raises(module.BenchmarkError):
        module.validate_cases(plan)


def test_patch_versions_are_disclosed_for_actual_path_comparison(benchmark, tmp_path):
    module, direct, remote, plan, catalog = benchmark
    nodes = SyntheticNodes(catalog)

    def mutate(side, skill, result):
        if side == "ssh":
            result["tool_identity"]["runtime"] = "3.11.13"

    nodes.mutate = mutate
    report = module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="synthetic",
                              dispatch=nodes, clock=nodes.clock, rounds=5)
    assert report["complete"] and report["comparability"]
    assert report["runtime_versions"] == {"direct": ["3.11.9"], "ssh": ["3.11.13"]}
    assert any("patch versions differ" in item for item in report["limitations"])
    assert report["cases"][0]["assessment"]["recommendation"] == "no_route_change"


def test_real_query_nodes_and_real_worker_preserve_governed_data(tmp_path, monkeypatch):
    domain = TOOL.resolve().parents[2]
    harness_spec = importlib.util.spec_from_file_location("benchmark_public_pipeline", domain / "evals/pipeline_harness.py")
    harness = importlib.util.module_from_spec(harness_spec)
    harness_spec.loader.exec_module(harness)
    pipeline = harness.Pipeline(tmp_path / "isolated project")
    lock_path = pipeline.root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(lock_path.read_bytes())
    for entry in lock["files"].values():
        entry["sha256"] = hashlib.sha256((pipeline.root / entry["path"]).read_bytes()).hexdigest()
    lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    pipeline.rules = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    frozen = tmp_path / "frozen skills"
    shutil.copytree(pipeline.skills, frozen, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    pipeline.skills = frozen
    for name, entry in pipeline.catalog["skills"].items():
        entry.update(root=str(frozen / name), package_digest=harness.package_digest(frozen / name))
    config = pipeline.root.parent / "config.yml"
    config.write_text(yaml.safe_dump({"schema_version": "2.0", "workspace_id": "benchmark-fixture",
                                     "knowledge_roots": {"wifi": pipeline.root.name}, "code_root": "main", "modules": []}), encoding="utf-8")
    pipeline.catalog["workspaces"] = {"benchmark-fixture": {"config": str(config), "rules_digest": pipeline.rules}}
    pipeline.catalog_path.write_bytes(canonical(pipeline.catalog))
    bundle_ref, bundle = pipeline.capture("benchmark-create", b"# Fixture\nCapture is synthetic benchmark evidence.\n")
    view_ref = pipeline.view("benchmark-create", bundle_ref, "benchmark-rule", pipeline.card("benchmark-rule", bundle))
    pipeline.apply("benchmark-create", view_ref)
    generation = pipeline.call("knowledge-index-build", {"operation_id": "benchmark-build"})["data"]
    pipeline.call("knowledge-index-build", {"operation_id": "benchmark-activate", "generation_ref": generation["generation_ref"], "expected_active": None}, "activate")
    retained = {ref: (pipeline.root / ref).read_bytes() for ref in (
        "docs-raw/specs/raw-source.md", "knowledge/rules/benchmark-rule.md", "governance/sources.lock.yaml",
        "logs/operations/benchmark-create/journal.json", "artifacts/indexes/local/active.json",
    )}
    spec = importlib.util.spec_from_file_location("public_execution_benchmark", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    direct = {"schema_version": "1.0", "mode": "local", "knowledge_root": str(pipeline.root),
              "catalog": str(pipeline.catalog_path), "rules_digest": pipeline.rules}
    remote_local = tmp_path / "remote local profile.json"
    remote_local.write_bytes(canonical(direct))
    remote = {"schema_version": "1.0", "mode": "ssh", "target": "isolated-test-transport",
              "remote_python": "/unused/python", "remote_runner": "/unused/run_node.py", "remote_profile": "/unused/profile.json",
              "remote_profile_digest": hashlib.sha256(remote_local.read_bytes()).hexdigest(),
              "expected_catalog": str(pipeline.catalog_path), "rules_digest": pipeline.rules}
    plan = {"schema_version": "1.0", "shared_project_id": "synthetic-public-node-fixture", "cases": [
        {"id": "query", "skill": "hs-knowledge-query", "action": "search", "request": {"query": "capture", "purpose": "current"},
         "expected": {"required_card_ids": ["benchmark-rule"]}}]}
    actual_run = subprocess.run

    def transport(argv, **kwargs):
        if argv[0] == "ssh":
            return actual_run([sys.executable, str(TOOL.with_name("run_node.py")), "--worker", "--profile", str(remote_local)],
                              input=kwargs["input"], capture_output=True)
        return actual_run(argv, **kwargs)

    monkeypatch.setattr(module.runner.subprocess, "run", transport)
    report = module.benchmark(direct, remote, plan, tmp_path / "report.json", environment_id="isolated-local-worker-test",
                              rounds=3, warmups=0)
    assert report["complete"] and report["comparability"], report["diagnostics"]
    assert report["cases"][0]["assessment"]["recommendation"] == "no_route_change"
    for ref, raw in retained.items():
        assert (pipeline.root / ref).read_bytes() == raw
