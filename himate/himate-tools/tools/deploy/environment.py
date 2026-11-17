"""Compatibility entrypoint for the execution-host environment commands."""

import argparse
import json
from pathlib import Path
import sys


TOOL_ROOT = Path(__file__).resolve().parents[2]


def load_runtime():
    if sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12)}:
        raise ValueError("Unsupported Python version")
    sys.path.insert(0, str(TOOL_ROOT))
    import knowledge

    manifest, verified = knowledge.verified_runtime(TOOL_ROOT)
    loader = knowledge._VerifiedRuntime(TOOL_ROOT, verified)
    sys.meta_path.insert(0, loader)
    try:
        from himate_knowledge.environment import run_environment
    finally:
        sys.meta_path.remove(loader)
    return manifest, run_environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install"))
    parser.add_argument("--bin-dir", type=Path, help="Select a command directory and manage PATH separately")
    options = parser.parse_args(argv)
    installing = options.action == "install"
    try:
        manifest, run = load_runtime()
    except (OSError, ValueError, ImportError):
        diagnostic = {"code": "DEPENDENCY_CHECK_FAILED",
                      "message": "无法读取工具包的依赖清单，请检查工具包版本和 Python 路径。"}
        if installing:
            print(json.dumps({"phase": "checking", "message": "正在检查工具包和 Python 依赖。"}), flush=True)
            print(json.dumps({"phase": "checking", "diagnostics": [diagnostic], **diagnostic}), flush=True)
        else:
            print(json.dumps({"status": "unavailable", "diagnostics": [diagnostic]}), flush=True)
        return 1
    return run(TOOL_ROOT, manifest, options.action, bin_dir=options.bin_dir,
               output="jsonl" if installing else "json", legacy=True)


if __name__ == "__main__":
    raise SystemExit(main())
