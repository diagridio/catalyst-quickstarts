/**
 * Tests for the inbound-identity behaviour this quickstart demonstrates.
 *
 * Run from this directory with:
 *
 *     npm test
 *
 * which is `node --import tsx --test *.test.ts`: node's own test runner and
 * `node:assert`, so no test framework is a dependency of this quickstart.
 *
 * They cover the 401, the 403, the 200 and the verified subject reaching the
 * tool. No Catalyst project, no network and no API key: `buildLocalIssuer` from
 * local_identity.ts stands in for the Catalyst identity plane, signing with a
 * throwaway key it generates in-process.
 *
 * The app is not re-assembled here. main.ts exports `buildApp(config)`, so
 * these tests drive its own handlers, its own compiled graph and its own
 * required-scope constant.
 */

import assert from 'node:assert/strict';
import { once } from 'node:events';
import type { AddressInfo } from 'node:net';
import { after, describe, it } from 'node:test';

import { HumanMessage } from '@langchain/core/messages';

import { buildLocalIssuer } from './local_identity';

// Before importing main: the mode decides which tool the graph gets, and these
// tests are the offline one. Importing main with this unset would build a graph
// whose tool call needs a Catalyst project. A dynamic import is what makes the
// ordering expressible -- a static `import` would be hoisted above this line.
process.env['DIAGRID_QUICKSTART_IDENTITY'] = 'local';
const main = await import('./main');

// main.ts's own value, not a copy. A change to the app's required scope shows up
// here as the 200 and 403 cases swapping over, which is the intended failure.
const REQUIRED_SCOPES = main.LOCAL_REQUIRED_SCOPES;

// The subject model.ts's canned first turn asks the tool for. It is nobody, and
// the whole point of the `tools` node is that it never reaches the tool.
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

// The app under test: main.ts's handlers behind main.ts's middleware, on a port
// the OS picks so this never collides with a `dev run` on 8006.
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

/**
 * `response.json()` is typed `Promise<unknown>`, so every caller says what it
 * expects rather than each assertion casting inline.
 */
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
      // `requireAuth` defaults to true and oauthMiddleware is installed with
      // `app.use`, so this is the app-wide rule the README claims, checked on
      // both documented routes rather than on one and assumed for the other.
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
      // The README claims "no header, or an empty one" is 401, so both halves
      // are checked. `trimBearer` strips whitespace, so a blank value leaves an
      // empty token and takes the same branch as an absent header.
      const response = await get('/whoami', { 'X-Diagrid-User-Token': value });

      assert.equal(response.status, 401);
      assert.deepEqual(await response.json(), { error: 'oauth.missing_token' });
    });
  }

  it('answers 403 for a credential without the required scope', async () => {
    // 403, not 401, and the distinction is the point: authentication succeeded
    // and authorization failed. The credential is signed by the same issuer and
    // has not expired -- it simply carries `reports.read`.
    const response = await get('/whoami', auth(issuer.wrongScope));

    assert.equal(response.status, 403);
    assert.deepEqual(await response.json(), { error: 'oauth.missing_scope' });
  });

  it('answers 401 for an expired credential', async () => {
    // Five minutes stale, because the verifier allows 120s of clock skew. If
    // local_identity's EXPIRED_LIFETIME_SECONDS ever creeps inside that window
    // this returns 200 and fails here rather than in a reader's terminal.
    const response = await get('/whoami', auth(issuer.expired));

    assert.equal(response.status, 401);
    assert.deepEqual(await response.json(), { error: 'oauth.expired' });
  });

  for (const value of [
    'Bearer not-a-jwt',
    // A bare "Bearer" with nothing after it, which looks like an empty
    // credential but is not one. BEARER_PREFIX is "Bearer " -- the trailing
    // space is part of it -- and HTTP strips trailing header whitespace, so the
    // prefix never matches and the literal string "Bearer" is taken as the
    // token. It therefore lands here, among the malformed tokens, rather than on
    // the oauth.missing_token path an empty header gets. Same status either way,
    // but a different code, and that is worth pinning.
    'Bearer',
  ]) {
    it(`answers 401 oauth.decode_error for ${JSON.stringify(value)}`, async () => {
      // Asserting the code and not just the status: 401 alone would still pass
      // if a future version routed this through missing_token or
      // invalid_signature, and those mean different things to a reader
      // debugging a real credential.
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
    // The exact object the README's offline section prints. Claim NAMES only:
    // `user.claims` is a real person's decoded credential in a deployment, and
    // `identity()` must not start echoing it back.
    assert.deepEqual(body, {
      subject: 'alice@example.com',
      tenant: 'local-tenant',
      issuerId: 'https://local-identity.invalid',
      scopes: [...REQUIRED_SCOPES].sort(),
    });
    assert.ok(!('claims' in body));
  });

  it('answers for the verified caller, not the model guess', async () => {
    // The thesis of the whole quickstart, asserted end to end. The canned model
    // asks `my_bookings` for someone@example.com. `callTools` substitutes the
    // subject the middleware verified, so the answer names alice@example.com and
    // the model's guess appears nowhere in the response.
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
    // The exact three messages the README's offline section prints: the task,
    // the tool's answer, and the model's summary of it.
    assert.deepEqual(body.messages, [TASK.task, TOOL_ANSWER, MODEL_SUMMARY]);
  });

  it('substitutes in the graph, not in the handler', async () => {
    // Invoke the real compiled graph directly, with no HTTP and no middleware.
    // Proves the substitution lives in the `tools` node rather than in the route
    // handler: the subject travels as graph config, which is exactly why a
    // message the model could rewrite is not involved.
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
    // A missing config key must not fall back to the model's argument.
    // `callTools` reads `user_subject` with a default of '', so a graph invoked
    // without it answers for nobody. That is the safe direction; falling
    // through to the model's someone@example.com would be the unsafe one.
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
      // Validated after authentication, so a bad body from a verified caller is
      // a 400 while the same body from an anonymous one is still a 401.
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
    // A body over express.json's size limit is the one failure a client can
    // provoke from outside, and it reaches the same error handler as the one
    // that matters: an outbound MCP call that cannot reach Catalyst. What is
    // asserted is the shape rather than the status. Express's default handler
    // answers an HTML page carrying the stack and this repository's absolute
    // paths, and an app that fails while holding a verified caller's credential
    // must not describe its own internals to whoever asked.
    //
    // console.error is captured, not merely allowed: the stack has to go
    // somewhere, and "logged server-side" is half of the property under test.
    // Capturing it also keeps a passing run from printing a stack trace a
    // reader would take for a failure.
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
    // The middleware fetches this document over the loopback port the OS picked.
    // If it were malformed every credential-bearing test above would fail as a
    // 503, so this makes the cause legible.
    const response = await fetch(issuer.config.jwksUri!);
    const document = await json<{ keys: { kid: string; alg: string }[] }>(response);

    assert.deepEqual(
      document.keys.map((key) => key.kid),
      ['local-quickstart-key']
    );
    assert.equal(document.keys[0]!.alg, 'RS256');
  });

  it('encodes the public key numbers as unpadded base64url', async () => {
    // JWKS requires unpadded base64url. Standard base64 would emit "+" and "/"
    // and pad with "=", and jose would reject the key -- which would surface as
    // an opaque 503 rather than as a wrong-encoding error.
    const response = await fetch(issuer.config.jwksUri!);
    const document = await json<{ keys: { e: string; n: string }[] }>(response);
    const { e, n } = document.keys[0]!;

    assert.equal(e, 'AQAB', 'the standard RSA exponent must encode as AQAB');
    for (const value of [e, n]) {
      assert.ok(!/[=+/]/.test(value), `${value} is not base64url`);
    }
  });
});
