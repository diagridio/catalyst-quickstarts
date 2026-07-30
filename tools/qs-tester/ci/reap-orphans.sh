#!/usr/bin/env bash
# Delete qs-ci-* projects older than 6 hours. Cancelled jobs never run their
# teardown, so without this they accumulate and eventually block new runs
# against the two-concurrent-project limit.
set -uo pipefail

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "::error::DIAGRID_API_KEY is not set" >&2
  exit 1
fi

if ! diagrid login --api-key "$DIAGRID_API_KEY"; then
  echo "::error::diagrid login failed — cannot reap orphaned projects" >&2
  exit 1
fi

CUTOFF=$(( $(date +%s) - 6 * 3600 ))

# `diagrid project list -o json` gives name and creation timestamp per project.
# The list itself is captured first (rather than piped straight into python3)
# so a failure here is loud too: without `set -e`, a failed list call would
# otherwise feed empty/error output into json.load, which raises, exits
# non-zero, but feeds nothing into the `while read` loop below — so the
# script would still exit 0. Same silent-failure shape as the login call.
if ! project_json="$(diagrid project list -o json)"; then
  echo "::error::diagrid project list failed — cannot reap orphaned projects" >&2
  exit 1
fi
# JSON shape verified against `diagrid project list -o json` (CLI 1.36.0): a
# top-level object with `items`, each entry carrying `metadata.name` and
# `metadata.createdAt`. createdAt is formatted "2026-07-23 15:58:49" — a space
# separator and NO timezone suffix, so fromisoformat returns a naive datetime
# and .timestamp() would read it as local time. The API reports UTC, so stamp
# it as UTC explicitly; without that the cutoff is off by the runner's offset
# (harmless on UTC CI runners, wrong when a human runs this locally).
# --yes confirmed via `diagrid project delete --help` (CLI 1.36.0).
printf '%s' "$project_json" \
  | python3 -c '
import json, sys, datetime
cutoff = int(sys.argv[1])
# Do NOT assume stdin starts with the JSON document. `diagrid project list` reads
# DIAGRID_API_KEY from the environment (verified: a bogus value fails with
# "Invalid apikey"), and when it authenticates that way it prints
# "Successfully authenticated using the provided API Key" on *stdout*, ahead of
# the JSON. The command still exits 0, so the `if !` guard above cannot catch it
# and json.load(sys.stdin) dies with "Expecting value: line 1 column 1".
# Slice from the first brace instead, and fail loudly with the actual output
# rather than a traceback if there is no JSON at all — a list call that returns
# nothing must not be mistaken for "no orphans to reap".
raw = sys.stdin.read()
start = raw.find("{")
if start == -1:
    sys.stderr.write(
        "::error::diagrid project list returned no JSON; not reaping anything. "
        "Raw output was:\n" + raw[:500] + "\n"
    )
    sys.exit(1)
data = json.loads(raw[start:])
for p in data.get("items", []):
    meta = p.get("metadata", {})
    name = meta.get("name", "")
    if not name.startswith("qs-ci-"):
        continue
    try:
        created = datetime.datetime.fromisoformat(meta.get("createdAt", ""))
    except ValueError:
        continue
    if created.tzinfo is None:
        created = created.replace(tzinfo=datetime.timezone.utc)
    if created.timestamp() < cutoff:
        print(name)
' "$CUTOFF" \
  | while read -r stale; do
      echo "Reaping stale project: $stale"
      diagrid project delete "$stale" --yes || \
        echo "::warning::Could not delete $stale"
    done
