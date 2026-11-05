#!/usr/bin/env bash
# Delete the ephemeral project. Runs under `if: always()`, so it must not fail
# the job when setup never got far enough to create anything. It DOES fail when
# a project exists and could not be deleted: that is a leak, not a test result.
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

# Agent-family suites run their README's documented `diagrid project delete` as
# part of the test, so by the time this runs the project is usually already gone.
# Check first, so a green run does not end with a misleading warning. This script
# still matters: it is the safety net for a suite that died before its teardown.
if ! diagrid project get "$PROJECT" >/dev/null 2>&1; then
  echo "Project $PROJECT no longer exists; nothing to delete."
  exit 0
fi

echo "Deleting project $PROJECT"
# --yes confirmed via `diagrid project delete --help` (CLI 1.36.0 and 1.119.0):
# skips the interactive confirmation prompt. `--approve` is a documented synonym.
#
# The exit code of `diagrid project delete` proves nothing: CLI 1.67.0 and
# 1.119.0 both print "Failed to delete project ...: forbidden request" and still
# exit 0. Trusting it is how every nightly project leaked while this script
# printed "Deleted". So the only evidence of a delete is the project being gone.
out="$(diagrid project delete "$PROJECT" --yes 2>&1)" || true
printf '%s\n' "$out"

# Deletion can be asynchronous, so give it a couple of minutes to disappear. A
# reported failure is final, so it gets one check instead of the full wait.
tries=24
case "$out" in *"Failed to delete"*) tries=1 ;; esac
for _ in $(seq 1 "$tries"); do
  if ! diagrid project get "$PROJECT" >/dev/null 2>&1; then
    echo "Deleted $PROJECT"
    exit 0
  fi
  sleep 5
done

# Fail the step on purpose. A leaked project costs money and counts against the
# org's project limit, and a warning on a green job is never read. A red step
# also makes the `report` job open its issue.
echo "::error::Project $PROJECT still exists after delete. If the delete said" \
  "'forbidden request', the DIAGRID_API_KEY used by CI lacks permission to" \
  "delete projects. reap-orphans.sh will retry, but only with a key that can." >&2
exit 1
