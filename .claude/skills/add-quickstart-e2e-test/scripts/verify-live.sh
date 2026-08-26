#!/usr/bin/env bash
# Run one agent-family suite against a real Catalyst project, then prove one of
# its assertions is not vacuous, then tear down everything it created.
#
# Usage: verify-live.sh <suite-path> [mutation-assignment] [expected-keyword]
#   suite-path         repo-relative, e.g. agents/langgraph/tests/quickstart.robot
#   mutation           a Python assignment to override, as NAME=<literal>.
#                      Default: READY_MARKERS=("__mutation_check__",)
#   expected-keyword   the keyword the mutation must make FAIL.
#                      Default: Wait Until Ready Marker
#
# The leg is not a parameter here: it is read from `ci/list-suites.py --row`
# (which reads `suites.leg_id()`), the same field the nightly workflow's matrix
# now carries. A leg typed by hand as `agents-<name>` would silently ignore a
# row's explicit `leg` override -- the override exists precisely for suites
# whose `name` is over `suites.project_name_budget()` -- and this script would
# then build and try to provision a project name over Catalyst's 55-character
# ceiling.
#
# Agent-family suites only. Canonical suites need a different procedure and this
# script refuses them rather than running them wrong -- see the check below.
#
# The override is written to a generated variable file rather than passed with
# --variable, because --variable can only set scalars and the assertions worth
# breaking (READY_MARKERS, REQUESTS) are tuples. A CLI --variablefile outranks the
# suite's own `Variables` import, so this reaches any module-level name and needs
# no type guessing here.
set -uo pipefail

SUITE="${1:?usage: verify-live.sh <suite-path> [NAME=<python-literal>] [expected-keyword]}"
MUTATION="${2:-READY_MARKERS=(\"__mutation_check__\",)}"
EXPECT_KEYWORD="${3:-Wait Until Ready Marker}"

# The mutated run must fail for the mutated reason. A sentinel inside the
# override gives the checker a second, independent handle on that: the failure
# message of the keyword above has to name it. Custom mutations that keep the
# sentinel get the stronger check; ones that do not are checked on the keyword
# name alone.
NEEDLE=""
case "$MUTATION" in
  *__mutation_check__*) NEEDLE="__mutation_check__" ;;
esac

ROOT="$(git rev-parse --show-toplevel)"
HARNESS="$ROOT/tools/qs-tester"

# --- Refuse what this script cannot do correctly -----------------------------
# A canonical suite is provisioned OUTSIDE the suite by ci/setup-project.sh
# (which this script does not run), and all four of its language tests share
# appIDs and ports 5001/5002, so they cannot run together in one project: they
# need `--include <language>`, one language per project. Running one here would
# fail against a project that does not exist, which proves nothing about the
# suite. The default mutation would not apply either -- canonical data lives in
# quickstarts.py, which has no READY_MARKERS.
ROW="$(cd "$HARNESS" && uv run python ci/list-suites.py --row "$SUITE")" || exit 1
FAMILY="$(printf '%s\n' "$ROW" | grep '^FAMILY=' | cut -d= -f2-)"
if [ "$FAMILY" != "agent" ]; then
  LANGUAGES="$(printf '%s\n' "$ROW" | grep '^LANGUAGES=' | cut -d= -f2-)"
  FIRST_LANG="$(printf '%s\n' "$LANGUAGES" | cut -d' ' -f1)"
  echo "::error::$SUITE is a '$FAMILY' suite; verify-live.sh handles agent-family suites only."
  echo
  echo "A canonical suite needs an externally provisioned project and one language"
  echo "at a time (all four share appIDs and ports 5001/5002). Run it by hand, once"
  echo "per language in [$LANGUAGES]:"
  echo
  echo "  export DIAGRID_API_KEY=... LANG_ID=$FIRST_LANG"
  echo "  eval \"\$(bash tools/qs-tester/ci/setup-project.sh | grep '^PROJECT=')\""
  echo "  cd tools/qs-tester"
  echo "  uv run robot --include $FIRST_LANG --variable PROJECT:\$PROJECT \\"
  echo "    --outputdir results/$FIRST_LANG ../../$SUITE"
  echo "  bash ci/teardown-project.sh \"\$PROJECT\""
  echo
  echo "Then the mutation check, against a SECOND project created the same way,"
  echo "mutating a value that suite reads from its Variables import (for example"
  echo "STATE_STORE_BODY for state/tests/quickstart.robot), and confirm the right"
  echo "keyword failed:"
  echo
  echo "  uv run python ci/check_mutation.py results/<leg>-mutated/output.xml 'POST And Expect'"
  echo
  echo "See tools/qs-tester/README.md, 'Create a project and run a suite'."
  exit 2
fi

# The leg used for the ephemeral project name, read from the manifest via the
# same `suites.leg_id()` the lint rule and the nightly matrix use -- not
# reconstructed from `$SUITE` here, so an explicit `leg` override on the row
# is honored rather than silently ignored.
LEG_FRAGMENT="$(printf '%s\n' "$ROW" | grep '^LEG=' | cut -d= -f2-)"
LEG="agents-$LEG_FRAGMENT"

# --- Names first, teardown second, work last ---------------------------------
# Two projects, because the mutated run cannot reuse the first one: an
# agent-family suite provisions itself in SETUP from its README's documented
# `project create` and `agent create`, and `Run Documented Commands` stops at the
# first non-zero exit. Against an existing project that `project create` fails,
# the suite dies in SETUP, and the mutated assertion is never reached -- a
# non-zero exit that proves nothing. The cost is one extra provisioning; the
# mutated run stops at the readiness gate, so it spends no model tokens.
PROJECT="$(bash "$HARNESS/ci/project-name.sh" "$LEG" | grep '^PROJECT=' | cut -d= -f2-)"
PROJECT_MUTATED="$(bash "$HARNESS/ci/project-name.sh" "$LEG-mut" | grep '^PROJECT=' | cut -d= -f2-)"
if [ -z "$PROJECT" ] || [ -z "$PROJECT_MUTATED" ]; then
  echo "::error::could not compute the ephemeral project names."
  exit 1
fi
export PROJECT

# Tear both down on every exit path, including an early failure and a mid-run
# interrupt. A leaked project with agent infrastructure costs money until
# reap-orphans.sh collects it. teardown-project.sh is safe on a project that was
# never created: it checks first and exits 0. INT/TERM just exit, so the EXIT
# trap does the deleting exactly once.
cleanup() {
  bash "$HARNESS/ci/teardown-project.sh" "$PROJECT"
  bash "$HARNESS/ci/teardown-project.sh" "$PROJECT_MUTATED"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

bash "$HARNESS/ci/login.sh" || exit 1
cd "$HARNESS" || exit 1

# Clear any results left by a previous iteration before each run, not just
# before the mutation check. A run that dies before robot writes a fresh
# output.xml (a uv sync failure, an interrupted process) must leave nothing
# for a human to misread from log.html/report.html, and must not let a later
# `if ! uv run robot ...` success accidentally reuse a directory that still
# has other stale artifacts sitting next to the new output.xml.
rm -rf "results/$LEG"

echo "== live run: $SUITE (project $PROJECT)"
if ! uv run robot --variable "PROJECT:$PROJECT" --outputdir "results/$LEG" "../../$SUITE"; then
  echo "::error::live run FAILED. Read results/$LEG/log.html and the captured dev-run log."
  exit 1
fi

echo "== mutation check: overriding $MUTATION, expecting $EXPECT_KEYWORD to FAIL"
echo "   (fresh project $PROJECT_MUTATED, because the suite provisions its own)"
# Same clearing here, and it matters more: unlike the live leg above, this
# leg's verdict comes from ci/check_mutation.py reading results/$LEG-mutated/
# output.xml, not from robot's own exit code. If the mutated run below dies
# before writing a new output.xml (a bad --variablefile, a fatal data error,
# an interrupted run) and a previous accepted run's output.xml were still
# sitting here, the checker would read THAT stale file and could certify
# VERIFIED on evidence from a run that did not just happen. Removing the
# directory first means the checker can only ever see output from this run,
# or (correctly) none at all.
rm -rf "results/$LEG-mutated"
mkdir -p "results/$LEG-mutated"
printf '%s\n' "$MUTATION" > "results/$LEG-mutated/mutate.py"
# The short timeouts keep a run we expect to fail from waiting out the full
# readiness window. They do not shorten SETUP: Run Documented Commands has its
# own 600s timeout, which `project create --wait` needs.
if uv run robot --variable "PROJECT:$PROJECT_MUTATED" \
     --variablefile "results/$LEG-mutated/mutate.py" \
     --variable READINESS_TIMEOUT:20s --variable MARKER_TIMEOUT:20s \
     --outputdir "results/$LEG-mutated" "../../$SUITE"; then
  echo "::error::The suite PASSED with $MUTATION applied, so that assertion is vacuous:"
  echo "  it cannot fail, which means a broken quickstart would ship green."
  echo "  Check first that Robot actually loaded the variable file (it errors loudly"
  echo "  if the path is wrong), then that the suite reads the name from its"
  echo "  Variables import rather than from get_quickstart()."
  echo "  Fix the assertion; do not report this suite as verified."
  exit 1
fi

# A non-zero exit is NOT the proof. The mutated run has to fail on the mutated
# assertion; anything else (a failed project create, a build error, a missing
# key) is a failure that would have happened with or without the mutation and
# says nothing about whether the assertion can fail.
if ! uv run python ci/check_mutation.py \
     "results/$LEG-mutated/output.xml" "$EXPECT_KEYWORD" "$NEEDLE"; then
  echo "::error::The mutated run failed, but not on $EXPECT_KEYWORD."
  echo "  That is a failure the mutation did not cause, so it proves nothing about"
  echo "  the assertion. Read results/$LEG-mutated/log.html for the real cause, fix"
  echo "  it, and re-run. Do not report this suite as verified."
  exit 1
fi

echo
echo "VERIFIED: $SUITE passed against $PROJECT, and failed on $EXPECT_KEYWORD"
echo "          against $PROJECT_MUTATED with $MUTATION applied."
