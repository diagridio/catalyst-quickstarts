#!/usr/bin/env bash
# Run one suite against a real Catalyst project, then prove one of its
# assertions is not vacuous, then tear down whatever happened.
#
# Usage: verify-live.sh <suite-path> <leg-id> [mutation-assignment]
#   suite-path          repo-relative, e.g. agents/langgraph/tests/quickstart.robot
#   leg-id              name fragment, e.g. agents-langgraph
#   mutation-assignment a Python assignment to override, as NAME=<literal>.
#                       Default: READY_MARKERS=("__mutation_check__",)
#
# The override is written to a generated variable file rather than passed with
# --variable, because --variable can only set scalars and the assertions worth
# breaking (READY_MARKERS, REQUESTS) are tuples. A CLI --variablefile outranks the
# suite's own `Variables` import, so this reaches any module-level name and needs
# no type guessing here.
set -uo pipefail

SUITE="${1:?usage: verify-live.sh <suite-path> <leg-id> [NAME=<python-literal>]}"
LEG="${2:?usage: verify-live.sh <suite-path> <leg-id> [NAME=<python-literal>]}"
MUTATION="${3:-READY_MARKERS=(\"__mutation_check__\",)}"

ROOT="$(git rev-parse --show-toplevel)"
eval "$(bash "$ROOT/tools/qs-tester/ci/project-name.sh" "$LEG" | grep '^PROJECT=')"
export PROJECT

# Tear down on every exit path, including a mid-run interrupt. A leaked project
# with agent infrastructure costs money until reap-orphans.sh collects it.
cleanup() { bash "$ROOT/tools/qs-tester/ci/teardown-project.sh" "$PROJECT"; }
trap cleanup EXIT INT TERM

bash "$ROOT/tools/qs-tester/ci/login.sh" || exit 1
cd "$ROOT/tools/qs-tester" || exit 1

echo "== live run: $SUITE (project $PROJECT)"
if ! uv run robot --variable "PROJECT:$PROJECT" --outputdir "results/$LEG" "../../$SUITE"; then
  echo "::error::live run FAILED. Read results/$LEG/log.html and the captured dev-run log."
  exit 1
fi

echo "== mutation check: overriding $MUTATION, expecting a FAILURE"
# Reuses the same project, so the marginal cost is one app restart rather than a
# second provisioning. The short timeouts keep a run we expect to fail from
# waiting out the full readiness window.
mkdir -p "results/$LEG-mutated"
printf '%s\n' "$MUTATION" > "results/$LEG-mutated/mutate.py"
if uv run robot --variable "PROJECT:$PROJECT" \
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

echo
echo "VERIFIED: $SUITE passed, and failed as expected with $MUTATION applied."
