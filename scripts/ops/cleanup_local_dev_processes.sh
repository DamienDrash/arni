#!/usr/bin/env bash
set -euo pipefail

MODE="dry"
if [[ "${1:-}" == "--apply" ]]; then
  MODE="apply"
fi

ROOT="/root/.openclaw/workspace/arni"
PATTERN='(pytest|next dev|npm run (dev|test|build)|tail -f|watch )'

printf "[%s] scanning stale dev processes in %s\n" "$MODE" "$ROOT"
mapfile -t lines < <(ps -eo pid,etimes,cmd --sort=-etimes | awk -v root="$ROOT" '$0 ~ root {print}' | grep -E "$PATTERN" || true)

if [[ ${#lines[@]} -eq 0 ]]; then
  echo "no matching local dev processes found"
  exit 0
fi

for line in "${lines[@]}"; do
  pid=$(awk '{print $1}' <<<"$line")
  etimes=$(awk '{print $2}' <<<"$line")
  cmd=$(cut -d' ' -f3- <<<"$line")
  if [[ "$pid" == "$$" ]]; then
    continue
  fi
  # Keep fresh processes (< 5 min) untouched.
  if [[ "$etimes" -lt 300 ]]; then
    printf "keep  pid=%s age=%ss cmd=%s\n" "$pid" "$etimes" "$cmd"
    continue
  fi
  if [[ "$MODE" == "apply" ]]; then
    kill "$pid" 2>/dev/null || true
    printf "killed pid=%s age=%ss cmd=%s\n" "$pid" "$etimes" "$cmd"
  else
    printf "would-kill pid=%s age=%ss cmd=%s\n" "$pid" "$etimes" "$cmd"
  fi
done
