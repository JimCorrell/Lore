#!/bin/bash
set -euo pipefail
TODOS_FILE=".claude/memory/todos.md"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
mkdir -p ".claude/memory"
if [[ ! -f "$TODOS_FILE" ]]; then
  printf "# Todos Memory\nAuto-maintained by Claude Code. Do not edit manually.\nLast session will append entries below.\n\n" > "$TODOS_FILE"
fi
printf "\n---\n## Session ended: %s\n" "$TIMESTAMP" >> "$TODOS_FILE"
exit 0
