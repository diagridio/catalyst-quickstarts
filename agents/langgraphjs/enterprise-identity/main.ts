/** A LangGraph.js agent that knows who is calling it. See README.md to run it. */

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

// Only the offline issuer demands a scope; real scopes come from your provider.
export const LOCAL_REQUIRED_SCOPES: readonly string[] = ['agent.invoke'];

/** The graph config key the verified subject travels under. */
const USER_SUBJECT_KEY = 'user_subject';

const SUBJECT_ARG = 'subject';

const HTTP_BAD_REQUEST = 400;
const HTTP_INTERNAL_SERVER_ERROR = 500;

/** body-parser stamps this on the error it raises for an unparseable body. */
const BODY_PARSE_FAILED = 'entity.parse.failed';

const DEFAULT_APP_PORT = 8006;
const HOST = '0.0.0.0';

// The offline issuer has no Catalyst project behind it, and so no MCP server to
// reach: that mode runs the in-process tool instead.
const OFFLINE_IDENTITY = process.env['DIAGRID_QUICKSTART_IDENTITY'] === 'local';
const tools = OFFLINE_IDENTITY ? localTools : catalystTools;
const toolsByName = OFFLINE_IDENTITY ? localToolsByName : catalystToolsByName;

const chatModel = await buildModel(OFFLINE_IDENTITY);
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

/** Whether the caller's identity belongs in this tool call's arguments. */
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
 * The subject comes from the graph's config and overrides whatever subject the
 * model asked for: a model can request anybody's bookings, but only the
 * verified caller's are ever served.
 */
async function callTools(
  state: typeof MessagesAnnotation.State,
  config: LangGraphRunnableConfig
): Promise<{ messages: ToolMessage[] }> {
  // A graph invoked with no subject answers for nobody, never the model's guess.
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

// An ordinary LangGraph graph: no node reads a header or a credential. Identity
// is handled in the HTTP layer below and reaches the graph as plain config.
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
 * Against Catalyst this is one empty object: issuer, audience and JWKS URI are
 * all discovered, so the app configures none of them.
 *
 * The dynamic import is load-bearing: .dockerignore keeps local_identity.ts out
 * of the image, so the offline issuer cannot be switched on in a container.
 */
async function buildOAuthConfig(): Promise<OAuthConfig> {
  if (OFFLINE_IDENTITY) {
    const { startLocalIssuer } = await import('./local_identity');
    return startLocalIssuer(LOCAL_REQUIRED_SCOPES);
  }

  return {};
}

/**
 * The verified caller, as JSON. Claim names only, never claim values:
 * `user.claims` is a real person's decoded credential.
 */
function identity(user: VerifiedUser): Record<string, unknown> {
  return {
    subject: user.subject,
    tenant: user.tenant,
    issuerId: user.issuerId,
    scopes: user.scopes,
  };
}

/** The verified caller, or `undefined` once the request has been answered. */
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

function isBodyParseError(error: unknown): boolean {
  return (
    error instanceof SyntaxError &&
    (error as { type?: string }).type === BODY_PARSE_FAILED
  );
}

/** The app, assembled around one identity policy. */
export function buildApp(config: OAuthConfig): express.Express {
  const app = express();
  app.disable('x-powered-by');
  // Responses are per-caller, so no ETag: a validator would invite a shared
  // cache to store one person's identity.
  app.disable('etag');

  // --- The entire Catalyst identity integration ----------------------------
  app.use(oauthMiddleware(config));
  // -------------------------------------------------------------------------

  // Mounted after the middleware, so an unauthenticated request is refused
  // before the app spends anything on its body. `type` parses any Content-Type.
  const parseJsonBody = express.json({ type: () => true });

  /** Who Catalyst says is calling. */
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

    // The subject travels as config, not as a message the model could rewrite.
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

  // Registered last: an error handler only sees what the handlers ahead of it
  // passed on.
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
      // The stack goes to the log; the response must not describe this app's
      // internals to whoever asked.
      console.error(`[ERROR] ${req.method} ${req.path} failed`, error);
      res.status(HTTP_INTERNAL_SERVER_ERROR).json({ error: 'internal_error' });
    }
  );

  return app;
}

// Guarded so this module can be imported without binding a port.
if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const port = Number(process.env['APP_PORT'] ?? DEFAULT_APP_PORT);
  buildApp(await buildOAuthConfig()).listen(port, HOST, () => {
    console.log(`Listening on http://${HOST}:${port}`);
  });
}
