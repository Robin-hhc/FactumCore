"""Check or install pinned Python dependencies on the toolkit execution host."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

from deploy import install_dependencies


TOOL_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = TOOL_ROOT / "runtime/requirements.lock.txt"
INSTALL_TIMEOUT_SECONDS = 30 * 60


def report():
    if sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12)}:
        raise ValueError("Unsupported Python version")
    sys.path.insert(0, str(TOOL_ROOT))
    import knowledge

    manifest, verified = knowledge.verified_runtime(TOOL_ROOT)
    loader = knowledge._VerifiedRuntime(TOOL_ROOT, verified)
    sys.meta_path.insert(0, loader)
    try:
        from himate_knowledge.doctor import inspect_dependencies

        dependencies, gaps = inspect_dependencies(REQUIREMENTS)
    finally:
        sys.meta_path.remove(loader)
    return {"status": "needs_install" if gaps else "ready", "python": sys.executable,
            "python_version": platform.python_version(), "toolkit_version": manifest["version"],
            "tool_root": str(TOOL_ROOT), "dependencies": dependencies, "diagnostics": gaps}


def emit(**event):
    print(json.dumps(event), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install"))
    action = parser.parse_args(argv).action
    if action == "install":
        emit(phase="checking", message="正在检查工具包和 Python 依赖。")
    try:
        result = report()
    except (OSError, ValueError, ImportError):
        diagnostic = {"code": "DEPENDENCY_CHECK_FAILED", "message": "无法读取工具包的依赖清单，请检查工具包版本和 Python 路径。"}
        if action == "install":
            emit(phase="checking", **diagnostic)
        else:
            emit(status="unavailable", diagnostics=[diagnostic])
        return 1
    if action == "check":
        emit(**result)
        return 0
    if result["status"] == "needs_install":
        emit(phase="installing", message="正在为当前 Python 安装锁定依赖。")
        try:
            install_dependencies(sys.executable, REQUIREMENTS, cwd=TOOL_ROOT,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 timeout=INSTALL_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError):
            emit(phase="installing", code="DEPENDENCY_INSTALL_FAILED",
                 message="依赖安装失败，请检查 pip、软件源和当前 Python 的写入权限后重试。")
            return 1
    emit(phase="verifying", message="安装阶段已完成，等待复查 Python 依赖。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
