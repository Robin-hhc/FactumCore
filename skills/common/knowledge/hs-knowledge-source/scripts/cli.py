"""Public source entry; never load unpinned cached bytecode."""

import secrets
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.pycache_prefix = str(Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16)))


def main():
    from entry import execute
    from support import run

    return run(execute, Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    raise SystemExit(main())
