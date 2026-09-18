/**
 * A stand-in CRM, exposed over MCP.
 *
 * Its one tool reports the identity the call arrived with: the agent sends no
 * password and no API key, and the CRM still knows whose question it is.
 */

import { USER_TOKEN_HEADER } from '@diagrid/agent-core';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import type { RequestHandlerExtra } from '@modelcontextprotocol/sdk/shared/protocol.js';
import express from 'express';
import { decodeJwt } from 'jose';
import { z } from 'zod';

const SERVER_NAME = 'crm';
const SERVER_VERSION = '1.0.0';
const MCP_PATH = '/mcp';
const DEFAULT_APP_PORT = 8007;
const HOST = '0.0.0.0';

/** Node lower-cases inbound header names, so the lookup key is lower-cased too. */
const USER_TOKEN_HEADER_KEY = USER_TOKEN_HEADER.toLowerCase();
const BEARER_PREFIX = 'bearer ';

const NO_USER = '<no user identity>';
const NO_AGENT = '<no agent>';

const HTTP_METHOD_NOT_ALLOWED = 405;

/** The two identities a delegated token names: the user, and the actor. */
interface CallingParties {
  readonly user: string;
  readonly agent: string;
}

/**
 * Read the calling user from the token Catalyst minted for this request.
 *
 * Catalyst verifies the signature before the request arrives, so `decodeJwt` is
 * jose's decode-only half on purpose: this CRM holds no identity coordinates.
 */
function callingParties(
  headers: Record<string, string | string[] | undefined>
): CallingParties {
  const header = headers[USER_TOKEN_HEADER_KEY];
  const raw = Array.isArray(header) ? (header[0] ?? '') : (header ?? '');
  const token = raw.toLowerCase().startsWith(BEARER_PREFIX)
    ? raw.slice(BEARER_PREFIX.length)
    : raw;
  if (!token) {
    return { user: NO_USER, agent: NO_AGENT };
  }

  const claims = decodeJwt(token);
  const actor = claims['act'] as { sub?: string } | undefined;
  return {
    user: claims.sub ?? NO_USER,
    agent: actor?.sub ?? NO_AGENT,
  };
}

/** The CRM's one tool. */
function buildServer(): McpServer {
  const mcp = new McpServer({ name: SERVER_NAME, version: SERVER_VERSION });

  mcp.registerTool(
    'account_summary',
    {
      description: 'Summarise a CRM account, and report who the CRM is answering.',
      inputSchema: { account_id: z.string() },
    },
    (
      { account_id }: { account_id: string },
      extra: RequestHandlerExtra<never, never>
    ) => {
      // MCP carries no identity of its own. The transport copies the inbound
      // HTTP headers onto every tool call, which is where the token arrives.
      const { user, agent } = callingParties(extra.requestInfo?.headers ?? {});
      console.log(
        `account_summary(${account_id}) for user=${user} via agent=${agent}`
      );
      return {
        content: [
          {
            type: 'text' as const,
            text:
              `Account ${account_id}: 3 open opportunities, $120k pipeline. ` +
              `Served to user=${user} via agent=${agent}.`,
          },
        ],
      };
    }
  );

  return mcp;
}

const app = express();
app.use(express.json());

// Stateless mode: Catalyst's MCP proxy opens its own connection for each tool
// call, so there is no session for a CRM to keep.
app.post(MCP_PATH, async (req, res) => {
  const mcp = buildServer();
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
  });
  res.on('close', () => {
    void transport.close();
    void mcp.close();
  });

  await mcp.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

// Stateless mode has no stream to resume and no session to delete, so the other
// Streamable HTTP methods are refused rather than left to answer 404.
app.all(MCP_PATH, (_req, res) => {
  res.status(HTTP_METHOD_NOT_ALLOWED).json({
    jsonrpc: '2.0',
    error: { code: -32000, message: 'Method not allowed.' },
    id: null,
  });
});

const port = Number(process.env['APP_PORT'] ?? DEFAULT_APP_PORT);
app.listen(port, HOST, () => {
  console.log(`CRM MCP server listening on http://${HOST}:${port}${MCP_PATH}`);
});
