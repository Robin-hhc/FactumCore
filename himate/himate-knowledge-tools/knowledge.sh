#!/bin/sh
# Set HIMATE_KNOWLEDGE_PYTHON once when python3 is not the prepared interpreter.
exec "${HIMATE_KNOWLEDGE_PYTHON:-python3}" -B "$(dirname -- "$0")/knowledge.py" "$@"
