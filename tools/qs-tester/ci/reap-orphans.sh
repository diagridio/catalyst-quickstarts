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
# --yes confirmed via `diagrid project delete --help` (CLI 1.36.0 and 1.119.0).
#
# The stale names are collected into a variable rather than piped into the
# delete loop: a `while` at the end of a pipe runs in a subshell, so a failure
# counter set inside it would be lost and the script would exit 0 regardless.
if ! stale_names="$(printf '%s' "$project_json" \
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
' "$CUTOFF")"; then
  exit 1
fi

if [ -z "$stale_names" ]; then
  echo "No stale qs-ci-* projects."
  exit 0
fi

# Do not trust the exit code of `diagrid project delete`: CLI 1.67.0 and 1.119.0
# both print "Failed to delete project ...: forbidden request" and exit 0. This
# loop used to rely on it, so for weeks it "reaped" the same projects every
# night without deleting any. Check that each project is actually gone instead.
deleted=0
leaked=()
while read -r stale; do
  [ -n "$stale" ] || continue
  echo "Reaping stale project: $stale"
  out="$(diagrid project delete "$stale" --yes 2>&1)" || true
  printf '%s\n' "$out"
  gone=0
  # A reported failure is final; only a reported success is worth waiting on
  # (deletion can be asynchronous). Polling after a "forbidden" would cost two
  # minutes per project, and the backlog this reaps can be hundreds deep.
  tries=24
  case "$out" in *"Failed to delete"*) tries=1 ;; esac
  for _ in $(seq 1 "$tries"); do
    if ! diagrid project get "$stale" >/dev/null 2>&1; then
      gone=1
      break
    fi
    sleep 5
  done
  if [ "$gone" -eq 1 ]; then
    deleted=$((deleted + 1))
  else
    leaked+=("$stale")
  fi
done <<<"$stale_names"

echo "Deleted $deleted stale project(s)."
if [ "${#leaked[@]}" -gt 0 ]; then
  echo "::error::${#leaked[@]} stale project(s) still exist after delete:" \
    "${leaked[*]}. If the deletes said 'forbidden request', the DIAGRID_API_KEY" \
    "used by CI lacks permission to delete projects." >&2
  exit 1
fi
