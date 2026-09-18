/**
 * An offline stand-in for the Catalyst identity plane.
 *
 * Opt in with DIAGRID_QUICKSTART_IDENTITY=local. It generates a throwaway RSA
 * key, serves the public half as JWKS on localhost, and logs the three
 * credentials behind this quickstart's 200, 403 and 401 responses.
 *
 * Never a real deployment: the private key lives in this process's memory and
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

const DEFAULT_LIFETIME_SECONDS = 3600;

// The verifier allows 120s of clock skew, so anything demonstrating
// oauth.expired has to be staler than that.
const EXPIRED_LIFETIME_SECONDS = -300;

/** A running throwaway issuer: its config, and the credentials it accepts. */
export interface LocalIssuer {
  readonly config: OAuthConfig;
  /** Carries the required scopes -> 200. */
  readonly verified: string;
  /** Verifies, carries the wrong scope -> 403 oauth.missing_scope. */
  readonly wrongScope: string;
  /** Carries the required scopes but is stale -> 401 oauth.expired. */
  readonly expired: string;
}

/** Start the throwaway issuer and mint the three credentials it accepts. */
export async function buildLocalIssuer(
  requiredScopes: readonly string[]
): Promise<LocalIssuer> {
  // `extractable` so the public half can leave the key object as a JWK below.
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
  // Without this the listening server would keep `node --test` from exiting.
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
      // Plain http needs no `allowInsecureJwks`: loopback is exempt from https.
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

/** Start the throwaway issuer, log its credentials, and return its config. */
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
