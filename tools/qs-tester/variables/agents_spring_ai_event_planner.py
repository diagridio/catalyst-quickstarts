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

SECRETS = ("OPENAI_API_KEY",)

# README "### 2. Trigger the Agent".
#
# `field` is None because the README documents no response body: tool 2
# deliberately crashes the process mid-request, so the curl call never returns a
# result.
#
# `status` is NOT a transcription. This README documents no status code at all,
# and `EventPlannerTools.stepTwoCompare` calls `Runtime.getRuntime().halt(1)`
# before the controller returns, so a live run is more likely to see a connection
# error than any status code. The 200 below is therefore an assumption that is
# expected to fail on the first credentialed run, and it is left standing on
# purpose: the value that replaces it has to come from an observed response.
# Substituting a plausible-looking one is the guessing `field = None` in
# agents_langgraph.py exists to refuse. Recorded in the harness README's
# Limitations so that failure lands on a documented line.
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
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
        "secrets": list(SECRETS),
    }
