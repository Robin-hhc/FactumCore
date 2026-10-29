"""Soft benchmark observations must not become performance pass/fail gates."""

import importlib.util
from pathlib import Path
import subprocess

import pytest


SPEC = importlib.util.spec_from_file_location("benchmark_metrics", Path(__file__).parents[1] / "benchmark_ingest.py")
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)


def report(**overrides):
    return {"verification_tier": "local_synthetic_document_flow", "instrumented": False,
            "environment": {"python": "3.12", "platform": "fixture"},
            "workload": {"id": "fixture", "source_sha256": "a" * 64}, "median_seconds": 2, **overrides}


def test_document_metrics_preserves_actual_calls_and_small_sample_distribution():
    rows = [{"seconds": duration, "outer_cli_calls": [
        {"skill": "apply", "action": "batch", "seconds": duration / 2},
        {"skill": "query", "action": "search", "seconds": duration / 4}]} for duration in (4, 2, 6)]
    result = BENCH.document_metrics(rows)
    assert result["flow"] == {"samples": 3, "min_seconds": 2, "median_seconds": 4, "max_seconds": 6}
    assert result["outer_cli_calls_per_run"] == [2, 2, 2]
    assert result["actions"]["apply/batch"]["median_seconds"] == 2
    assert result["actions"]["query/search"]["samples"] == 3


def test_large_timing_increase_is_an_advisory_observation():
    result = BENCH.compare_baseline(report(median_seconds=200), report())
    assert result["comparable"] is True and result["advisory_only"] is True
    assert result["changes"]["median_seconds"]["ratio"] == 100


@pytest.mark.parametrize("changed", [
    {"instrumented": True}, {"workload": {"id": "different"}}, {"environment": {"python": "3.10"}},
    {"verification_tier": "local_synthetic_symbol_lookup"},
])
def test_incompatible_observations_are_not_compared(changed):
    result = BENCH.compare_baseline(report(**changed), report())
    assert result["comparable"] is False and result["reasons"]


def test_old_baseline_with_missing_metadata_is_explicitly_incomparable():
    assert BENCH.compare_baseline(report(), {"median_seconds": 1})["comparable"] is False


def test_zero_baseline_has_no_invented_ratio():
    assert BENCH.compare_baseline(report(), report(median_seconds=0))["changes"]["median_seconds"]["ratio"] is None


@pytest.mark.parametrize("value", [float("inf"), float("nan"), -1, "unknown", 10**400])
def test_invalid_baseline_timing_is_not_compared(value):
    assert BENCH.compare_baseline(report(), report(median_seconds=value))["comparable"] is False


def test_invalid_baseline_and_unavailable_git_preserve_measurements(tmp_path, monkeypatch):
    lock = tmp_path / "himate-knowledge-wifi-mp/governance/framework.lock.yaml"
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b"fixture lock")
    baseline = tmp_path / "baseline.json"
    baseline.write_bytes(b"{unfinished")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 15)

    monkeypatch.setattr(BENCH.subprocess, "run", timeout)
    measured = BENCH.finish_report(report(), tmp_path, baseline)
    assert measured["median_seconds"] == 2 and measured["commit"] is None
    assert measured["comparison"]["comparable"] is False
    assert measured["comparison"]["advisory_only"] is True
