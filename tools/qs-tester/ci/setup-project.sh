#!/usr/bin/env bash
# Create the ephemeral Catalyst project for one matrix leg.
#
# Reads:  DIAGRID_API_KEY (required), LANG_ID (required), GITHUB_RUN_ID (optional)
# Writes: PROJECT to $GITHUB_ENV when running under Actions; always echoes it.
set -euo pipefail

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "::error::DIAGRID_API_KEY is not set. The diagrid CLI has no environment" >&2
  echo "fallback for it, so without this variable the login would block on an" >&2
  echo "interactive browser prompt and the job would hang." >&2
  exit 1
fi

if [ -z "${LANG_ID:-}" ]; then
  echo "::error::LANG_ID is not set (expected one of csharp java javascript python)" >&2
  exit 1
fi

RUN_ID="${GITHUB_RUN_ID:-local$(date +%s)}"
PROJECT="qs-ci-${LANG_ID}-${RUN_ID}"

# Write PROJECT to $GITHUB_ENV as soon as the name is known, before any command
# that can fail. Under `set -euo pipefail`, a failure partway through project
# creation (e.g. `project create` succeeds but `kv create` fails) would abort
# the script before a trailing write ever ran, leaving PROJECT unset for
# teardown-project.sh -- which would then find nothing to delete and exit 0,
# orphaning the project until the nightly reap-orphans.sh run.
echo "PROJECT=$PROJECT"
if [ -n "${GITHUB_ENV:-}" ]; then
  echo "PROJECT=$PROJECT" >> "$GITHUB_ENV"
fi

# --api-key is mandatory: `diagrid login` does not read DIAGRID_API_KEY itself.
diagrid login --api-key "$DIAGRID_API_KEY"

# --wait blocks until the managed services are ready; --use makes it the default
# project so ad-hoc CLI calls in later steps do not need --project.
diagrid project create "$PROJECT" \
  --deploy-managed-kv \
  --deploy-managed-pubsub \
  --enable-managed-workflow \
  --wait --use

# --deploy-managed-kv provisions a store named `kvstore`, which state/java expects.
# The other three state quickstarts default to `statestore`, so provision that too.
# Both are real stores, so no STATESTORE_NAME override is needed anywhere and each
# language exercises its own published default.
diagrid kv create statestore --project "$PROJECT" --wait
