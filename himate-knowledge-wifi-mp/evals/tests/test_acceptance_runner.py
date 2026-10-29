"""Runner selection, incomplete execution and advisory reporting use no business fixtures."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


EVALS = Path(__file__).resolve().parents[1]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(EVALS))
    spec = importlib.util.spec_from_file_location("acceptance_runner_test_subject", EVALS / "run_acceptance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workspace(tmp_path):
    for label in ("hs-knowledge-one", "hs-knowledge-two"):
        package = tmp_path / "skills/common/knowledge" / label
        (package / "tests").mkdir(parents=True)
        (package / "SKILL.md").write_text("fixture", encoding="utf-8")
        (package / "tests/test_smoke.py").write_text("", encoding="utf-8")
    (tmp_path / "himate-knowledge-wifi-mp/evals/tests").mkdir(parents=True)
    return tmp_path


def test_full_is_directory_selection_and_covers_new_files(runner, tmp_path):
    root = workspace(tmp_path)
    groups = runner.select_groups(root, "full", None)
    assert [item[1] for item in groups] == ["hs-knowledge-one", "hs-knowledge-two", "domain-and-integration"]
    assert all(len(item[2]) == 1 and item[2][0].is_dir() for item in groups)
    (groups[0][2][0] / "test_future.py").write_text("", encoding="utf-8")
    assert runner.select_groups(root, "full", ["hs-knowledge-one"]) == groups[:1]


def test_quick_has_explicit_files_and_rejects_missing_or_unknown_selection(runner, monkeypatch, tmp_path):
    root = workspace(tmp_path)
    monkeypatch.setattr(runner, "QUICK_FILES", {"hs-knowledge-one": ("test_smoke.py",)})
    selected = runner.select_groups(root, "quick", None)
    assert selected == [(0, "hs-knowledge-one", (root / "skills/common/knowledge/hs-knowledge-one/tests/test_smoke.py",))]
    with pytest.raises(ValueError, match="Unknown group"):
        runner.select_groups(root, "full", ["one"])
    with pytest.raises(ValueError, match="No quick selection"):
        runner.select_groups(root, "quick", ["hs-knowledge-two"])
    (selected[0][2][0]).unlink()
    with pytest.raises(ValueError, match="Quick test file"):
        runner.select_groups(root, "quick", None)


def test_real_quick_selectors_exist_and_cover_all_current_groups(runner):
    full = runner.select_groups(runner.ROOT, "full", None)
    quick = runner.select_groups(runner.ROOT, "quick", None)
    assert {item[1] for item in quick} == {item[1] for item in full}
    assert all(Path(str(path).split("::", 1)[0]).is_file() for _, _, paths in quick for path in paths)


def write_junit(path):
    path.write_text('<testsuites><testsuite tests="2" failures="0" errors="0" skipped="1">'
                    '<testcase classname="tests.test_demo.Suite" name="test_a" time="2.5" />'
                    '<testcase classname="tests.test_demo" name="test_b[x]" time="0.5"><skipped /></testcase>'
                    '</testsuite></testsuites>', encoding="utf-8")


def test_junit_identifies_cases_and_aggregates_total_timing(runner, tmp_path):
    tests = tmp_path / "himate-knowledge-wifi-mp/evals/tests"
    tests.mkdir(parents=True)
    (tests / "test_demo.py").write_text("", encoding="utf-8")
    xml = tmp_path / "results.xml"
    write_junit(xml)
    counts, cases = runner.read_junit(xml, "domain-and-integration", (tests,), tmp_path)
    assert counts == {"tests": 2, "failures": 0, "errors": 0, "skipped": 1}
    assert cases[0]["nodeid"] == "himate-knowledge-wifi-mp/evals/tests/test_demo.py::Suite::test_a"
    assert cases[1]["outcome"] == "skipped"
    _, selected = runner.read_junit(xml, "domain-and-integration", (str(tests / "test_demo.py") + "::Suite::test_a",), tmp_path)
    assert selected[0]["nodeid"] == cases[0]["nodeid"]
    metrics = runner.performance_report([{**counts, "seconds": 4.0, "cases": cases}], 4.2)
    assert metrics["suite_wall_seconds"] == 4.2
    assert metrics["group_wall_seconds_sum"] == 4.0
    assert metrics["test_seconds_sum"] == 3.0
    assert metrics["selected_tests"] == 2
    assert metrics["slowest_files"][0]["seconds"] == 3.0
    assert metrics["advisory"] is True
    assert "setup/call/teardown" in metrics["unavailable_metrics"]


@pytest.mark.parametrize("kind", ["timeout", "missing_xml", "malformed_xml", "spawn_error"])
def test_incomplete_group_retains_output_and_fails(runner, monkeypatch, tmp_path, kind):
    def execute(*args, **kwargs):
        if kind == "spawn_error":
            raise OSError("cannot launch fixture")
        if kind == "malformed_xml":
            (tmp_path / "00.xml").write_text("<broken", encoding="utf-8")
        return (124 if kind == "timeout" else 0, b"partial stdout", b"partial stderr", kind == "timeout")

    monkeypatch.setattr(runner, "execute_pytest", execute)
    result = runner.run_group((0, "fixture", (tmp_path / "tests",)), tmp_path, {})
    assert result["exit_code"] != 0
    assert result["diagnostic"]
    assert (tmp_path / "00.stdout.txt").exists()
    assert (tmp_path / "00.stderr.txt").exists()
    if kind != "spawn_error":
        assert (tmp_path / "00.stdout.txt").read_bytes() == b"partial stdout"


def test_timeout_stops_process_tree_and_collects_partial_output(runner, monkeypatch):
    class Process:
        returncode = 124

        def __init__(self):
            self.calls = 0

        def wait(self, timeout):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("fixture", timeout)
            return self.returncode

    process = Process()
    stopped = []

    def launch(*args, **kwargs):
        assert kwargs["stdout"] != subprocess.PIPE and kwargs["stderr"] != subprocess.PIPE
        kwargs["stdout"].write(b"partial and flushed")
        kwargs["stderr"].write(b"stderr")
        return process

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner, "stop_process_tree", lambda p: stopped.append(p))
    result = runner.execute_pytest(["fixture"], {}, 0.01)
    assert stopped == [process]
    assert result == (124, b"partial and flushed", b"stderr", True)


def test_real_timeout_keeps_flushed_stdout_and_stderr_without_pipe_readers(runner):
    command = [sys.executable, "-u", "-c", "import sys, threading; print('ready', flush=True); "
               "print('error ready', file=sys.stderr, flush=True); threading.Event().wait()"]
    code, stdout, stderr, timed_out = runner.execute_pytest(command, dict(os.environ), 2)
    assert code == 124 and timed_out is True
    assert stdout.strip() == b"ready" and stderr.strip() == b"error ready"


@pytest.mark.parametrize("failure", ["exit", "timeout", "oserror"])
def test_windows_taskkill_failure_falls_back_to_direct_kill(runner, monkeypatch, failure):
    process = SimpleNamespace(pid=12345, kill=lambda: killed.append(True))
    killed = []

    def taskkill(*args, **kwargs):
        assert args[0] == ["taskkill", "/PID", "12345", "/T", "/F"]
        assert kwargs["timeout"] == 10
        if failure == "timeout":
            raise subprocess.TimeoutExpired("taskkill", 10)
        if failure == "oserror":
            raise OSError("not available")
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(runner.subprocess, "run", taskkill)
    runner.stop_process_tree(process)
    assert killed == [True]


@pytest.mark.parametrize("kill_error", [False, True])
def test_timeout_cleanup_has_bounded_waits_when_process_will_not_exit(runner, monkeypatch, kill_error):
    waits, kills = [], []

    class Process:
        def wait(self, timeout):
            waits.append(timeout)
            raise subprocess.TimeoutExpired("fixture", timeout)

        def kill(self):
            kills.append(True)
            if kill_error:
                raise OSError("already gone or inaccessible")

    def launch(*args, **kwargs):
        kwargs["stdout"].write(b"partial")
        kwargs["stderr"].write(b"diagnostic")
        return Process()

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner, "stop_process_tree", lambda process: None)
    result = runner.execute_pytest(["fixture"], {}, 0.01)
    assert result[:2] == (124, b"partial") and result[3] is True
    assert result[2].startswith(b"diagnostic")
    assert waits == [0.01, 10, 5] and kills == [True]


def report_fixture():
    return {"passed": True, "profile": "full", "jobs": 3,
            "environment": {"python_version": "3.11.1", "python_implementation": "CPython",
                            "system": "fixture", "release": "one", "machine": "x64",
                            "processor": "fixture-cpu", "cpu_count": 4},
            "selection": [{"group": "one", "paths": ["tests"]}],
            "performance": {"suite_wall_seconds": 10.0, "test_cases": [
                {"group": "one", "nodeid": "tests/test_a.py::test_a", "seconds": 2.0, "outcome": "passed"}]}}


def test_baseline_comparison_is_advisory_and_uses_matching_inventory(runner, tmp_path):
    baseline = report_fixture()
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    current = report_fixture()
    current["performance"]["suite_wall_seconds"] = 20.0
    current["performance"]["test_cases"][0]["seconds"] = 8.0
    comparison = runner.compare_baseline(current, path)
    assert comparison["advisory"] is True
    assert comparison["suite_wall"]["delta_seconds"] == 10.0
    assert comparison["slowdowns"][0]["delta_seconds"] == 6.0
    assert current["passed"] is True
    current["performance"]["test_cases"].append({"group": "one", "nodeid": "new", "seconds": 1.0})
    comparison = runner.compare_baseline(current, path)
    assert comparison["suite_wall"] is None
    assert comparison["matched_tests"] == 1 and comparison["added_tests"] == 1


@pytest.mark.parametrize("kind", ["old_schema", "different_environment", "different_hardware", "unreadable", "malformed", "invalid_timing"])
def test_unavailable_baseline_never_invalidates_results(runner, tmp_path, kind):
    current = report_fixture()
    path = tmp_path / "baseline.json"
    baseline = report_fixture()
    if kind == "old_schema":
        baseline = {"schema_version": "2.0", "passed": True, "groups": []}
    if kind == "different_environment":
        baseline["environment"]["machine"] = "another"
    if kind == "different_hardware":
        baseline["environment"]["cpu_count"] = 99
    if kind == "invalid_timing":
        baseline["performance"]["suite_wall_seconds"] = float("nan")
    if kind != "unreadable":
        path.write_text("{broken" if kind == "malformed" else json.dumps(baseline), encoding="utf-8")
    comparison = runner.compare_baseline(current, path)
    assert comparison["status"] == "unavailable"
    assert comparison["reason"]
    assert current["passed"] is True


def test_main_keeps_all_group_results_when_one_group_times_out(runner, monkeypatch, tmp_path, capsys):
    root = workspace(tmp_path / "root")
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "runtime_environment", lambda root: {})
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k hidden_filter")

    def run_group(item, *args):
        assert "PYTEST_ADDOPTS" not in args[1]
        return {"group": item[1], "exit_code": 124 if item[0] == 0 else 0, "seconds": 0.1,
                "tests": 0, "failures": 0, "errors": 0, "skipped": 0, "cases": [],
                "diagnostic": "timed out" if item[0] == 0 else None}

    monkeypatch.setattr(runner, "run_group", run_group)
    output = tmp_path / "output"
    assert runner.main(["--output-dir", str(output)]) == 2
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert len(report["groups"]) == 3 and report["passed"] is False
    assert report["profile"] == "full" and report["selection_scope"] == "full_suite"
    assert "[1/3]" in capsys.readouterr().out


def test_json_integer_outside_float_range_cannot_break_soft_comparison(runner, tmp_path):
    baseline = report_fixture()
    baseline["performance"]["suite_wall_seconds"] = 10**400
    path = tmp_path / "oversized-baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    current = report_fixture()
    assert runner.compare_baseline(current, path)["status"] == "unavailable"
    assert current["passed"] is True
