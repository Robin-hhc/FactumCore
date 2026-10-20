"""Public process entry point."""

from pathlib import Path

from handoff import execute
from support import run

if __name__ == "__main__":
    raise SystemExit(run(execute, Path(__file__).resolve().parents[1]))
