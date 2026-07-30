#!/usr/bin/env bash
# Delete the ephemeral project. Runs under `if: always()`, so it must not fail
# the job when setup never got far enough to create anything.
set -uo pipefail

PROJECT="${1:-${PROJECT:-}}"

if [ -z "$PROJECT" ]; then
  echo "No project name given and PROJECT is unset; nothing to delete."
  exit 0
fi

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "DIAGRID_API_KEY is unset; cannot authenticate to delete $PROJECT." >&2
  exit 0
fi

diagrid login --api-key "$DIAGRID_API_KEY" || exit 0

echo "Deleting project $PROJECT"
# Deliberately not `set -e`: a delete failure should be visible but must not mask
# the real test failure that is already being reported.
# --yes confirmed via `diagrid project delete --help` (CLI 1.36.0): skips the
# interactive confirmation prompt. `--approve` is a documented synonym.
if diagrid project delete "$PROJECT" --yes; then
  echo "Deleted $PROJECT"
else
  echo "::warning::Failed to delete $PROJECT — reap-orphans.sh will collect it."
fi
