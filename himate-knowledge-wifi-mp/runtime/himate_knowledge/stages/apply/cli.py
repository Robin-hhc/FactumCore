# ruff: noqa: E402 - isolate bytecode lookup before private package imports.
import pathlib
import sys
import secrets
import tempfile

sys.dont_write_bytecode = True
sys.pycache_prefix = str(pathlib.Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16)))

from .support import run_cli
from .entry import execute


def main():
    return run_cli(execute, pathlib.Path(__file__).resolve().parent)


if __name__ == "__main__":
    sys.exit(main())
