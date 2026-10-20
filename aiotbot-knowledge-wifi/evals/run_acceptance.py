"""Run isolated package/process mechanism checks; never reads restricted gold.

Use a new explicit --output-dir for every run. Reports do not close T211.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]


def run_group(item, output, environment):
    number, label, path = item
    xml = output / f"{number:02d}.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--import-mode=importlib",
        str(path),
        "-q",
        "--basetemp",
        str(output / "tmp" / f"group-{number:02d}"),
        "--junitxml",
        str(xml),
    ]
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=900)
    (output / f"{number:02d}.stdout.txt").write_bytes(result.stdout)
    (output / f"{number:02d}.stderr.txt").write_bytes(result.stderr)
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if xml.exists():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
    return {"group": label, "exit_code": result.returncode, "seconds": round(time.monotonic() - started, 3), **counts}


def main():
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--jobs", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    output = Path(args.output_dir).absolute()
    if output.exists():
        parser.error("Use a new output directory; previous evidence is never removed")
    for path in (output, *output.parents):
        if path.is_symlink():
            parser.error("Linked output paths are not accepted")
    output.mkdir(parents=True)
    (output / "tmp").mkdir()
    packages = sorted((ROOT / "skills/common/knowledge").glob("hs-*/tests"))
    groups = [(i, path.parent.name, path) for i, path in enumerate(packages)]
    groups.append((len(groups), "domain-and-integration", ROOT / "aiotbot-knowledge-wifi/evals/tests"))
    env = dict(os.environ, AIOTBOT_TEST_TMP=str(output / "unittest-tmp"))
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_group, item, output, env) for item in groups]
        results = [future.result() for future in futures]
    report = {
        "schema_version": "2.0",
        "verification_tier": "isolated_synthetic_mechanisms",
        "groups": results,
        "passed": all(row["exit_code"] == 0 for row in results),
        "totals": {key: sum(row[key] for row in results) for key in ("tests", "failures", "errors", "skipped")},
        "limitations": [
            "No real human or implicit host acceptance",
            "No real six Target or CI/publication/ACL acceptance",
            "No restricted gold accessed",
        ],
    }
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
