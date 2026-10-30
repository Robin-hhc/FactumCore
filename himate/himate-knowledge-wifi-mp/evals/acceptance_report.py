"""Standard-library reporting for the isolated test runner; no business imports."""

from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET


COUNT_KEYS = ("tests", "failures", "errors", "skipped")
ENVIRONMENT_KEYS = ("python_version", "python_implementation", "system", "release", "machine", "processor", "cpu_count")


def runtime_environment(root):
    """Record observations, without changing Git, dependencies or the issued rules lock."""
    data = {"python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
            "python_executable": sys.executable, "system": platform.system(),
            "release": platform.release(), "machine": platform.machine(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "commit": None, "rules_digest": None}
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, timeout=5,
                                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        if result.returncode == 0:
            data["commit"] = result.stdout.decode("ascii").strip()
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        pass
    lock = root / "himate/himate-knowledge-wifi-mp/governance/framework.lock.yaml"
    try:
        data["rules_digest"] = hashlib.sha256(lock.read_bytes()).hexdigest()
    except OSError:
        pass
    return data


def _test_modules(paths, root):
    aliases = {}
    for selector in paths:
        selected = Path(str(selector).split("::", 1)[0])
        files = selected.rglob("test_*.py") if selected.is_dir() else (selected,)
        for path in files:
            relative = path.relative_to(root)
            parts = relative.with_suffix("").parts
            # pytest resolves this project's configured rootdir to evals. Keep
            # both repository paths and classified root-relative classnames;
            # the old tests.test_file form remains useful for saved reports.
            names = {".".join(parts), path.stem}
            if "evals" in parts:
                names.add(".".join(parts[parts.index("evals") + 1:]))
            if "tests" in parts:
                names.add(".".join(parts[parts.index("tests"):]))
            for name in names:
                aliases[name] = relative.as_posix()
    return sorted(aliases.items(), key=lambda row: len(row[0]), reverse=True)


def read_junit(path, group, paths, root):
    tree = ET.parse(path).getroot()
    counts = dict.fromkeys(COUNT_KEYS, 0)
    for suite in tree.iter("testsuite"):
        if suite.find("testsuite") is None:
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
    aliases = _test_modules(paths, root)
    cases = []
    for test in tree.iter("testcase"):
        classname, name = test.get("classname", ""), test.get("name", "")
        file = test.get("file")
        nodeid = classname + "::" + name
        for alias, relative in aliases:
            if classname == alias or classname.startswith(alias + "."):
                file = relative
                suffix = classname[len(alias):].strip(".").replace(".", "::")
                nodeid = relative + "::" + (suffix + "::" if suffix else "") + name
                break
        seconds = float(test.get("time", "0"))
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("JUnit contains invalid test timing")
        outcome = next((kind for tag, kind in (("failure", "failed"), ("error", "error"), ("skipped", "skipped"))
                        if test.find(tag) is not None), "passed")
        cases.append({"group": group, "nodeid": nodeid, "file": file or classname,
                      "seconds": seconds, "outcome": outcome})
    return counts, cases


def performance_report(groups, wall_seconds):
    cases = sorted((case for group in groups for case in group["cases"]), key=lambda row: (row["group"], row["nodeid"]))
    files = defaultdict(lambda: {"tests": 0, "seconds": 0.0})
    for case in cases:
        row = files[(case["group"], case["file"])]
        row["tests"] += 1
        row["seconds"] += case["seconds"]
    slow_files = [{"group": key[0], "file": key[1], **row, "seconds": round(row["seconds"], 6)}
                  for key, row in files.items()]
    return {"advisory": True, "suite_wall_seconds": round(wall_seconds, 6),
            "group_wall_seconds_sum": round(sum(group["seconds"] for group in groups), 6),
            "test_seconds_sum": round(sum(case["seconds"] for case in cases), 6),
            "selected_tests": len(cases), "selected_count_source": "JUnit reported cases; incomplete on interrupted groups",
            "test_timing_scope": "JUnit per-case total; parallel group sums are not suite wall time",
            "slowest_tests": sorted(cases, key=lambda row: row["seconds"], reverse=True)[:20],
            "slowest_files": sorted(slow_files, key=lambda row: row["seconds"], reverse=True)[:20],
            "test_cases": cases, "unavailable_metrics": ["setup/call/teardown", "CLI invocation count"],
            "comparison": None, "environment_limitations": "Machine load and filesystem caches are uncontrolled; hardware descriptors may be unavailable"}


def _delta(current, baseline):
    return {"current_seconds": current, "baseline_seconds": baseline,
            "delta_seconds": round(current - baseline, 6),
            "ratio": round(current / baseline, 4) if baseline else None}


def _valid_seconds(value):
    if (not isinstance(value, (int, float)) or value < 0 or value > sys.float_info.max
            or not math.isfinite(value)):
        raise ValueError("Baseline has invalid timing values")


def compare_baseline(current, path):
    """Advisory only: never edit passed/exit status, including invalid old reports."""
    unavailable = {"advisory": True, "status": "unavailable", "baseline": str(path)}
    try:
        baseline = json.loads(Path(path).read_text(encoding="utf-8"))
        for report in (current, baseline):
            if not isinstance(report, dict) or not all(key in report for key in ("environment", "profile", "jobs", "selection", "performance")):
                raise ValueError("Baseline lacks current runner metadata; old summaries are not assumed comparable")
            if not all(key in report["environment"] for key in ENVIRONMENT_KEYS):
                raise ValueError("Environment metadata is incomplete")
        if current["profile"] != baseline["profile"] or current["jobs"] != baseline["jobs"]:
            raise ValueError("Profile or jobs differs")
        if any(current["environment"][key] != baseline["environment"][key] for key in ENVIRONMENT_KEYS):
            raise ValueError("Python or platform differs")
        indices = []
        for report in (current, baseline):
            cases = report["performance"]["test_cases"]
            _valid_seconds(report["performance"]["suite_wall_seconds"])
            for case in cases:
                _valid_seconds(case["seconds"])
            index = {(case["group"], case["nodeid"]): case for case in cases}
            if len(index) != len(cases):
                raise ValueError("Duplicate test identities prevent baseline comparison")
            indices.append(index)
        now, before = indices
        common = now.keys() & before.keys()
        inventory_equal = now.keys() == before.keys()
        selection_equal = current["selection"] == baseline["selection"] and inventory_equal
        complete = current.get("passed") is True and baseline.get("passed") is True
        changes = [{"group": key[0], "nodeid": key[1], **_delta(now[key]["seconds"], before[key]["seconds"])}
                   for key in sorted(common)
                   if now[key].get("outcome") == "passed" and before[key].get("outcome") == "passed"]
        suite = (_delta(current["performance"]["suite_wall_seconds"], baseline["performance"]["suite_wall_seconds"])
                 if selection_equal and complete else None)
        return {"advisory": True, "status": "compared", "baseline": str(path), "selection_equal": selection_equal,
                "suite_wall": suite, "matched_tests": len(common), "timed_passed_tests": len(changes),
                "added_tests": len(now.keys() - before.keys()), "removed_tests": len(before.keys() - now.keys()),
                "slowdowns": sorted((row for row in changes if row["delta_seconds"] > 0),
                                    key=lambda row: row["delta_seconds"], reverse=True)[:20],
                "note": "No performance threshold changes test exit status. Total comparison requires complete, identical selections; matched passed cases remain advisory."}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {**unavailable, "reason": str(exc)}
