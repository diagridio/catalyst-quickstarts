/**
 * A LangGraph.js agent that knows who is calling it.
 *
 * Run with Catalyst:
 *   diagrid dev run -f dev-enterprise-identity.yaml --approve \
 *     --skip-managed-kv --skip-managed-pubsub --skip-managed-workflow
 *
 * See README.md for the walkthrough, and for the offline mode that needs no
 * Catalyst project at all.
 */

import { pathToFileURL } from 'node:url';

import type { OAuthConfig, VerifiedUser } from '@diagrid/agent-core';
import {
  getVerifiedUser,
  oauthMiddleware,
} from '@diagrid/agent-core/express';
import { HumanMessage, ToolMessage } from '@langchain/core/messages';
import type { AIMessage } from '@langchain/core/messages';
import type { StructuredToolInterface } from '@langchain/core/tools';
import { END, MessagesAnnotation, START, StateGraph } from '@langchain/langgraph';
import type { LangGraphRunnableConfig } from '@langchain/langgraph';
import express from 'express';
import type { NextFunction, Request, Response } from 'express';

import { buildModel } from './model';
import {
  catalystTools,
  catalystToolsByName,
  localTools,
  localToolsByName,
} from './tools';

// Only the offline issuer demands a scope. Scopes come from your identity
// provider, and a Diagrid login carries `openid profile email offline_access`.
// See "On scopes" in the README.
export const LOCAL_REQUIRED_SCOPES: readonly string[] = ['agent.invoke'];

/** The graph config key the verified subject travels under. */
const USER_SUBJECT_KEY = 'user_subject';

/** The tool argument the `tools` node fills in from the verified caller. */
const SUBJECT_ARG = 'subject';

const HTTP_BAD_REQUEST = 400;
const HTTP_INTERNAL_SERVER_ERROR = 500;

/** body-parser stamps this on the error it raises for an unparseable body. */
const BODY_PARSE_FAILED = 'entity.parse.failed';

const DEFAULT_APP_PORT = 8006;
const HOST = '0.0.0.0';

// Which identity plane the app trusts, and so which tool the graph can use.
// The offline issuer runs with no Catalyst project behind it, so there is no MCP
// server to reach and the graph calls the in-process tool instead. Against
// Catalyst the tool call leaves the agent and picks the caller up on the way.
const OFFLINE_IDENTITY = process.env['DIAGRID_QUICKSTART_IDENTITY'] === 'local';
const tools = OFFLINE_IDENTITY ? localTools : catalystTools;
const toolsByName = OFFLINE_IDENTITY ? localToolsByName : catalystToolsByName;

const chatModel = await buildModel(OFFLINE_IDENTITY);
// `bindTools` is an optional member of BaseChatModel -- some providers cannot
// call tools at all -- so it is checked rather than asserted away.
if (!chatModel.bindTools) {
  throw new Error(
    `the configured model (${chatModel._llmType()}) cannot call tools`
  );
}
const model = chatModel.bindTools([...tools]);

async function callModel(
  state: typeof MessagesAnnotation.State
): Promise<{ messages: AIMessage[] }> {
  const response = await model.invoke(state.messages);
  return { messages: [response] };
}

/**
 * Whether the caller's identity belongs in this tool call's arguments.
 *
 * Asking the schema rather than hardcoding a tool name keeps the substitution
 * correct as tools are added: a new tool taking a subject is substituted into
 * without a change here, and one that takes none cannot be handed a caller.
 *
 * A subject the model supplied counts on its own, whatever the schema said, so
 * the model's value is always overwritten rather than trusted.
 */
function takesSubject(
  tool: StructuredToolInterface,
  args: Record<string, unknown>
): boolean {
  if (SUBJECT_ARG in args) {
    return true;
  }
  const schema = tool.schema as {
    shape?: Record<string, unknown>;
    properties?: Record<string, unknown>;
  };
  const declared = schema.shape ?? schema.properties;
  return declared !== undefined && SUBJECT_ARG in declared;
}

/**
 * Run the requested tools on behalf of the verified caller.
 *
 * The subject comes from the graph's config, which the HTTP handler filled in
 * from the middleware's VerifiedUser, and it overrides whatever subject the
 * model asked for. A model can request anybody's bookings; only the verified
 * caller's are ever served. Substituting beats validating here -- there is no
 * version of this where the model's opinion of who is calling matters.
 */
async function callTools(
  state: typeof MessagesAnnotation.State,
  config: LangGraphRunnableConfig
): Promise<{ messages: ToolMessage[] }> {
  // Defaulting to '' rather than falling through to the model's argument: a
  // graph invoked with no subject answers for nobody, which is the safe
  // direction.
  const subject = (config.configurable?.[USER_SUBJECT_KEY] as string) ?? '';
  const lastMessage = state.messages[state.messages.length - 1] as AIMessage;
  const results: ToolMessage[] = [];

  for (const call of lastMessage.tool_calls ?? []) {
    const tool = toolsByName[call.name];
    if (!tool) {
      throw new Error(`the model asked for an unknown tool: ${call.name}`);
    }
    const args = takesSubject(tool, call.args)
      ? { ...call.args, [SUBJECT_ARG]: subject }
      : call.args;
    console.log(`[IDENTITY] tool call for subject=${subject}`);
    const result: unknown = await tool.invoke(args);
    results.push(
      new ToolMessage({ content: String(result), tool_call_id: call.id ?? '' })
    );
  }

  return { messages: results };
}

function shouldUseTools(state: typeof MessagesAnnotation.State): string {
  const lastMessage = state.messages[state.messages.length - 1] as AIMessage;
  return lastMessage.tool_calls?.length ? 'tools' : END;
}

// An ordinary LangGraph graph. Note what is absent: there is no Diagrid import
// in any node, and no node reads a header or a credential. Identity is handled
// entirely in the HTTP layer below and reaches the graph as plain config.
export const compiled = new StateGraph(MessagesAnnotation)
  .addNode('agent', callModel)
  .addNode('tools', callTools)
  .addEdge(START, 'agent')
  .addConditionalEdges('agent', shouldUseTools)
  .addEdge('tools', 'agent')
  .compile();

/**
 * The identity policy the middleware enforces on every request.
 *
 * Against Catalyst this is one empty object -- issuer, audience and JWKS URI
 * are all discovered from Catalyst, so the app configures none of them.
 *
 * To require a scope as well, pass one: `{ scopes: ['reports.read'] }` answers
 * 403 for any verified caller without it. That needs an identity provider
 * issuing the scope, which is why the walkthrough does not use it.
 *
 * DIAGRID_QUICKSTART_IDENTITY=local swaps in a throwaway offline issuer so the
 * 200, 403 and 401 responses are all reachable with no Catalyst project and no
 * identity provider at all. See local_identity.ts.
 *
 * The import is dynamic, and that is load-bearing rather than stylistic:
 * .dockerignore keeps local_identity.ts out of the image, so setting the
 * variable on a derived container fails to start instead of quietly trusting
 * tokens the app minted itself.
 */
async function buildOAuthConfig(): Promise<OAuthConfig> {
  if (OFFLINE_IDENTITY) {
    const { startLocalIssuer } = await import('./local_identity');
    return startLocalIssuer(LOCAL_REQUIRED_SCOPES);
  }

  return {};
}

/**
 * The verified caller, as JSON.
 *
 * Claim names only, never claim values: `user.claims` is a real person's
 * decoded credential, and echoing it back would leak whatever the identity
 * provider chose to put there.
 */
function identity(user: VerifiedUser): Record<string, unknown> {
  return {
    subject: user.subject,
    tenant: user.tenant,
    issuerId: user.issuerId,
    scopes: user.scopes,
  };
}

/**
 * The verified caller, or `undefined` once the request has been answered.
 *
 * `getVerifiedUser` is honestly typed `VerifiedUser | undefined`, because a
 * route that `requireAuth: false` opened up has no caller to report. This app
 * leaves `requireAuth` at its default, so the guard is written out rather than
 * cast away. It answers 500 rather than an oauth error code, which only the
 * middleware produces.
 */
function requireUser(req: Request, res: Response): VerifiedUser | undefined {
  const user = getVerifiedUser(req);
  if (!user) {
    res.status(HTTP_INTERNAL_SERVER_ERROR).end();
  }
  return user;
}

function badRequest(res: Response, detail: string): void {
  res.status(HTTP_BAD_REQUEST).json({ error: 'bad_request', detail });
}

/** Whether `error` is body-parser refusing a body that is not JSON. */
function isBodyParseError(error: unknown): boolean {
  return (
    error instanceof SyntaxError &&
    (error as { type?: string }).type === BODY_PARSE_FAILED
  );
}

/**
 * The app, assembled around one identity policy.
 */
export function buildApp(config: OAuthConfig): express.Express {
  const app = express();
  // Express advertises itself on every response by default. An app behind
  // Catalyst has no reason to tell callers what it is built on.
  app.disable('x-powered-by');
  // Both routes answer per-caller, so no ETag is sent: a validator would invite
  // a shared cache to store one person's identity.
  app.disable('etag');

  // --- The entire Catalyst identity integration ----------------------------
  app.use(oauthMiddleware(config));
  // -------------------------------------------------------------------------
  // requireAuth stays at its default true, so every route is authenticated.
  // That is why no health route is exposed and why dev-enterprise-identity.yaml
  // sets enableAppHealthCheck: false -- an unauthenticated probe would only
  // ever see the 401. There is no per-path exclusion; requireAuth is app-wide.
  //
  // Body parsing is mounted after the middleware and only on the route that
  // reads a body, so an unauthenticated request is refused before the app
  // spends anything on its payload.
  //
  // `type: () => true` parses every body as JSON whatever the Content-Type.
  const parseJsonBody = express.json({ type: () => true });

  /** Who Catalyst says is calling. No model turn, so the 401/200 contrast is free. */
  app.get('/whoami', (req, res) => {
    const user = requireUser(req, res);
    if (!user) {
      return;
    }
    res.json(identity(user));
  });

  app.post('/agent/run', parseJsonBody, async (req, res) => {
    const user = requireUser(req, res);
    if (!user) {
      return;
    }
    console.log(
      `[IDENTITY] verified caller subject=${user.subject} issuer=${user.issuerId}`
    );

    const body: unknown = req.body;
    const task =
      typeof body === 'object' && body !== null && !Array.isArray(body)
        ? (body as Record<string, unknown>)['task']
        : undefined;
    if (typeof task !== 'string' || task.trim() === '') {
      badRequest(res, 'task must be a non-empty string');
      return;
    }

    // The verified subject travels as config, not as a message the model could
    // rewrite.
    const result = await compiled.invoke(
      { messages: [new HumanMessage({ content: task })] },
      { configurable: { [USER_SUBJECT_KEY]: user.subject } }
    );

    res.json({
      user: identity(user),
      // Drops the empty-content AIMessage that carries only tool_calls.
      messages: result.messages
        .map((message) => String(message.content))
        .filter((content) => content !== ''),
    });
  });

  // Registered last, because an error handler only sees what the handlers ahead
  // of it passed on. express.json() rejects a body that is not JSON, and this
  // turns that into the documented 400 instead of express's default HTML page.
  app.use(
    (error: unknown, req: Request, res: Response, next: NextFunction): void => {
      if (isBodyParseError(error)) {
        badRequest(res, 'body must be JSON');
        return;
      }
      if (res.headersSent) {
        // Nothing left to answer with. Express closes the connection.
        next(error);
        return;
      }
      // Anything else is this app failing rather than the caller. An app that
      // fails while holding a verified caller's credential should not describe
      // its own internals: the stack goes to the log, and the response says
      // only that the request failed.
      console.error(`[ERROR] ${req.method} ${req.path} failed`, error);
      res.status(HTTP_INTERNAL_SERVER_ERROR).json({ error: 'internal_error' });
    }
  );

  return app;
}

// Guarded so this module can be imported without starting a server or binding
// a port.
if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const port = Number(process.env['APP_PORT'] ?? DEFAULT_APP_PORT);
  buildApp(await buildOAuthConfig()).listen(port, HOST, () => {
    console.log(`Listening on http://${HOST}:${port}`);
  });
}
