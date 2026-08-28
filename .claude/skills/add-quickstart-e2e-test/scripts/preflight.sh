#!/usr/bin/env bash
# Check everything needed to finish a run, before any files are written.
#
# Usage: preflight.sh [family]     family: canonical | agent
#
# Exits non-zero listing what is missing. Finding a missing key now costs
# seconds; finding it after four files are written costs the whole run.
set -uo pipefail

FAMILY="${1:-agent}"
HARNESS="$(git rev-parse --show-toplevel)/tools/qs-tester"
problems=()

[ -d "$HARNESS" ] || problems+=("tools/qs-tester not found; run from inside the repository")

if ! command -v uv >/dev/null 2>&1; then
  problems+=("uv is not installed: https://docs.astral.sh/uv/")
fi

if ! command -v diagrid >/dev/null 2>&1; then
  problems+=("diagrid CLI is not on PATH; install the pinned version (see below)")
else
  pinned="$(grep -o "DIAGRID_CLI_VERSION: 'v[0-9.]*'" \
    "$(git rev-parse --show-toplevel)/.github/workflows/e2e-quickstarts.yml" \
    | grep -o 'v[0-9.]*')"
  actual="v$(diagrid version 2>/dev/null | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)"
  if [ -n "$pinned" ] && [ "$pinned" != "$actual" ]; then
    echo "note: local diagrid $actual, CI pins $pinned. Usually fine; if the CLI"
    echo "      surface changed, reproduce CI with:"
    echo "      curl -sL https://downloads.diagrid.io/cli/install.sh | RELEASE_VERSION=\"$pinned\" bash"
  fi
fi

[ -n "${DIAGRID_API_KEY:-}" ] || problems+=("DIAGRID_API_KEY is not set; the live run cannot happen without it")

if [ "$FAMILY" = "agent" ]; then
  # Any one provider key is enough to start; the suite's own Require Env Var
  # names the specific one it needs.
  if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${GEMINI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    problems+=("no model provider key set (OPENAI_API_KEY, GEMINI_API_KEY or ANTHROPIC_API_KEY); agent quickstarts call a real model")
  fi
fi

(cd "$HARNESS" && uv sync -q) || problems+=("uv sync failed in tools/qs-tester")

if [ ${#problems[@]} -gt 0 ]; then
  echo "preflight failed:"
  for p in "${problems[@]}"; do echo "  - $p"; done
  exit 1
fi

echo "preflight ok (family: $FAMILY)"
