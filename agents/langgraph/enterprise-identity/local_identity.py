"""An offline stand-in for the Catalyst identity plane.

Opt in with DIAGRID_QUICKSTART_IDENTITY=local. It generates a throwaway RSA key,
serves the public half as JWKS on localhost, and logs three ready-to-paste
credentials so every response this quickstart describes -- 200, 403 and 401 --
is reachable with no Catalyst project and no identity provider.

Never a real deployment. The private key lives in this process's memory and the
credentials it signs are logged in plain text.
"""

import base64
import datetime
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import FrozenSet, Iterable, NamedTuple

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from diagrid.identity import OAuthConfig

ISSUER = "https://local-identity.invalid"
AUDIENCE = "catalyst-quickstart"
KID = "local-quickstart-key"

# The verifier allows 120s of clock skew, so anything demonstrating
# oauth.expired has to be older than that.
_EXPIRED_LIFETIME_SECONDS = -300


class LocalIssuer(NamedTuple):
    """A running throwaway issuer: its config, and the credentials it accepts."""

    config: OAuthConfig
    verified: str  # carries the required scopes -> 200
    wrong_scope: str  # verifies, carries the wrong scope -> 403 oauth.missing_scope
    expired: str  # carries the required scopes but is stale -> 401 oauth.expired


def _b64u(value: int) -> str:
    """Encode a public-key number the way JWKS wants it: base64url, no padding."""
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def build_local_issuer(required_scopes: FrozenSet[str]) -> LocalIssuer:
    """Start the throwaway issuer and mint the three credentials it accepts."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    numbers = key.public_key().public_numbers()
    jwks = json.dumps(
        {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": KID,
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64u(numbers.n),
                    "e": _b64u(numbers.e),
                }
            ]
        }
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(jwks)))
            self.end_headers()
            self.wfile.write(jwks)

        def log_message(self, *args: object) -> None:
            # The default handler writes every request to stderr, burying the
            # app's own log lines.
            pass

    # Port 0: the OS picks a free port.
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    jwks_uri = f"http://127.0.0.1:{server.server_port}/jwks.json"

    def mint(subject: str, scopes: Iterable[str], lifetime_seconds: int = 3600) -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        return jwt.encode(
            {
                "sub": subject,
                "iss": ISSUER,
                "aud": AUDIENCE,
                "tid": "local-tenant",
                "scp": " ".join(sorted(scopes)),
                "iat": now,
                "exp": now + datetime.timedelta(seconds=lifetime_seconds),
            },
            pem,
            algorithm="RS256",
            headers={"kid": KID},
        )

    return LocalIssuer(
        config=OAuthConfig(
            scopes=required_scopes,
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_uri=jwks_uri,
        ),
        verified=mint("alice@example.com", required_scopes),
        wrong_scope=mint("bob@example.com", {"reports.read"}),
        expired=mint("carol@example.com", required_scopes, _EXPIRED_LIFETIME_SECONDS),
    )


def start_local_issuer(required_scopes: FrozenSet[str]) -> OAuthConfig:
    """Start the throwaway issuer, log its credentials, and return its config."""
    issuer = build_local_issuer(required_scopes)

    logging.warning("LOCAL IDENTITY MODE - throwaway keys, never a real deployment")
    logging.info("JWKS served at %s", issuer.config.jwks_uri)
    logging.info("200 (verified, has %s):", " ".join(sorted(required_scopes)))
    logging.info("  %s", issuer.verified)
    logging.info("403 (verifies, wrong scope) oauth.missing_scope:")
    logging.info("  %s", issuer.wrong_scope)
    logging.info("401 (expired 5 minutes ago) oauth.expired:")
    logging.info("  %s", issuer.expired)

    return issuer.config
