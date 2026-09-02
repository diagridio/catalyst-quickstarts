"""Data for the agents/spring-ai/event-planner end-to-end suite.

Every command is transcribed verbatim from
agents/spring-ai/event-planner/README.md, with the documented project name
replaced by `{project}`. Change the README, change this file, and
`docsync/check_readme_sync.py --all` will say so if you change only one.
"""

from pathlib import Path

# This module lives flat in variables/, same as every other data module, so
# this stays parents[3] regardless of the quickstart's own three-level depth
# below.
REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "spring-ai-event-planner"
LANGUAGE = "java"

DOCUMENTED_PROJECT = "spring-ai-quickstart"
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "spring-ai" / "event-planner")

# README "### 1. Deploy and Run" documents login, create, agent create and dev run
# in ONE fenced block. Note the reduced flag set: no --deploy-managed-pubsub,
# unlike every other agent quickstart. The flags are per-quickstart data, not a
# constant.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --wait --use",
    "diagrid agent create spring-ai-event-planner --wait",
)

# README "## Setup". The documented `cd event-planner` is expressed as the working
# directory; the `#` comment line above it is not a command.
INSTALL = "mvn package -DskipTests"

RUN = "diagrid dev run -f dev-spring-ai-event-planner.yaml --approve"

TEARDOWN = ("diagrid project delete {project}",)

# EMPTY ON PURPOSE, and this is the interesting one: this README documents no
# readiness wording at all. There is no "wait until" line to transcribe, so
# inventing one would be inventing an assertion. Readiness rests entirely on the
# connection gate below.
READY_MARKERS = ()

# EMPTY ON PURPOSE. EventPlannerController exposes only @PostMapping("/run"), and
# spring-boot-starter-actuator is not on the classpath, so there is no GET path to
# probe.
HEALTH_PROBES = ()

# appID and appPort from dev-spring-ai-event-planner.yaml.
CONNECTED_APPS = (("spring-ai-event-planner", 8080),)

# EMPTY, NOT VERIFIED. `Wait Until Catalyst Attached` waits for the first inbound
# request Catalyst makes back through the dev tunnel, which is the point at which
# workflow calls stop hanging. Measured on agents/langgraph 2026-08-27: a call
# made before that hangs forever and twelve retries over 181s never recovered it,
# while the same call gated on the marker answered in ~1s three runs running.
# Nothing about that race is Python-specific, so this suite is very likely exposed
# to it too.
#
# It is empty rather than guessed because the marker is whatever THIS app's
# logging makes visible for an inbound request, and this Spring Boot app's request logging has not been
# checked. A marker that never appears makes the gate time out (loud, and the
# suite fails); a marker matched from the wrong line would let the suite through
# early (silent, and the run hangs). Fill this in by running the quickstart once
# and reading what the app logs when Catalyst probes it.
CATALYST_PROBE_MARKERS = ()

# Empty: the quickstart ships a canned offline model (CannedChatModel.java) and
# reaches a real provider only when DIAGRID_QUICKSTART_MODEL=openai, which this
# suite does not set. Keep in step with the `secrets` entry in suites.py — one
# without the other is a declaration that lies.
SECRETS = ()

# README "### 2. Trigger the Agent".
#
# `field` is None because the README documents no response body: tool 2
# deliberately crashes the process mid-request, so the curl call never returns a
# result.
#
# `status` is NOT a transcription, and it is now known to be UNREACHABLE. This
# README documents no status code, and `EventPlannerTools.stepTwoCompare` calls
# `Runtime.getRuntime().halt(1)` unconditionally before the controller returns.
# Measured 2026-09-02, running offline against the canned model: TOOL 1 and TOOL
# 2 both fire and the JVM then dies mid-request, so curl exits 000 with the port
# closed and there is no status code to record.
#
# The 200 is left standing on purpose rather than replaced with a passing
# assertion. There is no response to transcribe, and encoding "the connection
# dies" here would assert the crash as the quickstart's documented outcome when
# the README's outcome is the RECOVERY — reached only by commenting the halt out,
# a source edit no suite should make. So this suite stays red and `nightly:
# False` in suites.py, and the crash coverage lives in the crash-recovery
# sibling, whose `kill_after_seconds` makes the same crash a runtime request.
# Recorded in the harness README's Limitations.
REQUESTS = (
    {
        "method": "POST",
        "port": 8080,
        "path": "/run",
        "payload": {"prompt": "Find a venue in Austin for a company gala"},
        "status": 200,
        "field": None,
    },
)

# Documented commands this suite deliberately does not run, each with its reason.
#
# Empty here, and that is not an oversight. The one documented step this suite
# skips is the '## Crash Recovery' resume (README:115), which needs the crash
# line in EventPlannerTools.java commented out first — a source edit that is out
# of scope. But the command that step documents is byte-identical to the one at
# README:59, which is RUN. doc-sync excuses a documented line if it is in the
# harness commands *or* in UNCOVERED, and RUN already matches this string, so an
# entry here would be inert data claiming the suite does not run a command it in
# fact runs. Contrast agents_microsoft_dotnet.py, whose UNCOVERED entry is a
# genuinely distinct string and is load-bearing.
UNCOVERED = ()


def get_quickstart():
    """Everything the suite needs, in one flat dict."""
    return {
        "family": FAMILY,
        "name": NAME,
        "language": LANGUAGE,
        "dir": QUICKSTART_DIR,
        "setup": list(SETUP),
        "install": INSTALL,
        "run": RUN,
        "teardown": list(TEARDOWN),
        "health_probes": [list(probe) for probe in HEALTH_PROBES],
        "catalyst_probe_markers": list(CATALYST_PROBE_MARKERS),
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
        "secrets": list(SECRETS),
    }
