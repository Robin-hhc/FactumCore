#!/bin/sh
# Prefer the managed virtual environment, matching bin/knowledge.js.
root=$(dirname -- "$0")
managed="$root/.venv/bin/python"

if [ -n "$HIMATE_KNOWLEDGE_PYTHON" ] && "$HIMATE_KNOWLEDGE_PYTHON" -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)' >/dev/null 2>&1; then
  exec "$HIMATE_KNOWLEDGE_PYTHON" -B "$root/knowledge.py" "$@"
fi
if [ -x "$managed" ] && "$managed" -c 'import sys' >/dev/null 2>&1; then
  exec "$managed" -B "$root/knowledge.py" "$@"
fi
exec "${HIMATE_KNOWLEDGE_PYTHON:-python3}" -B "$root/knowledge.py" "$@"
