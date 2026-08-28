#!/usr/bin/env bash
# Authenticate the diagrid CLI with an API key.
#
# This is one of the two sanctioned deviations from running documented commands
# verbatim: every quickstart README documents a bare `diagrid login`, which
# blocks on an interactive browser prompt and would hang CI forever. The CLI
# does not read DIAGRID_API_KEY on its own, so --api-key is mandatory.
set -euo pipefail

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "::error::DIAGRID_API_KEY is not set; the login would block on an" >&2
  echo "interactive browser prompt and the job would hang." >&2
  exit 1
fi

diagrid login --api-key "$DIAGRID_API_KEY"
