#!/bin/sh
# Explicit interpreter supplied by the caller; never install or guess a runtime.
set -eu
if [ -z "${FACTUM_PYTHON:-}" ]; then
    echo 'FACTUM_PYTHON must name the explicitly selected Python interpreter' >&2
    exit 3
fi
case "$FACTUM_PYTHON" in
    /*|[A-Za-z]:[\\/]*) ;;
    *) echo 'FACTUM_PYTHON must be absolute' >&2; exit 3 ;;
esac
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$FACTUM_PYTHON" "$script_dir/check.py" "$@"
