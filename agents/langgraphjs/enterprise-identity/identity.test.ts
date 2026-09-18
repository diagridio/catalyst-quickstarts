/**
 * Tests for the inbound-identity behaviour this quickstart demonstrates: the
 * 401, the 403, the 200, and the verified subject reaching the tool.
 *
 * Run with `npm test`. `buildLocalIssuer` stands in for the Catalyst identity
 * plane, so no Catalyst project, network or API key is needed.
 */

import assert from 'node:assert/strict';
import { once } from 'node:events';
import type { AddressInfo } from 'node:net';
import { after, describe, it } from 'node:test';

import { HumanMessage } from '@langchain/core/messages';

import { buildLocalIssuer } from './local_identity';

// Set before importing main, which picks its tool from this. The import is
// dynamic because a static one would be hoisted above this line.
process.env['DIAGRID_QUICKSTART_IDENTITY'] = 'local';
const main = await import('./main');

// main.ts's own value, not a copy.
const REQUIRED_SCOPES = main.LOCAL_REQUIRED_SCOPES;

// The subject the canned model asks for. It is nobody, and never reaches a tool.
const MODEL_GUESS = 'someone@example.com';

const TASK = { task: 'What bookings do I have?' };

const TOOL_ANSWER =
  'Bookings for alice@example.com: Grand Ballroom on March 15th, 9AM-1PM; ' +
  'Rooftop Terrace on March 22nd, 6PM-11PM.';

const MODEL_SUMMARY =
  'You have two bookings: the Grand Ballroom on March 15th (9AM-1PM) and ' +
  'the Rooftop Terrace on March 22nd (6PM-11PM).';

/** One throwaway issuer for the file: generating an RSA key is not free. */
const issuer = await buildLocalIssuer(REQUIRED_SCOPES);

// main.ts's own handlers and middleware, on a port the OS picks.
const server = main.buildApp(issuer.config).listen(0, '127.0.0.1');
await once(server, 'listening');
const BASE = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;

after(() => {
  server.close();
});

/** The header Catalyst sets on an inbound request, as the middleware reads it. */
function auth(token: string): Record<string, string> {
  return { 'X-Diagrid-User-Token': `Bearer ${token}` };
}

/** `response.json()` is typed `Promise<unknown>`, so callers say what they expect. */
async function json<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

function get(path: string, headers: Record<string, string> = {}): Promise<Response> {
  return fetch(`${BASE}${path}`, { headers });
}

function post(
  path: string,
  body: unknown,
  headers: Record<string, string> = {}
): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
}

describe('fail closed, before any application code runs', () => {
  for (const [method, path, payload] of [
    ['GET', '/whoami', undefined],
    ['POST', '/agent/run', TASK],
  ] as const) {
    it(`refuses ${method} ${path} with no credential`, async () => {
      const response =
        method === 'GET' ? await get(path) : await post(path, payload);

      assert.equal(response.status, 401);
      assert.deepEqual(await response.json(), { error: 'oauth.missing_token' });
      // An authorization verdict is not a cacheable response.
      assert.equal(response.headers.get('cache-control'), 'no-store');
    });
  }

  for (const value of ['', '   ']) {
    it(`treats the header ${JSON.stringify(value)} as no credential`, async () => {
      const response = await get('/whoami', { 'X-Diagrid-User-Token': value });

      assert.equal(response.status, 401);
      assert.deepEqual(await response.json(), { error: 'oauth.missing_token' });
    });
  }

  it('answers 403 for a credential without the required scope', async () => {
    // 403, not 401: authentication succeeded and authorization failed.
    const response = await get('/whoami', auth(issuer.wrongScope));

    assert.equal(response.status, 403);
    assert.deepEqual(await response.json(), { error: 'oauth.missing_scope' });
  });

  it('answers 401 for an expired credential', async () => {
    // Five minutes stale, because the verifier allows 120s of clock skew.
    const response = await get('/whoami', auth(issuer.expired));

    assert.equal(response.status, 401);
    assert.deepEqual(await response.json(), { error: 'oauth.expired' });
  });

  for (const value of [
    'Bearer not-a-jwt',
    // A bare "Bearer": the prefix includes its trailing space, so the literal
    // string is taken as the credential rather than read as an absent one.
    'Bearer',
  ]) {
    it(`answers 401 oauth.decode_error for ${JSON.stringify(value)}`, async () => {
      const response = await get('/whoami', { 'X-Diagrid-User-Token': value });

      assert.equal(response.status, 401);
      assert.deepEqual(await response.json(), { error: 'oauth.decode_error' });
    });
  }
});

describe('the verified caller reaches the app', () => {
  it('reports the documented identity', async () => {
    const response = await get('/whoami', auth(issuer.verified));

    assert.equal(response.status, 200);
    const body = await json<Record<string, unknown>>(response);
    // Claim names only: `identity()` must never echo back `user.claims`.
    assert.deepEqual(body, {
      subject: 'alice@example.com',
      tenant: 'local-tenant',
      issuerId: 'https://local-identity.invalid',
      scopes: [...REQUIRED_SCOPES].sort(),
    });
    assert.ok(!('claims' in body));
  });

  it('answers for the verified caller, not the model guess', async () => {
    // The thesis of the quickstart, end to end: the model asks for
    // someone@example.com and the answer names the verified alice@example.com.
    const response = await post('/agent/run', TASK, auth(issuer.verified));

    assert.equal(response.status, 200);
    const body = await json<{
      user: { subject: string };
      messages: string[];
    }>(response);
    assert.equal(body.user.subject, 'alice@example.com');
    assert.match(body.messages[1]!, /alice@example\.com/);
    assert.ok(
      !JSON.stringify(body).includes(MODEL_GUESS),
      "the model's guessed subject reached the response, so the tools node " +
        'stopped substituting the verified subject'
    );
    // The task, the tool's answer, and the model's summary of it.
    assert.deepEqual(body.messages, [TASK.task, TOOL_ANSWER, MODEL_SUMMARY]);
  });

  it('substitutes in the graph, not in the handler', async () => {
    // The real compiled graph, with no HTTP and no middleware: the substitution
    // lives in the `tools` node, not in the route handler.
    const result = await main.compiled.invoke(
      { messages: [new HumanMessage({ content: TASK.task })] },
      { configurable: { user_subject: 'dave@example.com' } }
    );

    const toolAnswers = result.messages
      .map((message) => String(message.content))
      .filter((content) => content.includes('Bookings for'));
    assert.ok(toolAnswers.length > 0, 'the graph did not reach the tool');
    assert.match(toolAnswers[0]!, /dave@example\.com/);
    assert.ok(!toolAnswers[0]!.includes(MODEL_GUESS));
  });

  it('does not fall back to the model guess when no subject is configured', async () => {
    // A missing config key answers for nobody, never the model's argument.
    const result = await main.compiled.invoke(
      { messages: [new HumanMessage({ content: TASK.task })] },
      { configurable: {} }
    );

    const joined = result.messages
      .map((message) => String(message.content))
      .join(' ');
    assert.ok(!joined.includes(MODEL_GUESS));
  });
});

describe('request validation', () => {
  for (const payload of [{}, { task: '' }, { task: '   ' }, { task: 7 }, []]) {
    it(`answers 400 for ${JSON.stringify(payload)}`, async () => {
      // Validated after authentication: the same body unauthenticated is a 401.
      const response = await post('/agent/run', payload, auth(issuer.verified));

      assert.equal(response.status, 400);
      const body = await json<{ error: string }>(response);
      assert.equal(body.error, 'bad_request');
    });
  }

  it('answers 400 for a body that is not JSON', async () => {
    const response = await post('/agent/run', 'not json', auth(issuer.verified));

    assert.equal(response.status, 400);
    const body = await json<{ detail: string }>(response);
    assert.equal(body.detail, 'body must be JSON');
  });

  it('reports a failure of its own as a generic 500, and logs the cause', async () => {
    // An oversized body is the one internal failure a client can provoke from
    // outside. console.error is captured because "logged server-side, never
    // returned to the caller" is the property under test.
    const logged: unknown[][] = [];
    const original = console.error;
    console.error = (...args: unknown[]) => {
      logged.push(args);
    };
    let response: Response;
    try {
      response = await post(
        '/agent/run',
        { task: 'x'.repeat(200_000) },
        auth(issuer.verified)
      );
    } finally {
      console.error = original;
    }

    assert.equal(response.status, 500);
    assert.match(
      response.headers.get('content-type') ?? '',
      /application\/json/
    );
    assert.deepEqual(await response.json(), { error: 'internal_error' });
    assert.equal(logged.length, 1, 'the cause was not logged');
  });
});

describe('the offline issuer itself', () => {
  it('serves a JWKS the verifier can read', async () => {
    // A malformed document would fail every test above as an opaque 503.
    const response = await fetch(issuer.config.jwksUri!);
    const document = await json<{ keys: { kid: string; alg: string }[] }>(response);

    assert.deepEqual(
      document.keys.map((key) => key.kid),
      ['local-quickstart-key']
    );
    assert.equal(document.keys[0]!.alg, 'RS256');
  });

  it('encodes the public key numbers as unpadded base64url', async () => {
    // JWKS requires unpadded base64url; jose rejects a key encoded any other way.
    const response = await fetch(issuer.config.jwksUri!);
    const document = await json<{ keys: { e: string; n: string }[] }>(response);
    const { e, n } = document.keys[0]!;

    assert.equal(e, 'AQAB', 'the standard RSA exponent must encode as AQAB');
    for (const value of [e, n]) {
      assert.ok(!/[=+/]/.test(value), `${value} is not base64url`);
    }
  });
});
