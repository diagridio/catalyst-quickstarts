#!/usr/bin/env bash
# Every check CI's lint job runs, in the same order, with no credentials.
# Run this until it is green before attempting a live run.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)/tools/qs-tester" || exit 1
failed=()

run() {
  local label="$1"
  echo "== $label"
  shift
  if ! "$@"; then failed+=("$label"); fi
}

run "manifest"  uv run python ci/list-suites.py --validate
echo "== dryrun"
# shellcheck disable=SC2046  # word splitting is the point: one path per suite
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths) || failed+=("dryrun")
run "doc-sync"  uv run python docsync/check_readme_sync.py --all
run "skill doc-sync"  uv run python docsync/check_skill_docs.py
run "unit tests" uv run pytest -q
echo "== keyword smoke tests"
# The whole directory, matching CI's "Test the harness keywords" step: naming
# files individually here means a new one (readiness.robot, teardown.robot)
# silently never runs locally while CI runs it.
uv run robot --outputdir results/smoke resources/tests || failed+=("smoke")

if [ ${#failed[@]} -gt 0 ]; then
  echo
  echo "static verification FAILED: ${failed[*]}"
  exit 1
fi
echo
echo "static verification passed"
