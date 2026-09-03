"""Suite data for the Spring AI crash-recovery quickstart.

Mirrors agents/spring-ai/crash-recovery/README.md. Every value below is either
transcribed from that README or read out of the quickstart's own source, with a
comment naming which.

This is the third of the guided activation flow's three agent cells to get a
suite. It is the one whose crash flow is fully coverable: the README documents
`kill_after_seconds`, so the app halts itself at a known point inside the
booking window and the test never has to aim a kill at a moving target.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "spring-ai-crash-recovery"
LANGUAGE = "java"

# README "### 1. Deploy and Run".
DOCUMENTED_PROJECT = "spring-ai-crash-recovery"
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "spring-ai" / "crash-recovery")

# README "### 1. Deploy and Run" documents login, create, agent create and dev
# run in ONE fenced block. Same reduced flag set as the event-planner sibling:
# no --deploy-managed-pubsub. The flags are per-quickstart data, not a constant.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --wait --use",
    "diagrid agent create spring-ai-crash-recovery --wait",
)

# README "## Setup". The `#` comment line above it is not a command.
INSTALL = "mvn package -DskipTests"

RUN = "diagrid dev run -f dev-spring-ai-crash-recovery.yaml --approve"

TEARDOWN = ("diagrid project delete {project}",)

# EMPTY ON PURPOSE, for the same reason as the event-planner sibling: this README
# documents no readiness wording. Readiness rests on the connection gate below.
#
# Note the README's own warning that the recovered run "is usually scrolling
# before Spring Boot has finished starting Tomcat". That is why a Tomcat marker
# is not a readiness assertion for the RECOVERY phase — there it lands after the
# work it would be gating. It is still the right gate for the FIRST request,
# which is what SERVING_MARKER below is for; the two are different phases, not a
# contradiction.
READY_MARKERS = ()

# EMPTY ON PURPOSE. CrashRecoveryController exposes only POST mappings
# (/crash/run, /crash/kill) and actuator is not on the classpath, so there is no
# GET path to probe.
HEALTH_PROBES = ()

# From dev-spring-ai-crash-recovery.yaml's appPort, which also matches the
# README's documented curl targets. Single-sourced because it appears in four
# places (the connection gate, the request, the port-closed check and the
# serving marker) and a run against a port one of them disagreed about fails in
# a way that looks like a broken quickstart.
APP_PORT = 8080

CONNECTED_APPS = (("spring-ai-crash-recovery", APP_PORT),)

CATALYST_PROBE_MARKERS = ()

# Empty: the quickstart ships a canned offline model (CannedChatModel.java) and
# reaches a real provider only when DIAGRID_QUICKSTART_MODEL=openai, which this
# suite does not set. Keep in step with the `secrets` entry in suites.py — one
# without the other is a declaration that lies.
SECRETS = ()

# The documented calls, in documented order. README "### 2. Book under an id you
# own" and "## Collect the answer".
#
# `field` is "result" for both: unlike the event-planner sibling, this README
# documents the response shape explicitly — `{"id", "result", "message"}` — and
# states that with the offline model `result` is exactly the tool's own line. So
# the expected value is transcribed, not guessed.
CRASH_ID = "trip-42"
CRASH_REFERENCE = "ABC123"

# README "## Collect the answer" prints this body verbatim, noting the code after
# BK- is derived from the reference. Asserted as a prefix for that reason: the
# README documents the derivation but not the derived value, and reading the
# algorithm out of the source to predict it would be inventing an expectation.
CRASH_RESULT_PREFIX = f"Booking {CRASH_REFERENCE} confirmed. Confirmation code: BK-"

REQUESTS = (
    {
        "method": "POST",
        "port": APP_PORT,
        "path": "/crash/run",
        "payload": {"id": CRASH_ID, "reference": CRASH_REFERENCE},
        "status": 200,
        "field": "result",
    },
)

# Log markers, transcribed from the quickstart's own source because the README
# quotes them only partially. SlowBookingTools.java and CrashRecoveryController
# emit these; the `{}` placeholders are Spring's, so each entry below is the
# fixed prefix up to the first substitution.
#
# COMMITTING_SELF_KILL is the self-crash variant, which is the path this suite
# takes. COMMITTING_MANUAL is the two-terminal variant the suite does not use;
# it is recorded so a failure that lands on the wrong branch is legible.
COMMITTING_SELF_KILL = ">>> commitReservation("
SELF_KILL_MARKER = ">>> crash: halting the JVM"
COMMITTED_MARKER = "): committed. Confirmation code: "
OFFLINE_MODEL_MARKER = ">>> Using the canned offline model"

# Read from the app's own startup output, not the README, which documents no
# readiness wording. Load-bearing because of the ORDER Spring Boot logs in:
#
#   Tomcat initialized with port 8080
#   >>> Using the canned offline model          <- fires here
#   Tomcat started on port 8080 (http)          <- only now is the port serving
#
# Gating the first POST on the model marker alone raced the listener and failed
# intermittently: the request arrived before Tomcat accepted connections, the
# booking never started, and the run died on the committing marker three minutes
# later with no sign of why.
SERVING_MARKER = f"Tomcat started on port {APP_PORT}"

# How many seconds into the booking the app halts itself. README "### 2." says to
# keep this below `crash-recovery.delay-seconds` (30 by default) so the crash
# lands inside the booking rather than after it finished.
KILL_AFTER_SECONDS = 8

# Documented commands this suite deliberately does not run, each with its reason.
UNCOVERED = (
    (
        'curl -X POST "http://localhost:8080/crash/kill"',
        "README '### 3. Crash the app mid-call' is the two-terminal variant, and "
        "the README itself says to skip it when kill_after_seconds is sent. This "
        "suite sends it, so the self-crash path is what runs. Covering both would "
        "mean racing a kill against a live window for no extra assertion.",
    ),
)


def get_quickstart():
    """Everything the suite needs, in one flat dict.

    Robot calls this as a keyword: `${qs}=  Get Quickstart`.
    """
    return {
        "family": FAMILY,
        "name": NAME,
        "language": LANGUAGE,
        "dir": QUICKSTART_DIR,
        "setup": SETUP,
        "install": INSTALL,
        "run": RUN,
        "teardown": TEARDOWN,
        "health_probes": HEALTH_PROBES,
        "catalyst_probe_markers": CATALYST_PROBE_MARKERS,
        "connected_apps": CONNECTED_APPS,
        "secrets": SECRETS,
    }
