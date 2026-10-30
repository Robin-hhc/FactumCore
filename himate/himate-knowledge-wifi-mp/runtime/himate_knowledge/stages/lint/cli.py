"""Public, read-only lint. This CLI uses the independent 0/1/2 report protocol."""
import sys
sys.dont_write_bytecode = True
from .lint import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
