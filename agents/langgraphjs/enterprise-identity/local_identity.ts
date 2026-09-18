/**
 * An offline stand-in for the Catalyst identity plane.
 *
 * Opt in with DIAGRID_QUICKSTART_IDENTITY=local. It generates a throwaway RSA
 * key, serves the public half as JWKS on localhost, and logs three
 * ready-to-paste credentials so every response this quickstart describes --
 * 200, 403 and 401 -- is reachable with no Catalyst project and no identity
 * provider.
 *
 * Why it exists: 403 oauth.missing_scope needs a credential that genuinely
 * verifies. Against real Catalyst you cannot mint one that lacks a scope, and
 * with no issuer configured at all the middleware answers 503
 * oauth.not_configured instead. This is the only way the scope check is
 * observable. It is the same trade model.ts makes for the model: free, offline,
 * identical on every run.
 *
 * Never a real deployment. The private key lives in this process's memory and
 * the credentials it signs are logged in plain text.
 */

import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';

import type { OAuthConfig } from '@diagrid/agent-core';
import { SignJWT, exportJWK, generateKeyPair } from 'jose';

const ISSUER = 'https://local-identity.invalid';
const AUDIENCE = 'catalyst-quickstart';
const KID = 'local-quickstart-key';
const ALGORITHM = 'RS256';
const TENANT = 'local-tenant';

/** How long a credential minted for the happy path stays valid. */
const DEFAULT_LIFETIME_SECONDS = 3600;

// @diagrid/agent-core's verifier allows 120s of clock skew, so a credential
// that expired a minute ago still verifies. Anything demonstrating
// oauth.expired has to be older than that.
const EXPIRED_LIFETIME_SECONDS = -300;

/**
 * A running throwaway issuer: its config, and the credentials it accepts.
 *
 * `startLocalIssuer` returns only the config, because that is all main.ts
 * needs. The credentials are returned as well so that identity.test.ts can
 * present them, which is the only way the 200 and 403 paths are assertable
 * without a Catalyst project.
 */
export interface LocalIssuer {
  readonly config: OAuthConfig;
  /** Carries the required scopes -> 200. */
  readonly verified: string;
  /** Verifies, carries the wrong scope -> 403 oauth.missing_scope. */
  readonly wrongScope: string;
  /** Carries the required scopes but is stale -> 401 oauth.expired. */
  readonly expired: string;
}

/**
 * Start the throwaway issuer and mint the three credentials it accepts.
 *
 * Logs nothing: `startLocalIssuer` is the entry point that prints the
 * credentials for a reader to paste, and a test that already holds them has no
 * reason to write three JWTs to its own output.
 */
export async function buildLocalIssuer(
  requiredScopes: readonly string[]
): Promise<LocalIssuer> {
  // `extractable` because the public half has to leave the key object as a JWK
  // for the JWKS document below. The private half never does.
  const { privateKey, publicKey } = await generateKeyPair(ALGORITHM, {
    extractable: true,
  });
  const jwks = Buffer.from(
    JSON.stringify({
      keys: [
        {
          ...(await exportJWK(publicKey)),
          kid: KID,
          use: 'sig',
          alg: ALGORITHM,
        },
      ],
    })
  );

  const server = createServer((_request, response) => {
    response.writeHead(200, {
      'Content-Type': 'application/json',
      'Content-Length': String(jwks.byteLength),
    });
    response.end(jwks);
  });
  // Port 0: the OS picks a free one, so this never collides with the app.
  await new Promise<void>((resolve) => {
    server.listen(0, '127.0.0.1', resolve);
  });
  // The Node analogue of Python's daemon thread. Without it a listening server
  // keeps the event loop alive, so `node --test` would hang after the last
  // assertion instead of exiting.
  server.unref();
  const { port } = server.address() as AddressInfo;
  const jwksUri = `http://127.0.0.1:${port}/jwks.json`;

  const mint = (
    subject: string,
    scopes: readonly string[],
    lifetimeSeconds = DEFAULT_LIFETIME_SECONDS
  ): Promise<string> => {
    const now = Math.floor(Date.now() / 1000);
    return new SignJWT({ tid: TENANT, scp: [...scopes].sort().join(' ') })
      .setProtectedHeader({ alg: ALGORITHM, kid: KID })
      .setSubject(subject)
      .setIssuer(ISSUER)
      .setAudience(AUDIENCE)
      .setIssuedAt(now)
      .setExpirationTime(now + lifetimeSeconds)
      .sign(privateKey);
  };

  return {
    config: {
      scopes: requiredScopes,
      issuer: ISSUER,
      audience: AUDIENCE,
      // Plain http, and no `allowInsecureJwks`: the SDK exempts loopback hosts
      // from the https requirement, because that is where a local sidecar
      // publishes its keys. A flag that is not needed is not set.
      jwksUri,
    },
    verified: await mint('alice@example.com', requiredScopes),
    wrongScope: await mint('bob@example.com', ['reports.read']),
    expired: await mint(
      'carol@example.com',
      requiredScopes,
      EXPIRED_LIFETIME_SECONDS
    ),
  };
}

/**
 * Start the throwaway issuer, log its credentials, and return its config.
 *
 * This is what main.ts calls. The six log lines are the ones the README's
 * "## Run Offline Without a Catalyst Project" block reproduces, so their text
 * is part of the documented output.
 */
export async function startLocalIssuer(
  requiredScopes: readonly string[]
): Promise<OAuthConfig> {
  const issuer = await buildLocalIssuer(requiredScopes);

  console.warn(
    'LOCAL IDENTITY MODE - throwaway keys, never a real deployment'
  );
  console.log(`JWKS served at ${issuer.config.jwksUri}`);
  console.log(`200 (verified, has ${[...requiredScopes].sort().join(' ')}):`);
  console.log(`  ${issuer.verified}`);
  console.log('403 (verifies, wrong scope) oauth.missing_scope:');
  console.log(`  ${issuer.wrongScope}`);
  console.log('401 (expired 5 minutes ago) oauth.expired:');
  console.log(`  ${issuer.expired}`);

  return issuer.config;
}
