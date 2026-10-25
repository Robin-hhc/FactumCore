from pathlib import Path
import sys
import tempfile
import secrets

sys.dont_write_bytecode = True
sys.pycache_prefix = str(
    Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16))
)
from support import run  # noqa: E402 - reject cached bytecode before imports
from node import execute  # noqa: E402 - reject cached bytecode before imports

if __name__ == "__main__":
    sys.exit(run(execute, Path(__file__).resolve().parents[1]))
