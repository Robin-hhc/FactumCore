"""Measure a synthetic document flow in a supplied checkout; no host/API claim.

Run baseline and candidate with the same Python and a fresh short output path.
The fixture executes real public CLIs, activation, search and same-generation
read. Synthetic review declarations stand in for host/model work.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time


PROBE = '''import atexit, collections, json, os, sys
counts = collections.Counter()
def profile(frame, event, arg):
    if event != "call":
        return
    path = frame.f_code.co_filename.replace("\\\\", "/")
    name = frame.f_code.co_name
    if "/governance/contracts/" in path and (path.rsplit("/", 1)[-1], name) in {
        ("checks.py", "run"), ("knowledge.py", "parse_card"),
        ("knowledge.py", "validate_relations"), ("indexing.py", "verify_database"),
        ("index_runtime.py", "verify_generation")}:
        counts[path.rsplit("/", 1)[-1] + ":" + name] += 1
def save():
    path = os.path.join(os.environ["HIMATE_BENCH_TRACE"], str(os.getpid()) + ".json")
    with open(path, "x", encoding="utf-8") as stream:
        json.dump(dict(counts), stream, sort_keys=True)
atexit.register(save)
sys.setprofile(profile)
'''


def worker(checkout, output):
    sys.path.insert(0, str(checkout / "himate/himate-knowledge-wifi-mp/evals"))
    fixture_path = checkout / "himate/himate-knowledge-wifi-mp/evals/support/correction.py"
    spec = importlib.util.spec_from_file_location("measured_document_fixture", fixture_path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    harness = fixture.frozen_harness(output)
    original = ("# Source\nSynthetic fixture statement for test readers.\n" +
                "Supporting synthetic context line.\n" * 298).encode()
    harness.write("docs-raw/specs/source.md", original)
    calls = []
    actual_run = subprocess.run

    def timed_run(command, *args, **kwargs):
        started = time.perf_counter()
        result = actual_run(command, *args, **kwargs)
        if isinstance(command, (list, tuple)) and any(str(x).replace("\\", "/").endswith("knowledge.py") for x in command):
            cli = next(str(x) for x in command if str(x).replace("\\", "/").endswith("knowledge.py"))
            action = command[command.index("--action") + 1] if "--action" in command else "default"
            calls.append({"skill": "hs-knowledge-" + str(command[command.index(cli) + 1]), "action": action,
                          "seconds": round(time.perf_counter() - started, 6), "exit_code": result.returncode})
        return result

    subprocess.run = timed_run
    started = time.perf_counter()
    fixture.complete_document_operation(harness, "measured", "create", "Synthetic fixture statement.")
    elapsed = time.perf_counter() - started
    if (checkout / "skills/common/knowledge/hs-knowledge-source/SKILL.md").is_file():
        # The candidate's normal workflow must measure the combined public run,
        # not two independent actions or rewritten historical fixture results.
        assert [row["action"] for row in calls if row["skill"] == "hs-knowledge-source"] == ["run", "record"]
    assert (harness.root / "docs-raw/specs/source.md").read_bytes() == original
    return {"seconds": round(elapsed, 6), "outer_cli_calls": calls,
            "source_sha256": hashlib.sha256(original).hexdigest(), "source_lines": 300,
            "verified": ["actual_activation", "formal_search", "same_generation_read", "unchanged_original"]}


def symbol_worker(checkout):
    """Measure the public byte resolver separately from CLI and document work."""
    helper_path = checkout / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py"
    spec = importlib.util.spec_from_file_location("measured_symbol_contracts", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    symbols = helper.module("code_symbols")
    count = 1000
    original = "".join(f"int symbol_{i}(const int *value) {{ return *value; }}\n" for i in range(count)).encode()
    selector = {"kind": "function", "name": "symbol_0", "parameter_types": ["const int *"]}
    cache = {}
    started = time.perf_counter()
    first = symbols.resolve(original, selector, path="synthetic.c", cache=cache)
    cold = time.perf_counter() - started
    assert first["status"] == "resolved" and first["range"]["start_line"] == 1
    started = time.perf_counter()
    for number in range(count):
        result = symbols.resolve(original, {**selector, "name": f"symbol_{number}"}, path="synthetic.c", cache=cache)
        assert result["status"] == "resolved" and result["range"]["start_line"] == number + 1
    return {"verification_tier": "local_synthetic_symbol_lookup", "python": sys.version,
            "symbols": count, "lookups": count, "cold_seconds": round(cold, 6),
            "cached_lookup_seconds": round(time.perf_counter() - started, 6),
            "source_sha256": hashlib.sha256(original).hexdigest(),
            "limitations": ["In-memory C source only; no CLI, filesystem, build, LLM or host latency",
                            "Timing is diagnostic and is not a correctness or speed threshold"]}


def environment():
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count()}


def timing_stats(samples):
    """Small samples are observations; avoid giving three runs a tail percentile."""
    return {"samples": len(samples), "min_seconds": min(samples),
            "median_seconds": statistics.median(samples), "max_seconds": max(samples)}


def document_metrics(results):
    actions = {}
    for row in results:
        for call in row["outer_cli_calls"]:
            actions.setdefault(call["skill"] + "/" + call["action"], []).append(call["seconds"])
    return {"flow": timing_stats([row["seconds"] for row in results]),
            "outer_cli_calls_per_run": [len(row["outer_cli_calls"]) for row in results],
            "actions": {key: timing_stats(values) for key, values in sorted(actions.items())}}


def compare_baseline(report, baseline):
    """A comparison is advisory even when the measured latency increases."""
    reasons = []
    if not isinstance(baseline, dict):
        return {"advisory_only": True, "comparable": False, "reasons": ["Baseline is not an object"]}
    for key in ("verification_tier", "instrumented", "environment", "workload"):
        if key not in baseline or key not in report or baseline[key] != report[key]:
            reasons.append(key + " missing or different")
    if reasons:
        return {"advisory_only": True, "comparable": False, "reasons": reasons}
    keys = ("median_seconds",) if "median_seconds" in report else ("cold_seconds", "cached_lookup_seconds")
    changes = {}
    for key in keys:
        old, new = baseline.get(key), report.get(key)
        if (not isinstance(old, (int, float)) or not isinstance(new, (int, float))
                or min(old, new) < 0 or max(old, new) > sys.float_info.max
                or not math.isfinite(old) or not math.isfinite(new)):
            return {"advisory_only": True, "comparable": False, "reasons": [key + " invalid or absent"]}
        changes[key] = {"baseline": old, "current": new, "delta_seconds": new - old,
                        "ratio": new / old if old else None}
    return {"advisory_only": True, "comparable": True, "changes": changes,
            "note": "Same declared workload and environment; machine load and cache state are uncontrolled"}


def finish_report(report, checkout, baseline):
    report["environment"] = environment()
    report["commit"] = None
    try:
        commit = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                                capture_output=True, timeout=15, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        if commit.returncode == 0:
            report["commit"] = commit.stdout.decode("ascii", errors="replace").strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    report["rules_sha256"] = hashlib.sha256(
        (checkout / "himate/himate-knowledge-wifi-mp/governance/framework.lock.yaml").read_bytes()).hexdigest()
    if baseline:
        try:
            report["comparison"] = compare_baseline(report, json.loads(Path(baseline).read_bytes()))
        except (OSError, ValueError, UnicodeError) as exc:
            report["comparison"] = {"advisory_only": True, "comparable": False, "reasons": [str(exc)]}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--runs", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--instrument", action="store_true", help="Separate call-count probe; includes profiling overhead")
    parser.add_argument("--symbols", action="store_true", help="Measure symbol parsing and same-file cached lookups only")
    parser.add_argument("--baseline", help="Compare a prior summary as a soft observation; never a speed gate")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    checkout, output = Path(args.checkout).resolve(strict=True), Path(args.output_dir).absolute()
    if args.worker:
        print(json.dumps(worker(checkout, output)))
        return 0
    if output.exists() or any(path.is_symlink() for path in (output, *output.parents)):
        parser.error("Use a fresh, unlinked output directory")
    output.mkdir(parents=True)
    if args.symbols:
        report = symbol_worker(checkout)
        report.update(instrumented=False, workload={"id": "c-symbols-1000-v1", "symbols": report["symbols"],
                      "lookups": report["lookups"], "source_sha256": report["source_sha256"]})
        finish_report(report, checkout, args.baseline)
        (output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
        return 0
    probe = output / "probe"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text(PROBE, encoding="utf-8")
    results = []
    for number in range(args.runs):
        run = output / str(number)
        run.mkdir()
        trace = run / "trace"
        trace.mkdir()
        env = dict(os.environ, HIMATE_TEST_TMP=str(run), PYTHONDONTWRITEBYTECODE="1")
        if args.instrument:
            env.update(HIMATE_BENCH_TRACE=str(trace),
                       PYTHONPATH=os.pathsep.join(filter(None, (str(probe), os.environ.get("PYTHONPATH")))))
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker",
                                  "--checkout", str(checkout), "--output-dir", str(run)],
                                 env=env, capture_output=True, timeout=300)
        (run / "stdout.txt").write_bytes(process.stdout)
        (run / "stderr.txt").write_bytes(process.stderr)
        if process.returncode:
            raise RuntimeError("Benchmark failed; inspect " + str(run / "stderr.txt"))
        result = json.loads(process.stdout)
        counters = {}
        traces = list(trace.glob("*.json"))
        for path in traces:
            for key, value in json.loads(path.read_bytes()).items():
                counters[key] = counters.get(key, 0) + value
        result.update(python_processes=len(traces) - 1 if args.instrument else None, contract_calls=counters)
        results.append(result)
    report = {"verification_tier": "local_synthetic_document_flow", "instrumented": args.instrument,
              "python": sys.version, "runs": results,
              "median_seconds": statistics.median(row["seconds"] for row in results),
              "limitations": ["Profiled call counts require a separate --instrument run; its overhead is not a normal latency measurement",
                              "No LLM, company API, SSH or OpenFlow host timing",
                              "One card from a 300-line synthetic source; no semantic quality benchmark"]}
    report["metrics"] = document_metrics(results)
    report["workload"] = {"id": "document-create-query-v1", "source_lines": results[0]["source_lines"],
                          "source_sha256": results[0]["source_sha256"],
                          "cli_sequence": [[row["skill"], row["action"]] for row in results[0]["outer_cli_calls"]]}
    finish_report(report, checkout, args.baseline)
    (output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
