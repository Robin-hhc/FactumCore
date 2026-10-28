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
import os
from pathlib import Path
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
    fixture_path = checkout / "himate-knowledge-wifi-mp/evals/tests/test_post_ingest_correction.py"
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
        if isinstance(command, (list, tuple)) and any(str(x).replace("\\", "/").endswith("scripts/cli.py") for x in command):
            cli = next(str(x) for x in command if str(x).replace("\\", "/").endswith("scripts/cli.py"))
            action = command[command.index("--action") + 1] if "--action" in command else "default"
            calls.append({"skill": Path(cli).parents[1].name, "action": action,
                          "seconds": round(time.perf_counter() - started, 6), "exit_code": result.returncode})
        return result

    subprocess.run = timed_run
    started = time.perf_counter()
    fixture.complete_document_operation(harness, "measured", "create", "Synthetic fixture statement.")
    elapsed = time.perf_counter() - started
    assert (harness.root / "docs-raw/specs/source.md").read_bytes() == original
    return {"seconds": round(elapsed, 6), "outer_cli_calls": calls,
            "source_sha256": hashlib.sha256(original).hexdigest(), "source_lines": 300,
            "verified": ["actual_activation", "formal_search", "same_generation_read", "unchanged_original"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--runs", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--instrument", action="store_true", help="Separate call-count probe; includes profiling overhead")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    checkout, output = Path(args.checkout).resolve(strict=True), Path(args.output_dir).absolute()
    if args.worker:
        print(json.dumps(worker(checkout, output)))
        return 0
    if output.exists() or any(path.is_symlink() for path in (output, *output.parents)):
        parser.error("Use a fresh, unlinked output directory")
    output.mkdir(parents=True)
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
    (output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
