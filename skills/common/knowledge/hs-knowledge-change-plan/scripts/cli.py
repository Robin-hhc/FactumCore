"""Development compatibility CLI; execution lives in the knowledge repository."""
import secrets
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.pycache_prefix = str(Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16)))

from _runtime import run_legacy  # noqa: E402

if __name__ == "__main__":
    run_legacy(__file__, 'change-plan')
