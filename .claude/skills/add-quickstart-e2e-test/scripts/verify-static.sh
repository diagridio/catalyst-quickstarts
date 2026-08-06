#!/usr/bin/env bash
# Every check CI's lint job runs, in the same order, with no credentials.
# Run this until it is green before attempting a live run.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)/tools/qs-tester" || exit 1
failed=()

run() {
  echo "== $1"
  shift
  if ! "$@"; then failed+=("$1"); fi
}

run "manifest"  uv run python ci/list-suites.py --validate
run "unit tests" uv run pytest -q
run "doc-sync"  uv run python docsync/check_readme_sync.py --all
echo "== dryrun"
# shellcheck disable=SC2046  # word splitting is the point: one path per suite
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths) || failed+=("dryrun")
echo "== keyword smoke tests"
uv run robot --outputdir results/smoke \
  resources/tests/smoke.robot resources/tests/keywords.robot || failed+=("smoke")

if [ ${#failed[@]} -gt 0 ]; then
  echo
  echo "static verification FAILED: ${failed[*]}"
  exit 1
fi
echo
echo "static verification passed"
