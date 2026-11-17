#!/bin/sh
case $0 in
  */*) root=${0%/*} ;;
  *) root=. ;;
esac

supported() {
  "$1" -I -S -B -c 'import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] <= (3, 12)))' >/dev/null 2>&1
}

if [ -n "${HIMATE_KNOWLEDGE_PYTHON:-}" ] && supported "$HIMATE_KNOWLEDGE_PYTHON"; then
  exec "$HIMATE_KNOWLEDGE_PYTHON" -I -B "$root/knowledge.py" "$@"
fi

for python in python3 python python3.11 python3.12 python3.10; do
  if supported "$python"; then
    exec "$python" -I -S -B "$root/knowledge.py" --_bootstrap-python "$@"
  fi
done

# Keep working without system Python on PATH. Do not execute a linked managed root.
managed="${HOME:-}/.himate/knowledge/.venv"
if [ -n "${HOME:-}" ] && [ ! -L "$managed" ] && [ -f "$managed/pyvenv.cfg" ] && supported "$managed/bin/python"; then
  exec "$managed/bin/python" -I -S -B "$root/knowledge.py" --_bootstrap-python "$@"
fi

printf '%s\n' 'Knowledge requires Python 3.10, 3.11 or 3.12 on this execution host.' >&2
exit 3
