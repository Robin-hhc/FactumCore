"""Public entry: cached package bytecode is outside the trust boundary."""

import sys
from pathlib import Path
import tempfile
import secrets

sys.dont_write_bytecode = True
sys.pycache_prefix = str(
    Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16))
)


def main():
    from maintain import execute
    from support import run

    return run(execute, Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    raise SystemExit(main())
