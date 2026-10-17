#!/usr/bin/env bash
# Mutation check for the crash-recovery suites: prove the "step 1 is NOT re-run after the
# restart" assertion can fail.
#
# Usage: verify-replay-mutation.sh [--dry-run] <name>...
#   name   an agent suite under agents/ that runs the crash demo and calls a real model:
#          crewai adk openai-agents pydantic-ai strands deepagents mastra
#   --dry-run  print what would run for each name and check the premises, without
#              touching Catalyst. Needs no keys. Run this first.
#
# What it proves. Each crash suite ends with `Log Should Not Contain ${log_again}
# ${STEP1_MARKER}`: the restarted app's log must not contain step 1's completion line,
# because Catalyst replays step 1 from workflow history instead of running it again. That is
# the claim the whole demo makes, and an assertion that is never seen failing is worth
# nothing. So this re-runs the suite with STEP1_MARKER replaced by a string that DOES appear
# in the recovery log, and requires `Log Should Not Contain` to FAIL, naming that string.
#
# The replacement is a prefix of step 2's start line, which both the crash log and the
# recovery log contain (the armed and the un-armed variant share it). It has to be in the
# crash log too: the suite also waits for STEP1_MARKER there, before the crash, and a string
# absent from that log would fail that earlier wait instead and prove nothing about the
# assertion under test.
#
# The work is delegated to .claude/skills/add-quickstart-e2e-test/scripts/verify-live.sh,
# which does the green live run, the mutated run against a SECOND project, the verdict from
# ci/check_mutation.py, and the teardown of both projects on every exit path. That is two
# full runs per suite (about 5 minutes) and real model tokens for both.
#
# Needs DIAGRID_API_KEY and OPENAI_API_KEY (claude-agents, which needs ANTHROPIC_API_KEY,
# and the canned-model suites langgraph and microsoft-dotnet are not covered here).
set -uo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
  shift
fi
if [ "$#" -lt 1 ]; then
  sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
HARNESS="$ROOT/tools/qs-tester"
VERIFY="$ROOT/.claude/skills/add-quickstart-e2e-test/scripts/verify-live.sh"

if [ "$DRY_RUN" -eq 0 ]; then
  for var in DIAGRID_API_KEY OPENAI_API_KEY; do
    if [ -z "${!var:-}" ]; then
      echo "::error::$var is not set. Export it first, or use --dry-run to check the premises without it."
      exit 1
    fi
  done
fi

# Prints "<crash source file>|<marker>" for one suite, or fails. The marker is a string
# present in BOTH the crash log and the recovery log.
probe_for() {
  local name="$1" module src marker
  case "$name" in
    crewai|adk|openai-agents|pydantic-ai|strands|deepagents)
      module="agents_${name//-/_}"
      src="$ROOT/agents/$name/crash_test.py"
      # STEP2_ARMED_MARKER is the shared prefix of step 2's armed and un-armed lines.
      marker="$(cd "$HARNESS/variables" && uv run python -c \
        "import $module as m; print(m.STEP2_ARMED_MARKER, end='')")" || return 1
      ;;
    mastra)
      # mastra's STEP2_ARMED_MARKER is a fragment of the ARMED line only (it must not be
      # satisfiable by the un-armed one), so it is absent from the recovery log. Use the
      # shared start of both lines instead, copied from agents/mastra/crash_test.ts.
      src="$ROOT/agents/mastra/crash_test.ts"
      marker='>>> STEP 2 checkIncidentStatus: Checking '
      ;;
    *)
      echo "::error::'$name' is not a crash suite this script covers (crewai adk openai-agents pydantic-ai strands deepagents mastra)." >&2
      return 1
      ;;
  esac
  if [ -z "$marker" ]; then
    echo "::error::$name: could not read the replacement marker." >&2
    return 1
  fi
  # The marker must be printed by BOTH step 2 variants, so at least two lines of the
  # quickstart's own source carry it. One would mean it only exists in one of the logs.
  local hits
  hits="$(grep -F -c -- "$marker" "$src" || true)"
  if [ "${hits:-0}" -lt 2 ]; then
    echo "::error::$name: the marker '$marker' appears on $hits line(s) of $src; it must be on at least 2 (the armed and the un-armed step 2 lines), or it is not in both logs." >&2
    return 1
  fi
  printf '%s|%s' "$src" "$marker"
}

RESULTS=()
FAILED=0
for name in "$@"; do
  suite="agents/$name/tests/quickstart.robot"
  if [ ! -f "$ROOT/$suite" ]; then
    echo "::error::$suite does not exist."
    RESULTS+=("$name: NO SUITE")
    FAILED=1
    continue
  fi
  if ! probe="$(probe_for "$name")"; then
    RESULTS+=("$name: PREMISE FAILED")
    FAILED=1
    continue
  fi
  marker="${probe#*|}"
  # repr() so a marker with quotes, $ or backslashes lands in mutate.py as a valid literal.
  mutation="$(python3 -c 'import sys; print("STEP1_MARKER=" + repr(sys.argv[1]))' "$marker")"
  # The generated file has to be valid Python, or robot fails to start and proves nothing.
  if ! python3 -c 'import ast, sys; ast.parse(sys.argv[1])' "$mutation"; then
    echo "::error::$name: generated mutation is not valid Python: $mutation"
    RESULTS+=("$name: BAD MUTATION")
    FAILED=1
    continue
  fi

  echo "== $name"
  echo "   suite:     $suite"
  echo "   mutation:  $mutation"
  echo "   expecting: 'Log Should Not Contain' to FAIL, naming: $marker"
  if [ "$DRY_RUN" -eq 1 ]; then
    RESULTS+=("$name: ok (dry run)")
    continue
  fi

  if MUTATION_NEEDLE="$marker" MUTATED_RUN_ARGS="" \
     bash "$VERIFY" "$suite" "$mutation" "Log Should Not Contain"; then
    RESULTS+=("$name: VERIFIED")
  else
    RESULTS+=("$name: NOT VERIFIED")
    FAILED=1
  fi
done

echo
echo "== summary"
printf '   %s\n' "${RESULTS[@]}"
exit "$FAILED"
