"""Real native parsing with isolated leases, exact cleanup and process locks."""

import hashlib
import importlib.util
import json
import multiprocessing
from pathlib import Path

import pytest


_spec = importlib.util.spec_from_file_location(
    "source_read_contract_support", Path(__file__).resolve().parents[1] / "support/contracts.py",
)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
module = _helper.module


def source(suffix=".md"):
    return {"id": "doc-design", "source_id": "doc-design", "kind": "raw",
            "path": "docs-raw/design" + suffix}


def create(root, suffix=".md", text="# Design\n\nA documented requirement.\n", **kwargs):
    return module("source_read").create(root, source(suffix), text.encode(), **kwargs)


def snapshot(directory):
    return {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}


def lease_path(root, read_id):
    return root / "artifacts/source-read" / read_id / "lease.json"


def change_lease(root, read_id, **updates):
    path = lease_path(root, read_id)
    value = json.loads(path.read_text())
    value.update(updates)
    path.write_text(json.dumps(value))


def _create_worker(root, start, results):
    try:
        start.wait(10)
        result = create(Path(root))
        results.put(("ready", result))
    except BaseException as error:
        results.put(("error", repr(error)))


def _hold_busy_worker(root, read_id, ready, finish):
    reads = module("source_read")
    root = Path(root)
    with reads._file_lock(reads._busy_path(root, read_id)):
        with reads._guard(root):
            lease = reads._lease(root, read_id)
            lease.update(state="converting", expires_at=0)
            reads._write_lease(root, read_id, lease)
        ready.set()
        finish.wait(20)


def _lease_race_worker(root, read_id, operation, start, results):
    reads = module("source_read")
    reads._now = (lambda: 99) if operation == "renew" else (lambda: 101)
    start.wait(10)
    try:
        result = (reads.renew(root, read_id) if operation == "renew" else reads.cleanup(root))
        results.put((operation, "ok", result))
    except reads.ContractError as error:
        results.put((operation, error.code, None))


@pytest.mark.parametrize("suffix", [".md", ".txt"])
def test_native_source_read_and_release_preserve_ingest_and_other_artifacts(tmp_path, suffix):
    root = tmp_path / "library"
    root.mkdir()
    for reference in (".build/materials/current.md", ".build/materials/parsed/image.png",
                      ".build/cards/candidate.md", "artifacts/query/report.json",
                      "artifacts/sources/history.pdf", "artifacts/benchmark/report.json",
                      "governance/sources.lock.yaml", "knowledge/formal.md"):
        path = root / reference
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("unrelated bytes: " + reference)
    before = snapshot(root)
    reads = module("source_read")
    result = create(root, suffix)
    assert len(result["read_id"]) == 32
    assert result["expires_at"] > reads._now()
    assert (root / result["original_ref"]).read_bytes().startswith(b"# Design")
    parsed = result["parsed"]
    assert "A documented requirement." in (root / parsed["text_ref"]).read_text()
    assert reads.release(root, result["read_id"])["released"] is True
    assert reads.release(root, result["read_id"])["released"] is False
    after = snapshot(root)
    assert all(after[reference] == digest for reference, digest in before.items())
    assert not (root / "artifacts/source-read" / result["read_id"]).exists()


@pytest.mark.parametrize("read_id", ["", "../outside", "A" * 32, "a" * 31,
                                    "/" + "a" * 32, "a" * 32 + "/child", "C:/outside", None])
def test_invalid_handles_are_rejected_without_any_file_changes(tmp_path, read_id):
    (tmp_path / "keep").write_text("keep")
    before = snapshot(tmp_path)
    reads = module("source_read")
    for action in (reads.release, reads.renew):
        with pytest.raises(reads.ContractError, match="INVALID_SOURCE_READ_ID"):
            action(tmp_path, read_id)
    assert snapshot(tmp_path) == before


def test_expiry_and_renewal_have_explicit_boundary_and_keep_other_readers(tmp_path, monkeypatch):
    reads = module("source_read")
    first, second = create(tmp_path), create(tmp_path)
    change_lease(tmp_path, first["read_id"], expires_at=100)
    monkeypatch.setattr(reads, "_now", lambda: 99)
    renewed = reads.renew(tmp_path, first["read_id"], ttl_seconds=10)
    assert renewed["expires_at"] == 109
    monkeypatch.setattr(reads, "_now", lambda: 109)
    with pytest.raises(reads.ContractError, match="SOURCE_READ_EXPIRED"):
        reads.renew(tmp_path, first["read_id"])
    assert reads.cleanup(tmp_path)["removed"] == [first["read_id"]]
    assert (tmp_path / second["original_ref"]).is_file()
    assert reads.release(tmp_path, second["read_id"])["released"]


def test_ready_gets_full_ttl_even_after_a_long_conversion(tmp_path, monkeypatch):
    reads = module("source_read")
    moments = iter([100, 9000])
    monkeypatch.setattr(reads, "_now", lambda: next(moments))
    result = create(tmp_path)
    assert result["expires_at"] == 10800
    assert json.loads(lease_path(tmp_path, result["read_id"]).read_text())["state"] == "ready"


def test_capacity_reclaims_only_expired_jobs(tmp_path, monkeypatch):
    reads = module("source_read")
    monkeypatch.setattr(reads, "MAX_JOBS", 2)
    first, second = create(tmp_path), create(tmp_path)
    with pytest.raises(reads.ContractError, match="SOURCE_READ_CAPACITY"):
        create(tmp_path)
    change_lease(tmp_path, first["read_id"], expires_at=0)
    third = create(tmp_path)
    assert not lease_path(tmp_path, first["read_id"]).exists()
    assert lease_path(tmp_path, second["read_id"]).exists()
    assert lease_path(tmp_path, third["read_id"]).exists()


def test_parse_failure_removes_only_its_own_partial_job(tmp_path):
    reads = module("source_read")
    good = create(tmp_path)
    before = snapshot(tmp_path / "artifacts/source-read" / good["read_id"])
    with pytest.raises((reads.ContractError, UnicodeError, ValueError)):
        reads.create(tmp_path, source(".txt"), b"\xff\x00")
    assert reads._ids(tmp_path) == [good["read_id"]]
    assert snapshot(tmp_path / "artifacts/source-read" / good["read_id"]) == before
    assert [path.stem for path in (tmp_path / "artifacts/source-read/.locks").glob("*.lock")] == [good["read_id"]]


def test_read_size_limits_are_checked_without_modifying_other_jobs(tmp_path, monkeypatch):
    reads = module("source_read")
    good = create(tmp_path)
    monkeypatch.setattr(reads, "MAX_SOURCE_BYTES", 3)
    with pytest.raises(reads.ContractError, match="SOURCE_READ_TOO_LARGE"):
        create(tmp_path)
    assert reads._ids(tmp_path) == [good["read_id"]]
    monkeypatch.setattr(reads, "MAX_SOURCE_BYTES", 1024)
    with pytest.raises(reads.ContractError):
        create(tmp_path, options={"max_output_bytes": 1})
    assert reads._ids(tmp_path) == [good["read_id"]]


@pytest.mark.parametrize("field", ["max_input_bytes", "max_output_bytes"])
def test_oversized_parser_limits_fail_before_reserving_a_read(tmp_path, field):
    reads = module("source_read")
    options = {field: 512 * 1024 * 1024}
    with pytest.raises(reads.ContractError, match="INVALID_PARSER_OPTIONS"):
        create(tmp_path, options=options)
    assert options == {field: 512 * 1024 * 1024}
    assert not (tmp_path / "artifacts/source-read").exists()


def test_legal_parser_options_keep_the_same_ingest_and_read_profile(tmp_path):
    parser = module("document_parser")
    options = {"max_input_bytes": 8 * 1024 * 1024, "max_output_bytes": 1024 * 1024}
    original_options = dict(options)
    data = b"# Design\n\nA documented requirement.\n"
    ingested = parser.parse(tmp_path, source(), data, ".build/materials/parsed", options=options)
    reading = module("source_read").create(tmp_path, source(), data, options=options)
    try:
        assert reading["parsed"]["profile_sha256"] == ingested["profile_sha256"]
        assert options == original_options
    finally:
        module("source_read").release(tmp_path, reading["read_id"])


def test_cleanup_preserves_unknown_directories_and_rejects_links(tmp_path):
    reads = module("source_read")
    good = create(tmp_path)
    unknown = tmp_path / "artifacts/source-read/unknown/keep.txt"
    unknown.parent.mkdir()
    unknown.write_text("keep")
    assert reads.cleanup(tmp_path)["removed"] == []
    assert unknown.read_text() == "keep"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_text("keep")
    linked = tmp_path / "artifacts/source-read" / ("a" * 32)
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("This host cannot create directory links")
    with pytest.raises(reads.ContractError):
        reads.release(tmp_path, linked.name)
    assert (outside / "keep").read_text() == "keep"
    assert lease_path(tmp_path, good["read_id"]).is_file()


def test_simultaneous_processes_create_isolated_jobs(tmp_path):
    context = multiprocessing.get_context("spawn")
    start, results = context.Event(), context.Queue()
    workers = [context.Process(target=_create_worker, args=(str(tmp_path), start, results)) for _ in range(2)]
    for process in workers:
        process.start()
    try:
        start.set()
        outcomes = [results.get(timeout=40) for _ in workers]
        assert all(status == "ready" for status, _ in outcomes), outcomes
        ids = {result["read_id"] for _, result in outcomes}
        assert len(ids) == 2
        for _, result in outcomes:
            assert (tmp_path / result["parsed"]["text_ref"]).is_file()
        removed = outcomes[0][1]["read_id"]
        module("source_read").release(tmp_path, removed)
        assert all(lease_path(tmp_path, read_id).exists() for read_id in ids - {removed})
    finally:
        for process in workers:
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)
        assert all(process.exitcode == 0 for process in workers)


def test_expired_conversion_is_skipped_while_busy_and_reclaimed_after_process_exit(tmp_path):
    reads = module("source_read")
    result = create(tmp_path)
    context = multiprocessing.get_context("spawn")
    ready, finish = context.Event(), context.Event()
    worker = context.Process(target=_hold_busy_worker, args=(str(tmp_path), result["read_id"], ready, finish))
    worker.start()
    try:
        assert ready.wait(10)
        assert reads.cleanup(tmp_path)["removed"] == []
        with pytest.raises(reads.ContractError, match="SOURCE_READ_BUSY"):
            reads.release(tmp_path, result["read_id"])
        assert (tmp_path / result["parsed"]["text_ref"]).is_file()
        worker.terminate()  # Emulate a converter crash; the OS drops its busy lock.
        worker.join(5)
        assert reads.cleanup(tmp_path)["removed"] == [result["read_id"]]
        assert not (tmp_path / "artifacts/source-read" / result["read_id"]).exists()
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(5)


def test_cleanup_and_renewal_are_atomic_between_processes(tmp_path):
    result = create(tmp_path)
    change_lease(tmp_path, result["read_id"], expires_at=100)
    context = multiprocessing.get_context("spawn")
    start, results = context.Event(), context.Queue()
    workers = [context.Process(target=_lease_race_worker,
                              args=(str(tmp_path), result["read_id"], operation, start, results))
               for operation in ("renew", "cleanup")]
    for worker in workers:
        worker.start()
    try:
        start.set()
        outcomes = {item[0]: item[1:] for item in [results.get(timeout=20), results.get(timeout=20)]}
        status, renewed = outcomes["renew"]
        if status == "ok":
            assert outcomes["cleanup"][1]["removed"] == []
            assert lease_path(tmp_path, result["read_id"]).is_file()
            assert renewed["expires_at"] == 1899
        else:
            assert status == "SOURCE_READ_NOT_FOUND"
            assert outcomes["cleanup"][1]["removed"] == [result["read_id"]]
            assert not lease_path(tmp_path, result["read_id"]).exists()
    finally:
        for worker in workers:
            worker.join(5)
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
        assert all(worker.exitcode == 0 for worker in workers)
