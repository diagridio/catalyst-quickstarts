"""Tests for the inbound-identity behaviour this quickstart demonstrates.

Run from this directory with:

    uv run --with pytest pytest test_identity.py

No Catalyst, no Dapr, no network and no API key: `build_local_issuer` stands in
for the Catalyst identity plane, signing with a throwaway in-process key and
serving the public half as JWKS on a loopback port.

The outbound leg is not tested here -- carrying the caller onward to an MCP tool
needs a Catalyst project, so the README walkthrough covers it.
"""

import asyncio
import json
import os

# Must precede the `main` import: the mode decides which tool the graph gets.
os.environ["DIAGRID_QUICKSTART_IDENTITY"] = "local"

import pytest
from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from starlette.testclient import TestClient

import main
from diagrid.identity.asgi import OAuthMiddleware
from local_identity import build_local_issuer, _b64u

REQUIRED_SCOPES = main.LOCAL_REQUIRED_SCOPES

# The subject fake_model.py's canned first turn asks the tool for.
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
    a 500 response rather than propagating into the test.
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
    response = client.request(method, path, json=payload)

    assert response.status_code == 401
    assert response.json() == {"error": "oauth.missing_token"}
    # An authorization verdict is not cacheable.
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_header_is_treated_as_no_credential(client, value):
    response = client.get("/whoami", headers={"X-Diagrid-User-Token": value})

    assert response.status_code == 401
    assert response.json() == {"error": "oauth.missing_token"}


def test_a_credential_without_the_required_scope_is_403(client, issuer):
    # 403, not 401: authentication succeeded and authorization failed.
    response = client.get("/whoami", headers=auth(issuer.wrong_scope))

    assert response.status_code == 403
    assert response.json() == {"error": "oauth.missing_scope"}


def test_an_expired_credential_is_401(client, issuer):
    # Five minutes stale, because the verifier allows 120s of clock skew.
    response = client.get("/whoami", headers=auth(issuer.expired))

    assert response.status_code == 401
    assert response.json() == {"error": "oauth.expired"}


@pytest.mark.parametrize(
    "header",
    [
        {"X-Diagrid-User-Token": "Bearer not-a-jwt"},
        # A bare "Bearer": the prefix is "Bearer " with the trailing space, so
        # the literal string is taken as the token and lands among the malformed
        # ones rather than on the oauth.missing_token path.
        {"X-Diagrid-User-Token": "Bearer"},
    ],
)
def test_a_malformed_token_is_a_401(client, header):
    response = client.get("/whoami", headers=header)

    assert response.status_code == 401
    assert response.json() == {"error": "oauth.decode_error"}


# --- The verified caller reaches the app ------------------------------------


def test_a_verified_caller_gets_the_documented_identity(client, issuer):
    response = client.get("/whoami", headers=auth(issuer.verified))

    assert response.status_code == 200
    # Claim names only: `_identity` must never echo `user.claims` back.
    assert response.json() == {
        "subject": "alice@example.com",
        "tenant": "local-tenant",
        "issuer_id": "https://local-identity.invalid",
        "scopes": sorted(REQUIRED_SCOPES),
    }
    assert "claims" not in response.json()


def test_the_tool_answers_for_the_verified_caller_not_the_model_guess(client, issuer):
    """`call_tools` substitutes the verified subject for the model's guess."""
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
    # The exact three messages the README's offline section prints.
    assert body["messages"] == [
        TASK["task"],
        "Bookings for alice@example.com: Grand Ballroom on March 15th, 9AM-1PM; "
        "Rooftop Terrace on March 22nd, 6PM-11PM.",
        "You have two bookings: the Grand Ballroom on March 15th (9AM-1PM) and "
        "the Rooftop Terrace on March 22nd (6PM-11PM).",
    ]


def test_substitution_happens_in_the_graph_not_in_the_handler(client, issuer):
    result = asyncio.run(
        main.compiled.ainvoke(
            {"messages": [HumanMessage(content=TASK["task"])]},
            config={"configurable": {"user_subject": "dave@example.com"}},
        )
    )

    tool_answers = [m.content for m in result["messages"] if "Bookings for" in str(m.content)]
    assert tool_answers, "the graph did not reach the tool"
    assert "dave@example.com" in tool_answers[0]
    assert MODEL_GUESS not in tool_answers[0]


def test_an_unconfigured_subject_does_not_silently_become_the_model_guess():
    """A missing config key must not fall back to the model's argument.

    `call_tools` defaults `user_subject` to "", so a graph invoked without it
    answers for nobody rather than for the model's guess.
    """
    result = asyncio.run(
        main.compiled.ainvoke(
            {"messages": [HumanMessage(content=TASK["task"])]},
            config={"configurable": {}},
        )
    )

    joined = " ".join(str(m.content) for m in result["messages"])
    assert MODEL_GUESS not in joined


# --- Request validation -----------------------------------------------------


@pytest.mark.parametrize("payload", [{}, {"task": ""}, {"task": "   "}, {"task": 7}, []])
def test_a_task_that_is_not_a_non_empty_string_is_400(client, issuer, payload):
    # Validated after authentication: the same body unauthenticated is a 401.
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
    # JWKS requires unpadded base64url: a stdlib b64encode would emit "+", "/"
    # and "=", and PyJWKClient would reject the key.
    encoded = _b64u(65537)

    assert encoded == "AQAB", "the standard RSA exponent must encode as AQAB"
    assert "=" not in encoded
    assert "+" not in encoded and "/" not in encoded


def test_the_issuer_serves_a_jwks_the_verifier_can_read(issuer):
    # A malformed document would fail every credential-bearing test above as an
    # opaque 503, so it is worth asserting directly.
    import urllib.request

    with urllib.request.urlopen(issuer.config.jwks_uri, timeout=5) as response:
        document = json.load(response)

    assert [key["kid"] for key in document["keys"]] == ["local-quickstart-key"]
    assert document["keys"][0]["alg"] == "RS256"
