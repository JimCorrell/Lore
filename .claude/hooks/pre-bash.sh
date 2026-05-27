#!/bin/bash
set -euo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c \
  "import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')" 2>/dev/null || echo "")
[[ -z "$COMMAND" ]] && exit 0
if echo "$COMMAND" | grep -qE "DROP (TABLE|DATABASE|SCHEMA)" 2>/dev/null; then
  if ! echo "$COMMAND" | grep -qiE "(dev|test|local)" 2>/dev/null; then
    echo "BLOCKED: Destructive DROP on what may be a non-dev database. Run manually if intentional."
    exit 2
  fi
fi
if echo "$COMMAND" | grep -qE "git push.*--force.*(main|master)" 2>/dev/null; then
  echo "BLOCKED: Force push to main/master. Run manually if intentional."
  exit 2
fi
exit 0
