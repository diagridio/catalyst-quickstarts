"""Tests for the inbound-identity behaviour this quickstart demonstrates.

Run from this directory with:

    uv run --with pytest pytest test_identity.py

pytest is an ephemeral dependency on purpose. It is not in pyproject.toml and
not in uv.lock, so nothing here forces a lock regeneration -- a stale lock would
fail `uv sync --frozen` in the Dockerfile.

No Catalyst, no Dapr, no network and no API key. `build_local_issuer` from
local_identity.py stands in for the Catalyst identity plane: it signs with a
throwaway key it generates in-process and serves the public half as JWKS on a
loopback port, so a credential that genuinely verifies is available offline.
That is what makes the 200 and the 403 assertable here at all -- the Robot suite
next door can present no credential and therefore asserts only the two 401s.

WHAT IS DELIBERATELY NOT TESTED: the outbound leg. This quickstart covers
inbound identity only, and nothing here may grow an assertion implying an
agent's on-behalf-of token reaches a downstream MCP tool.

Why the app is re-assembled instead of imported: main.py installs its middleware
at module level, which is the two-line shape the README teaches, so by the time
`import main` returns its config is already fixed and cannot be pointed at this
test's issuer. The two ASGI lines are therefore rebuilt here -- but the handlers,
the compiled graph, the required scopes and the response shape are all main.py's
own objects, so drift in any of them fails these tests rather than sliding past.
"""

import json

import pytest
from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from starlette.testclient import TestClient

import main
from diagrid.identity.asgi import OAuthMiddleware
from local_identity import build_local_issuer, _b64u

# main.py's own value, not a copy. A change to the app's required scope shows up
# here as the 200 and 403 cases swapping over, which is the intended failure.
REQUIRED_SCOPES = main.REQUIRED_SCOPES

# The subject fake_model.py's canned first turn asks the tool for. It is nobody,
# and the whole point of the `tools` node is that it never reaches the tool.
MODEL_GUESS = "someone@example.com"

TASK = {"task": "What bookings do I have?"}


@pytest.fixture(scope="module")
def issuer():
    """One throwaway issuer for the module: generating an RSA key is not free."""
    return build_local_issuer(REQUIRED_SCOPES)


@pytest.fixture(scope="module")
def client(issuer):
    """The app under test: main.py's handlers behind main.py's middleware.

    `raise_server_exceptions=False` so an unhandled handler exception arrives as
    a 500 response rather than propagating into the test. Without it a test
    asserting a status code could not tell "the app answered 500" from "the test
    itself blew up", which the 400-on-bad-payload cases below depend on.
    """
    app = FastAPI()
    app.get("/whoami")(main.whoami)
    app.post("/agent/run")(main.agent_run)
    app.add_middleware(OAuthMiddleware, config=issuer.config)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def auth(token: str) -> dict:
    """The header Catalyst sets on an inbound request, as the middleware reads it."""
    return {"X-Diagrid-User-Token": f"Bearer {token}"}


# --- Fail closed, before any application code runs -------------------------


@pytest.mark.parametrize(
    "method,path,payload",
    [("GET", "/whoami", None), ("POST", "/agent/run", TASK)],
)
def test_no_credential_is_refused_on_every_route(client, method, path, payload):
    # `require_auth` defaults to True and OAuthMiddleware wraps every route, so
    # this is the app-wide rule the README claims, checked on both documented
    # routes rather than on one and assumed for the other. The exact body is the
    # one the Robot suite asserts against a live Catalyst project.
    response = client.request(method, path, json=payload)

    assert response.status_code == 401
    assert response.json() == {"error": "oauth.missing_token"}
    # An authorization verdict is not a cacheable response. This header is the
    # middleware's, not FastAPI's, and the README documents it.
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_header_is_treated_as_no_credential(client, value):
    # The README claims "no header, or an empty one" is 401, so both halves are
    # checked. `_trim_bearer` strips whitespace, so a blank value leaves an
    # empty token and takes the same branch as an absent header.
    response = client.get("/whoami", headers={"X-Diagrid-User-Token": value})

    assert response.status_code == 401
    assert response.json() == {"error": "oauth.missing_token"}


def test_a_credential_without_the_required_scope_is_403(client, issuer):
    # 403, not 401, and the distinction is the point: authentication succeeded
    # and authorization failed. The credential is signed by the same issuer and
    # has not expired -- it simply carries `reports.read`.
    response = client.get("/whoami", headers=auth(issuer.wrong_scope))

    assert response.status_code == 403
    assert response.json() == {"error": "oauth.missing_scope"}


def test_an_expired_credential_is_401(client, issuer):
    # Five minutes stale, because the verifier allows 120s of clock skew. If
    # local_identity's _EXPIRED_LIFETIME_SECONDS ever creeps inside that window
    # this returns 200 and fails here rather than in a reader's terminal.
    response = client.get("/whoami", headers=auth(issuer.expired))

    assert response.status_code == 401
    assert response.json() == {"error": "oauth.expired"}


@pytest.mark.parametrize(
    "header",
    [
        {"X-Diagrid-User-Token": "Bearer not-a-jwt"},
        # A bare "Bearer" with nothing after it, which looks like an empty
        # credential but is not one. BEARER_PREFIX is "Bearer " -- the trailing
        # space is part of it -- and HTTP strips trailing header whitespace, so
        # the prefix never matches and the literal string "Bearer" is taken as
        # the token. It therefore lands here, among the malformed tokens, rather
        # than on the oauth.missing_token path an empty header gets. Same status
        # either way now, but a different code, and that is worth pinning.
        {"X-Diagrid-User-Token": "Bearer"},
    ],
)
def test_a_malformed_token_is_a_401(client, header):
    # A token that is not a well-formed JWT makes PyJWKClient raise
    # jwt.DecodeError. diagrid 0.4.4 let that escape as a 500; 0.4.5 converts it
    # to oauth.decode_error, so the path now fails closed with the rest of the
    # oauth.* family and the README is free to claim it.
    #
    # Asserting the code and not just the status: 401 alone would still pass if
    # a future version routed this through missing_token or invalid_signature,
    # and those mean different things to a reader debugging a real credential.
    response = client.get("/whoami", headers=header)

    assert response.status_code == 401
    assert response.json() == {"error": "oauth.decode_error"}


# --- The verified caller reaches the app ------------------------------------


def test_a_verified_caller_gets_the_documented_identity(client, issuer):
    response = client.get("/whoami", headers=auth(issuer.verified))

    assert response.status_code == 200
    # The exact object the README's offline section prints. Claim NAMES only:
    # `user.claims` is a real person's decoded credential in a deployment, and
    # `_identity` must not start echoing it back.
    assert response.json() == {
        "subject": "alice@example.com",
        "tenant": "local-tenant",
        "issuer_id": "https://local-identity.invalid",
        "scopes": sorted(REQUIRED_SCOPES),
    }
    assert "claims" not in response.json()


def test_the_tool_answers_for_the_verified_caller_not_the_model_guess(client, issuer):
    """The thesis of the whole quickstart, asserted end to end.

    The canned model asks `my_bookings` for someone@example.com. `call_tools`
    substitutes the subject the middleware verified, so the answer names
    alice@example.com and the model's guess appears nowhere in the response.
    """
    response = client.post("/agent/run", json=TASK, headers=auth(issuer.verified))

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["subject"] == "alice@example.com"

    tool_answer = body["messages"][1]
    assert "alice@example.com" in tool_answer
    assert MODEL_GUESS not in json.dumps(body), (
        "the model's guessed subject reached the response, so the tools node "
        "stopped substituting the verified subject"
    )
    # The exact three messages the README's offline section prints: the task,
    # the tool's answer, and the model's summary of it.
    assert body["messages"] == [
        TASK["task"],
        "Bookings for alice@example.com: Grand Ballroom on March 15th, 9AM-1PM; "
        "Rooftop Terrace on March 22nd, 6PM-11PM.",
        "You have two bookings: the Grand Ballroom on March 15th (9AM-1PM) and "
        "the Rooftop Terrace on March 22nd (6PM-11PM).",
    ]


def test_substitution_happens_in_the_graph_not_in_the_handler(client, issuer):
    """Invoke the real compiled graph directly, with no HTTP and no middleware.

    Proves the substitution lives in the `tools` node rather than in the route
    handler: the subject travels as graph config, which is exactly why a message
    the model could rewrite is not involved.
    """
    result = main.compiled.invoke(
        {"messages": [HumanMessage(content=TASK["task"])]},
        config={"configurable": {"user_subject": "dave@example.com"}},
    )

    tool_answers = [m.content for m in result["messages"] if "Bookings for" in str(m.content)]
    assert tool_answers, "the graph did not reach the tool"
    assert "dave@example.com" in tool_answers[0]
    assert MODEL_GUESS not in tool_answers[0]


def test_an_unconfigured_subject_does_not_silently_become_the_model_guess():
    """A missing config key must not fall back to the model's argument.

    `call_tools` reads `user_subject` with a default of "", so a graph invoked
    without it answers for nobody. That is the safe direction; falling through
    to the model's `someone@example.com` would be the unsafe one.
    """
    result = main.compiled.invoke(
        {"messages": [HumanMessage(content=TASK["task"])]},
        config={"configurable": {}},
    )

    joined = " ".join(str(m.content) for m in result["messages"])
    assert MODEL_GUESS not in joined


# --- Request validation -----------------------------------------------------


@pytest.mark.parametrize("payload", [{}, {"task": ""}, {"task": "   "}, {"task": 7}, []])
def test_a_task_that_is_not_a_non_empty_string_is_400(client, issuer, payload):
    # Validated after authentication, so a bad body from a verified caller is a
    # 400 while the same body from an anonymous one is still a 401.
    response = client.post("/agent/run", json=payload, headers=auth(issuer.verified))

    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_a_body_that_is_not_json_is_400(client, issuer):
    response = client.post(
        "/agent/run",
        content=b"not json",
        headers={**auth(issuer.verified), "Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "body must be JSON"


# --- The offline issuer itself ----------------------------------------------


def test_jwks_numbers_are_base64url_without_padding():
    # JWKS requires unpadded base64url. A stdlib b64encode would emit "+" and
    # "/" and pad with "=", and PyJWKClient would reject the key -- which would
    # surface as an opaque 503 rather than as a wrong-encoding error.
    encoded = _b64u(65537)

    assert encoded == "AQAB", "the standard RSA exponent must encode as AQAB"
    assert "=" not in encoded
    assert "+" not in encoded and "/" not in encoded


def test_the_issuer_serves_a_jwks_the_verifier_can_read(issuer):
    # The middleware fetches this document over the loopback port the OS picked.
    # If it were malformed every credential-bearing test above would fail as a
    # 503, so this makes the cause legible.
    import urllib.request

    with urllib.request.urlopen(issuer.config.jwks_uri, timeout=5) as response:
        document = json.load(response)

    assert [key["kid"] for key in document["keys"]] == ["local-quickstart-key"]
    assert document["keys"][0]["alg"] == "RS256"
