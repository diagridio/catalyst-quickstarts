#!/usr/bin/env bash
# Compute the ephemeral Catalyst project name for one leg. No CLI calls, so it
# cannot fail partway and leave the name unknown.
#
# Agent-family suites provision themselves from their README's documented
# commands, but the name still has to be known BEFORE the suite runs: teardown
# runs under `if: always()`, and a suite that dies inside its documented
# `project create` would otherwise leak a project until reap-orphans.sh.
#
# Reads:  $1 (leg id, e.g. agents-langgraph), GITHUB_RUN_ID (optional)
# Writes: PROJECT to $GITHUB_ENV under Actions; always echoes it.
set -euo pipefail

LEG="${1:-}"
if [ -z "$LEG" ]; then
  echo "::error::Usage: project-name.sh <leg-id>   (e.g. agents-langgraph)" >&2
  exit 1
fi

RUN_ID="${GITHUB_RUN_ID:-local$(date +%s)}"
# The qs-ci- prefix is load-bearing: reap-orphans.sh collects leaked projects by
# that pattern. A name without it leaks forever.
PROJECT="qs-ci-${LEG}-${RUN_ID}"

echo "PROJECT=$PROJECT"
if [ -n "${GITHUB_ENV:-}" ]; then
  echo "PROJECT=$PROJECT" >> "$GITHUB_ENV"
fi
