#!/usr/bin/env bash
# Delete qs-ci-* projects older than 6 hours. Cancelled jobs never run their
# teardown, so without this they accumulate and eventually block new runs
# against the two-concurrent-project limit.
set -uo pipefail

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "::error::DIAGRID_API_KEY is not set" >&2
  exit 1
fi

diagrid login --api-key "$DIAGRID_API_KEY"

CUTOFF=$(( $(date +%s) - 6 * 3600 ))

# `diagrid project list -o json` gives name and creation timestamp per project.
# NOTE: the exact JSON shape below is UNVERIFIED — this task's environment has
# no DIAGRID_API_KEY and must not make authenticated API calls, so the shape
# guesses (bare list vs. `items` vs. `projects`, and `createdAt` at the top
# level vs. under `metadata`) have not been checked against real output. A
# human with API access must run `diagrid project list -o json | head -40`,
# confirm which branch actually applies, and delete the fallbacks that don't.
# --yes confirmed via `diagrid project delete --help` (CLI 1.36.0).
diagrid project list -o json \
  | python3 -c '
import json, sys, datetime
cutoff = int(sys.argv[1])
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get("items", data.get("projects", []))
for p in items:
    name = p.get("name") or p.get("metadata", {}).get("name", "")
    if not name.startswith("qs-ci-"):
        continue
    created = p.get("createdAt") or p.get("metadata", {}).get("createdAt", "")
    try:
        ts = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
    except ValueError:
        continue
    if ts < cutoff:
        print(name)
' "$CUTOFF" \
  | while read -r stale; do
      echo "Reaping stale project: $stale"
      diagrid project delete "$stale" --yes || \
        echo "::warning::Could not delete $stale"
    done
