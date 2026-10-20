# ruff: noqa: E402 - isolate bytecode lookup before private package imports.
import pathlib
import sys
import secrets
import tempfile

sys.dont_write_bytecode = True
sys.pycache_prefix = str(
    pathlib.Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16))
)

from recover import recover
from support import run_cli


if __name__ == "__main__":
    sys.exit(run_cli(recover, pathlib.Path(__file__).resolve().parents[1]))
