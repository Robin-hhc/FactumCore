"""Development compatibility import; no duplicate stage implementation."""
import secrets
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.pycache_prefix = str(Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16)))

from _runtime import expose  # noqa: E402

_actual = expose(__file__, globals(), 'source', 'entry')
