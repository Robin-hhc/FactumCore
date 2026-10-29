"""Run isolated package/process mechanism checks; never reads restricted gold.

Full is the default and collects every current test in each isolated group.
Quick is an explicit partial selection, not end-to-end acceptance. Use a fresh
--output-dir for every run. Performance observations never change test status.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from acceptance_report import COUNT_KEYS, compare_baseline, performance_report, read_junit, runtime_environment


ROOT = Path(__file__).resolve().parents[2]


# Small contract matrices and selected CLI smoke calls only. Full always uses
# directories instead, so additions never depend on extending this quick list.
# These do not cover the complete ingest journey, clone or fault/recovery matrix.
QUICK_FILES = {
    "hs-knowledge-apply": ("test_publication.py", "test_p7_regression.py"),
    "hs-knowledge-change-plan": (
        "test_cli.py::test_missing_request_returns_structured_error_without_creating_knowledge",
        "test_cli.py::test_independent_review_is_explicitly_moved_to_p5",
    ),
    "hs-knowledge-explore": (
        "test_cli.py::test_path_only_loads_current_rules_without_registration",
        "test_cli.py::test_explicit_wrong_rules_digest_is_still_rejected",
    ),
    "hs-knowledge-lint": ("test_cli.py", "test_local_check.py", "test_module_mapping.py"),
    "hs-knowledge-maintain": ("test_code_navigation.py",),
    "hs-knowledge-query": ("test_cli.py", "test_qualification.py"),
    "hs-knowledge-source": (
        "test_capture_cli.py::test_missing_request_returns_structured_error_without_creating_knowledge",
        "test_capture_cli.py::test_source_capture_returns_business_artifact_without_handoff_manifest",
        "test_manual_entry.py", "test_execution_history_boundary.py",
    ),
    "hs-knowledge-view-materialize": (
        "test_cli.py::test_missing_request_returns_structured_error_without_creating_knowledge",
        "test_cli.py::test_complete_stable_view_contains_card_navigation_and_lock",
    ),
    "domain-and-integration": (
        "test_acceptance_runner.py", "test_contracts.py", "test_staging_contracts.py", "test_workspace_mapping.py",
    ),
}


def select_groups(root, profile, requested):
    packages = sorted(path for path in (root / "skills/common/knowledge").glob("hs-*/tests")
                      if (path.parent / "SKILL.md").is_file())
    available = [(i, path.parent.name, path) for i, path in enumerate(packages)]
    available.append((len(available), "domain-and-integration", root / "himate-knowledge-wifi-mp/evals/tests"))
    labels = {label for _, label, _ in available}
    unknown = set(requested or ()) - labels
    if unknown:
        raise ValueError("Unknown group: " + ", ".join(sorted(unknown)))
    selected = []
    for number, label, path in available:
        if requested and label not in requested:
            continue
        if profile == "full":
            selected.append((number, label, (path,)))
            continue
        if label not in QUICK_FILES:
            if requested:
                raise ValueError("No quick selection for group: " + label)
            continue
        selectors = []
        for relative in QUICK_FILES[label]:
            file, separator, node = relative.partition("::")
            test = path / file
            if not test.is_file() or not test.resolve().is_relative_to(path.resolve()):
                raise ValueError("Quick test file is missing or outside its group: " + relative)
            selectors.append(str(test) + separator + node if separator else test)
        selected.append((number, label, tuple(selectors)))
    if not selected:
        raise ValueError("No groups selected")
    return selected


def stop_process_tree(process):
    """Stop only this test group's descendants, including a CLI awaiting pytest."""
    if os.name == "nt":
        try:
            killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if killed.returncode == 0:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass


def execute_pytest(command, environment, timeout):
    # Inherited pipes can keep Windows communicate reader threads alive after a
    # timeout; closing those pipes can then block on the reader's buffered lock.
    # Ordinary temporary files have no reader threads and retain flushed output.
    with tempfile.TemporaryFile(buffering=0) as stdout, tempfile.TemporaryFile(buffering=0) as stderr:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr,
                                   start_new_session=os.name != "nt",
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        timed_out, cleanup_unconfirmed = False, False
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            exit_code, timed_out = 124, True
            stop_process_tree(process)
            try:
                process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
                try:
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    cleanup_unconfirmed = True
        # Snapshot a finite byte count even if a platform could not stop every
        # descendant and one still owns a file handle.
        outputs = []
        for stream in (stdout, stderr):
            size = os.fstat(stream.fileno()).st_size
            stream.seek(0)
            outputs.append(stream.read(size))
        if cleanup_unconfirmed:
            outputs[1] += b"\nRunner could not confirm process exit after bounded cleanup.\n"
        return exit_code, outputs[0], outputs[1], timed_out


def run_group(item, output, environment):
    number, label, paths = item
    xml = output / f"{number:02d}.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--import-mode=importlib",
        *(str(path) for path in paths),
        "-q",
        "--basetemp",
        str(output / "t" / f"{number:02d}"),
        "--junitxml",
        str(xml),
    ]
    started = time.monotonic()
    diagnostic, stdout, stderr, timed_out = None, b"", b"", False
    try:
        exit_code, stdout, stderr, timed_out = execute_pytest(command, environment, 900)
        if timed_out:
            diagnostic = "Group timed out after 900 seconds; partial reports retained"
    except OSError as exc:
        exit_code, diagnostic = 2, "Could not launch group: " + str(exc)
        stderr = diagnostic.encode("utf-8")
    (output / f"{number:02d}.stdout.txt").write_bytes(stdout)
    (output / f"{number:02d}.stderr.txt").write_bytes(stderr)
    counts, cases = dict.fromkeys(COUNT_KEYS, 0), []
    try:
        counts, cases = read_junit(xml, label, paths, ROOT)
    except (OSError, ValueError, SyntaxError) as exc:
        diagnostic = (diagnostic + "; " if diagnostic else "") + "JUnit unavailable or invalid: " + str(exc)
        exit_code = exit_code or 2
    if exit_code == 0 and counts["tests"] == 0:
        exit_code, diagnostic = 2, "Group reported no tests"
    return {"group": label, "exit_code": exit_code, "seconds": round(time.monotonic() - started, 3),
            "timed_out": timed_out, "diagnostic": diagnostic, "cases": cases, **counts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--jobs", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--profile", choices=("quick", "full"), default="full")
    parser.add_argument("--groups", nargs="+", help="Exact group names; default includes every group available to the profile")
    parser.add_argument("--baseline", type=Path, help="Previous summary.json; comparison is advisory only")
    args = parser.parse_args(argv)
    try:
        groups = select_groups(ROOT, args.profile, args.groups)
    except ValueError as exc:
        parser.error(str(exc))
    output = Path(args.output_dir).absolute()
    if output.exists():
        parser.error("Use a new output directory; previous evidence is never removed")
    for path in (output, *output.parents):
        if path.is_symlink():
            parser.error("Linked output paths are not accepted")
    output.mkdir(parents=True)
    (output / "t").mkdir()
    env = dict(os.environ, HIMATE_TEST_TMP=str(output / "unittest-tmp"))
    # Selection belongs to this command, not a hidden inherited -k/-m/-x.
    env.pop("PYTEST_ADDOPTS", None)
    environment = runtime_environment(ROOT)
    selection = []
    for _, label, paths in groups:
        selectors = []
        for selector in paths:
            file, separator, node = str(selector).partition("::")
            selectors.append(Path(file).relative_to(ROOT).as_posix() + separator + node)
        selection.append({"group": label, "paths": selectors})
    started = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_group, item, output, env): item for item in groups}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                # A runner/reporting error must not discard other completed groups.
                result = {"group": item[1], "exit_code": 2, "seconds": 0.0, "timed_out": False,
                          "diagnostic": "Runner error: " + str(exc), "cases": [], **dict.fromkeys(COUNT_KEYS, 0)}
            results.append(result)
            print(f"[{len(results)}/{len(groups)}] {result['group']}: exit={result['exit_code']} "
                  f"tests={result['tests']} seconds={result['seconds']:.3f}", flush=True)
    wall_seconds = time.monotonic() - started
    order = {item[1]: item[0] for item in groups}
    results.sort(key=lambda row: order[row["group"]])
    report = {
        "schema_version": "2.0",
        "verification_tier": "isolated_synthetic_mechanisms",
        "profile": args.profile, "jobs": args.jobs, "environment": environment,
        "selection_scope": "full_suite" if args.profile == "full" and not args.groups else "partial",
        "selection": selection,
        "groups": [{key: value for key, value in row.items() if key != "cases"} for row in results],
        "passed": all(row["exit_code"] == 0 for row in results),
        "totals": {key: sum(row[key] for row in results) for key in COUNT_KEYS},
        "performance": performance_report(results, wall_seconds),
        "limitations": [
            "No implicit host triggering or review-context isolation acceptance",
            "No real six Target or CI/publication/ACL acceptance",
            "No restricted gold accessed",
            "Quick or group-filtered runs provide partial coverage; full is the default",
            "Performance is observational; setup/call/teardown and CLI counts are not sampled",
        ],
    }
    if args.baseline:
        report["performance"]["comparison"] = compare_baseline(report, args.baseline)
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
