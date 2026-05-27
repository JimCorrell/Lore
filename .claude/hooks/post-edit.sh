#!/bin/bash
set -euo pipefail
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c \
  "import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')" 2>/dev/null || echo "")
[[ -z "$FILE" ]] && exit 0
[[ ! -f "$FILE" ]] && exit 0
if [[ "$FILE" == *.py ]]; then
  uv run ruff format "$FILE" --quiet 2>/dev/null || true
  uv run ruff check "$FILE" --fix --quiet 2>/dev/null || true
fi
exit 0
