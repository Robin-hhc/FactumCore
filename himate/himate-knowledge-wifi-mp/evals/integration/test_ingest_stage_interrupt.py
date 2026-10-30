"""An actual stopped public P2 process cannot mark uncommitted sources handled."""

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time


SPEC = importlib.util.spec_from_file_location("interrupt_pipeline", Path(__file__).parents[1] / "support/pipeline.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def formal(root):
    return {path.relative_to(root).as_posix(): FIXTURE.sha(path.read_bytes())
            for path in root.rglob("*") if path.is_file()
            and path.relative_to(root).parts[0] != ".build"}


def test_stopped_public_prepare_leaves_formal_state_and_fresh_scan_unaffected(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    targets = []
    for number in range(80):
        source = "docs-raw/specs/interrupt/part-" + str(number) + ".md"
        p.write(source, ("# Source " + str(number) + "\nCaptured but never published.\n").encode())
        targets.append({"source_path": source})
    before = formal(p.root)
    incoming, outgoing = p.base / "interrupted-input.json", p.base / "interrupted-output.json"
    incoming.write_text(json.dumps({"operation_id": "stopped", "targets": targets}), encoding="utf-8")
    command = [*p.command("knowledge-source"),
               "--action", "prepare", "--knowledge-root", str(p.root),
               "--input", str(incoming), "--output", str(outgoing)]
    with (p.base / "interrupted-stdout.txt").open("wb") as stdout, (p.base / "interrupted-stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=os.name != "nt")
        try:
            deadline = time.monotonic() + 30
            staged = False
            while process.poll() is None and time.monotonic() < deadline:
                if any((p.root / ".build/operations/stopped/sources").glob("*/staged/original/*")):
                    staged = True
                    break
                time.sleep(0.01)
            assert staged and process.poll() is None, "The public process must really reach in-flight staging"
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=True)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=15)
    assert process.returncode != 0
    assert formal(p.root) == before
    response = p.call("knowledge-source", {"operation_id": "fresh-after-stop"}, "scan")
    scan = p.record(response["data"]["scan_ref"])
    assert len(scan["units"]) == len(targets)
    assert {row["change"] for row in scan["units"]} == {"new"}
    assert not (p.root / "logs/ingest").exists()
