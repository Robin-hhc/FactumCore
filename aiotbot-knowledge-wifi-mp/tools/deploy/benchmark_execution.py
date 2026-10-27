"""Compare explicit local and SSH profiles using read-only public node actions.

This does not clear filesystem caches or benchmark ingest. Every invocation gets
new runtime records; originals, cards, journals and active indexes are read-only.
"""

from __future__ import annotations

import argparse
import base64
import copy
import importlib.util
import math
from pathlib import Path
import platform
import re
import statistics
import sys
import time
import uuid


sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("benchmark_node_runner", Path(__file__).with_name("run_node.py"))
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

_ACTIONS = {
    ("hs-knowledge-query", "search"): {"query", "purpose", "context", "top_k", "scan_limit", "channel"},
    ("hs-knowledge-source-capture", "resolve-source"): {"source_ref"},
    ("hs-knowledge-source-scan", "status"): {"target_operation_id"},
}


class BenchmarkError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def validate_cases(plan):
    if (not isinstance(plan, dict) or set(plan) != {"schema_version", "shared_project_id", "cases"}
            or plan.get("schema_version") != "1.0" or not isinstance(plan.get("shared_project_id"), str)
            or not plan["shared_project_id"].strip() or len(plan["shared_project_id"]) > 128
            or not isinstance(plan.get("cases"), list) or not plan["cases"] or len(plan["cases"]) > 20):
        raise BenchmarkError("INVALID_BENCHMARK_PLAN")
    seen = set()
    for case in plan["cases"]:
        if (not isinstance(case, dict) or set(case) != {"id", "skill", "action", "request", "expected"}
                or not isinstance(case.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}", case["id"])
                or case["id"] in seen):
            raise BenchmarkError("INVALID_BENCHMARK_CASE")
        seen.add(case["id"])
        operation = (case.get("skill"), case.get("action"))
        allowed = _ACTIONS.get(operation)
        request, expected = case.get("request"), case.get("expected")
        if allowed is None or not isinstance(request, dict) or not set(request) <= allowed or not isinstance(expected, dict):
            raise BenchmarkError("READ_ONLY_BENCHMARK_ACTION_REQUIRED")
        if operation[0] == "hs-knowledge-query":
            required = expected.get("required_card_ids")
            if (set(expected) != {"required_card_ids"} or not isinstance(required, list) or not required
                    or any(not isinstance(item, str) or not item for item in required)
                    or len(required) != len(set(required)) or not isinstance(request.get("query"), str)
                    or not request["query"].strip()
                    or request.get("channel", "local") not in {"local", "shared"}
                    or request.get("purpose") not in {"current", "implementation", "guidance", "historical"}):
                raise BenchmarkError("EXPLICIT_QUERY_EXPECTATION_REQUIRED")
        elif operation[0] == "hs-knowledge-source-capture":
            if (set(request) != {"source_ref"} or not isinstance(request["source_ref"], dict)
                    or not {"source_id", "snapshot_id", "locator"} <= set(request["source_ref"])
                    or expected != {"current_source_matches": True}):
                raise BenchmarkError("EXACT_CURRENT_SOURCE_EXPECTATION_REQUIRED")
        elif (set(request) != {"target_operation_id"} or expected != {"nonempty_facts": True}
                or not isinstance(request["target_operation_id"], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", request["target_operation_id"])):
            raise BenchmarkError("FIXED_STATUS_TARGET_REQUIRED")
    return plan["cases"]


def package_identity(catalog):
    skills = catalog.get("skills") if isinstance(catalog, dict) else None
    if not isinstance(catalog, dict) or catalog.get("schema_version") != "2.0" or not isinstance(skills, dict) or not skills:
        raise BenchmarkError("INVALID_BENCHMARK_CATALOG")
    result = {}
    for name, entry in skills.items():
        if not isinstance(entry, dict) or not runner.pinned(entry.get("package_digest")):
            raise BenchmarkError("INVALID_BENCHMARK_CATALOG")
        result[name] = entry["package_digest"]
    return result


def source_semantics(source):
    if not isinstance(source, dict):
        raise BenchmarkError("SOURCE_EVIDENCE_REQUIRED")
    value = copy.deepcopy(source)
    try:
        raw = base64.b64decode(value.pop("bytes_b64"), validate=True)
        snapshot = value["snapshot"]
        reference = value["source_ref"]
        if (runner.sha(raw) != value["sha256"] or len(raw) != value["bytes"]
                or snapshot["sha256"] != value["sha256"] or snapshot["bytes"] != len(raw)
                or runner.sha(runner.canonical(snapshot)) != value["snapshot_digest"]
                or snapshot["snapshot_id"] != reference["snapshot_id"]
                or snapshot["source_id"] != reference["source_id"]):
            raise BenchmarkError("SOURCE_EVIDENCE_MISMATCH")
    except (KeyError, TypeError, ValueError) as exc:
        raise BenchmarkError("SOURCE_EVIDENCE_MISMATCH") from exc
    value["original_bytes_identity"] = {"sha256": runner.sha(raw), "bytes": len(raw)}
    return value


def semantic_result(case, response):
    """Remove only search's per-call receipt; keep all substantive evidence."""
    data = copy.deepcopy(response.get("data"))
    if not isinstance(data, dict) or response.get("diagnostics"):
        raise BenchmarkError("COMPLETE_SUCCESSFUL_RESULT_REQUIRED")
    if case["skill"] == "hs-knowledge-query":
        matches = data.get("matches")
        if (data.get("candidate_scan_truncated") is not False or data.get("gaps")
                or not isinstance(matches, list) or not matches
                or not runner.pinned(data.get("processing_digest"))
                or not isinstance(data.get("generation_ref"), str)
                or not isinstance(data.get("generation_id"), str)
                or data.get("evaluation") is not False
                or not set(case["expected"]["required_card_ids"]) <= {row.get("card_id") for row in matches}):
            raise BenchmarkError("QUERY_NOT_REPRESENTATIVE_OR_INCOMPLETE")
        if not isinstance(data.pop("receipt_ref", None), str):
            raise BenchmarkError("QUERY_RECEIPT_REQUIRED")
        for row in matches:
            if (not runner.pinned(row.get("card_digest")) or not row.get("claim_ids")
                    or not isinstance(row.get("sources"), list) or not row["sources"]):
                raise BenchmarkError("QUERY_CONTENT_EVIDENCE_REQUIRED")
            row["sources"] = [source_semantics(source) for source in row["sources"]]
    elif case["skill"] == "hs-knowledge-source-capture":
        if data.get("current_source_matches") is not True or data.get("limitations"):
            raise BenchmarkError("CURRENT_COMPLETE_SOURCE_REQUIRED")
        data = source_semantics(data)
        if data["source_ref"] != case["request"]["source_ref"]:
            raise BenchmarkError("SOURCE_REQUEST_BINDING_MISMATCH")
    else:
        operations = data.get("operations")
        if (not isinstance(operations, list) or len(operations) != 1
                or operations[0].get("operation_id") != case["request"]["target_operation_id"]
                or operations[0].get("gaps") or not operations[0].get("facts")):
            raise BenchmarkError("NONEMPTY_FIXED_STATUS_REQUIRED")
        data.pop("knowledge_root", None)  # physical paths differ by execution host
    return {"phase": response.get("phase"), "data": data}


def environment(direct):
    root = str(runner.absolute(direct["knowledge_root"]))
    normalized = root.replace("\\", "/")
    unc = normalized.lower().startswith("//?/unc/") or (
        normalized.startswith("//") and not normalized.startswith(("//?/", "//./")))
    return {"client_os": platform.system(), "client_python": platform.python_version(),
            "direct_root_is_unc": unc,
            "direct_root": root,
            "storage_equivalence": "declared_mapping_and_matching_config_content_evidence"}


def assessment(pairs, *, comparable, field_scope):
    direct = [pair["direct_seconds"] for pair in pairs]
    ssh = [pair["ssh_seconds"] for pair in pairs]
    result = {"rounds": len(pairs), "comparable": comparable,
              "direct_median_seconds": statistics.median(direct), "ssh_median_seconds": statistics.median(ssh),
              "direct_range_seconds": [min(direct), max(direct)], "ssh_range_seconds": [min(ssh), max(ssh)]}
    result["median_saved_seconds"] = result["direct_median_seconds"] - result["ssh_median_seconds"]
    result["direct_over_ssh_ratio"] = result["direct_median_seconds"] / result["ssh_median_seconds"] if result["ssh_median_seconds"] else None
    result["ssh_faster_every_pair"] = all(remote < local for local, remote in zip(direct, ssh))
    result["timing_ranges_separated"] = max(ssh) < min(direct)
    # Deliberately conservative evidence for one exact request/environment.
    result["recommendation"] = ("ssh_candidate_for_this_bound_case" if comparable and field_scope
                                and len(pairs) >= 5 and result["timing_ranges_separated"]
                                and result["ssh_faster_every_pair"] else "no_route_change")
    return result


def active_bindings(direct, cases):
    bindings, snapshots = {}, {}
    for channel in sorted({case["request"].get("channel", "local") for case in cases
                           if case["skill"] == "hs-knowledge-query"}):
        relative = f"artifacts/indexes/{channel}/active.json"
        path = runner.absolute(str(Path(direct["knowledge_root"]) / relative))
        raw = path.read_bytes()
        value = runner.strict_json(raw)
        if (not isinstance(value, dict) or value.get("record_kind") != "index_manifest"
                or value.get("rules_digest") != direct["rules_digest"]
                or value.get("digest") != runner.sha(runner.canonical({key: item for key, item in value.items() if key != "digest"}))
                or not isinstance(value.get("generation_ref"), str)
                or not value["generation_ref"].startswith(f"artifacts/indexes/{channel}/")
                or not isinstance(value.get("generation_id"), str)):
            raise BenchmarkError("BENCHMARK_ACTIVE_IDENTITY_REQUIRED")
        bindings[channel] = {"path": relative, "sha256": runner.sha(raw), "digest": value["digest"],
                             "generation_ref": value["generation_ref"], "generation_id": value["generation_id"]}
        snapshots[path] = raw
    return bindings, snapshots


def benchmark(direct, remote, plan, output, *, rounds=7, warmups=1, environment_id,
              dispatch=None, clock=None, configuration_snapshots=None,
              transport_note="Topology not independently verified"):
    cases = validate_cases(plan)
    runner.validate_profile(direct)
    runner.validate_profile(remote)
    if direct["mode"] != "local" or remote["mode"] != "ssh":
        raise BenchmarkError("LOCAL_AND_SSH_PROFILES_REQUIRED")
    if (isinstance(rounds, bool) or not isinstance(rounds, int) or not 3 <= rounds <= 31
            or isinstance(warmups, bool) or not isinstance(warmups, int) or not 0 <= warmups <= 5
            or not isinstance(environment_id, str) or not environment_id.strip() or len(environment_id) > 128
            or not isinstance(transport_note, str) or not transport_note.strip() or len(transport_note) > 1024):
        raise BenchmarkError("INVALID_BENCHMARK_SCHEDULE")
    direct_catalog = runner.absolute(direct["catalog"])
    ssh_catalog = runner.absolute(remote["expected_catalog"])
    catalog_bytes = {"direct": direct_catalog.read_bytes(), "ssh": ssh_catalog.read_bytes()}
    catalogs = {side: runner.strict_json(raw) for side, raw in catalog_bytes.items()}
    identities = {side: package_identity(catalog) for side, catalog in catalogs.items()}
    if direct["rules_digest"] != remote["rules_digest"] or identities["direct"] != identities["ssh"]:
        raise BenchmarkError("RULES_OR_PACKAGE_VERSIONS_DIFFER")
    for skill in {case["skill"] for case in cases} | {"hs-knowledge-maintain"}:
        for catalog in catalogs.values():
            runner.catalog_entry(catalog, skill)
    pointers, pointer_snapshots = active_bindings(direct, cases)
    output = runner.absolute(str(Path(output).absolute()), exists=False)
    if output.exists():
        raise BenchmarkError("BENCHMARK_OUTPUT_EXISTS")
    runner.caller_output_boundary(output, direct)
    runner.caller_output_boundary(output, remote)
    run_id = uuid.uuid4().hex
    artifacts = output.with_name(output.stem + "-samples-" + run_id)
    runner._installer.no_links(artifacts)
    artifacts.mkdir(mode=0o700, parents=True)
    dispatch = dispatch or runner.dispatch
    clock = clock or time.perf_counter
    report = {"schema_version": "1.0", "record_kind": "execution_benchmark", "run_id": run_id,
              "environment_id": environment_id, "shared_project_id": plan["shared_project_id"],
              "environment": environment(direct), "rules_digest": direct["rules_digest"],
              "transport_note": transport_note,
              "profile_digests": {"direct": runner.sha(runner.canonical(direct)), "ssh": runner.sha(runner.canonical(remote))},
              "active_bindings": pointers,
              "package_identity": identities["direct"], "catalog_digests": {side: runner.sha(raw) for side, raw in catalog_bytes.items()},
              "configuration_digests": {str(path): runner.sha(raw) for path, raw in (configuration_snapshots or {}).items()},
              "plan_digest": runner.sha(runner.canonical(plan)), "samples": [], "cases": [], "complete": False,
              "comparability": False, "diagnostics": [], "limitations": [
                  "First-use samples do not prove cold OS, disk, SMB or server caches; caches are not cleared.",
                  "Configuration loading or remote registration discovery before dispatch is outside timing; first-use does not prove cold SSH setup.",
                  "All timings include dispatcher/SSH, node startup, validation, result transport and parsing.",
                  "Only the listed read-only actions are measured; results do not establish ingest, apply or activation performance.",
                  "Run with no concurrent ingest or deployment change; unrelated host load is not controlled by this tool.",
                  "Runtime records are newly created under .build; no existing report or governed content is overwritten.",
                  "Recommendations apply only to the exact case, configuration, packages, runtime and observed environment."]}
    runtimes, requirements, semantic_digests, configs = {"direct": set(), "ssh": set()}, {}, {}, set()

    def sample(side, case, phase, iteration):
        serial = len(report["samples"])
        request = {**case["request"], "operation_id": f"bench-{run_id[:12]}-{serial}"}
        row = {"side": side, "case_id": case["id"], "phase": phase, "iteration": iteration,
               "operation_id": request["operation_id"], "seconds": None}
        report["samples"].append(row)
        started = clock()
        try:
            code, raw = dispatch(direct if side == "direct" else remote, case["skill"], request, case["action"])
        except (runner.ExecutionError, OSError, ValueError, KeyError, TypeError) as exc:
            row.update(seconds=clock() - started, error_code=getattr(exc, "code", "BENCHMARK_EXECUTION_UNAVAILABLE"))
            raise
        elapsed = clock() - started
        if not math.isfinite(elapsed) or elapsed <= 0:
            raise BenchmarkError("INVALID_BENCHMARK_CLOCK_SAMPLE")
        row.update(seconds=elapsed, exit_code=code)
        response = runner.strict_json(raw)
        runner.verify_response(response, code, case["skill"], runner.catalog_entry(catalogs[side], case["skill"]), direct["rules_digest"], request)
        ref = artifacts / f"{serial:04d}-{side}.json"
        runner.publish_new(ref, raw)
        row.update(response_path=str(ref), raw_sha256=runner.sha(raw), response_digest=response["digest"])
        if code != 0 or response.get("status") != "ok":
            raise BenchmarkError("BENCHMARK_NODE_DID_NOT_SUCCEED")
        runtime = response.get("tool_identity", {}).get("runtime")
        dependency_lock = response.get("tool_identity", {}).get("requirements_digest")
        if not isinstance(runtime, str) or not re.fullmatch(r"\d+\.\d+\.\d+.*", runtime):
            raise BenchmarkError("NODE_RUNTIME_VERSION_REQUIRED")
        if not runner.pinned(dependency_lock):
            raise BenchmarkError("NODE_DEPENDENCY_LOCK_IDENTITY_REQUIRED")
        runtimes[side].add(runtime)
        requirements.setdefault(case["skill"], set()).add(dependency_lock)
        row.update(runtime=runtime, requirements_digest=dependency_lock)
        if case["skill"] == "hs-knowledge-maintain":
            data = response["data"]
            if (data.get("complete") is not True or data.get("gaps") or data.get("affected_claims")
                    or not runner.pinned(data.get("config_digest")) or data.get("rules_digest") != direct["rules_digest"]):
                raise BenchmarkError("STABLE_CURRENT_PROJECT_CONTEXT_REQUIRED")
            configs.add(data["config_digest"])
            normalized = data
        else:
            normalized = semantic_result(case, response)
            if case["skill"] == "hs-knowledge-query":
                pointer = pointers[case["request"].get("channel", "local")]
                if any(response["data"].get(key) != pointer[key] for key in ("generation_ref", "generation_id")):
                    raise BenchmarkError("BENCHMARK_QUERY_GENERATION_CHANGED")
        row["semantic_digest"] = runner.sha(runner.canonical(normalized))
        semantic_digests.setdefault(case["id"], set()).add(row["semantic_digest"])
        return row

    metadata = {"id": "__project_identity__", "skill": "hs-knowledge-maintain", "action": "inspect-context", "request": {}, "expected": {}}
    try:
        # First observed pair is kept separately; probing would warm these paths.
        for case in cases:
            sample("direct", case, "first_use", 0)
            sample("ssh", case, "first_use", 0)
        for side in ("direct", "ssh"):
            sample(side, metadata, "identity_before", 0)
        for case_index, case in enumerate(cases):
            for number in range(warmups):
                for side in (("ssh", "direct") if number % 2 else ("direct", "ssh")):
                    sample(side, case, "warmup", number)
            pairs = []
            for number in range(rounds):
                order = ("ssh", "direct") if (number + case_index) % 2 else ("direct", "ssh")
                values = {side: sample(side, case, "warm", number)["seconds"] for side in order}
                pairs.append({"iteration": number, "order": list(order),
                              "direct_seconds": values["direct"], "ssh_seconds": values["ssh"]})
            report["cases"].append({"id": case["id"], "skill": case["skill"], "action": case["action"],
                                    "request_digest": runner.sha(runner.canonical(case["request"])),
                                    "pairs": pairs})
        for side in ("ssh", "direct"):
            sample(side, metadata, "identity_after", 0)
        if direct_catalog.read_bytes() != catalog_bytes["direct"] or ssh_catalog.read_bytes() != catalog_bytes["ssh"]:
            raise BenchmarkError("BENCHMARK_CATALOG_CHANGED")
        if any(Path(path).read_bytes() != raw for path, raw in (configuration_snapshots or {}).items()):
            raise BenchmarkError("BENCHMARK_CONFIGURATION_CHANGED")
        if any(path.read_bytes() != raw for path, raw in pointer_snapshots.items()):
            raise BenchmarkError("BENCHMARK_ACTIVE_CHANGED")
        report["complete"] = True
        report["project_config_digests"] = sorted(configs)
        report["runtime_versions"] = {side: sorted(versions) for side, versions in runtimes.items()}
        report["requirements_digests"] = {skill: sorted(values) for skill, values in requirements.items()}
        all_versions = set().union(*runtimes.values())
        families = {tuple(version.split(".")[:2]) for version in all_versions}
        report["comparability"] = (len(families) == 1 and all(len(versions) == 1 for versions in runtimes.values())
                                   and all(len(values) == 1 for values in requirements.values())
                                   and all(len(values) == 1 for values in semantic_digests.values()))
        if len(all_versions) > 1:
            report["limitations"].append("Python patch versions differ; this measures actual deployment paths, not an isolated transport/protocol effect.")
        if not report["comparability"]:
            report["diagnostics"].append({"code": "RUNTIME_CONTENT_OR_CONTEXT_CHANGED"})
        field_scope = report["environment"]["client_os"] == "Windows" and report["environment"]["direct_root_is_unc"]
        for case in report["cases"]:
            case["semantic_digests"] = sorted(semantic_digests[case["id"]])
            case["binding"] = {"config_digest": next(iter(configs)) if len(configs) == 1 else None,
                               "active_pointer": pointers.get(next((item["request"].get("channel", "local")
                                     for item in cases if item["id"] == case["id"] and item["skill"] == "hs-knowledge-query"), None))}
            case["assessment"] = assessment(case["pairs"], comparable=report["comparability"], field_scope=field_scope)
    except (BenchmarkError, runner.ExecutionError, OSError, ValueError, KeyError, TypeError) as exc:
        report["diagnostics"].append({"code": getattr(exc, "code", "BENCHMARK_EXECUTION_UNAVAILABLE")})
    report["digest"] = runner.sha(runner.canonical(report))
    runner.publish_new(output, runner.canonical(report) + b"\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-profile", required=True)
    parser.add_argument("--ssh-profile", required=True)
    parser.add_argument("--direct-config-env", action="store_true")
    parser.add_argument("--ssh-config-env", action="store_true")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--environment-id", required=True)
    parser.add_argument("--transport-note", default="Topology not independently verified")
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        direct_path, remote_path, cases_path = [runner.caller_path(path) for path in
                                               (args.direct_profile, args.ssh_profile, args.cases)]
        output_path = runner.caller_path(args.output, exists=False)
        snapshots = {path: path.read_bytes() for path in (direct_path, remote_path, cases_path)}
        if hasattr(runner, "load_configuration"):
            direct = runner.load_configuration(direct_path, config_env=args.direct_config_env)
            remote = runner.load_configuration(remote_path, config_env=args.ssh_config_env)
        else:
            if args.direct_config_env or args.ssh_config_env:
                raise BenchmarkError("CONFIG_ENV_LOADER_UNAVAILABLE")
            direct = runner.validate_profile(runner.strict_json(snapshots[direct_path]))
            remote = runner.validate_profile(runner.strict_json(snapshots[remote_path]))
        plan = runner.strict_json(snapshots[cases_path])
        report = benchmark(direct, remote, plan, output_path, rounds=args.rounds,
                           warmups=args.warmups, environment_id=args.environment_id,
                           configuration_snapshots=snapshots, transport_note=args.transport_note)
        return 0 if report["complete"] and report["comparability"] else 1
    except (BenchmarkError, runner.ExecutionError, OSError, ValueError, TypeError, KeyError) as exc:
        sys.stderr.write(getattr(exc, "code", "BENCHMARK_INPUT_UNAVAILABLE") + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
