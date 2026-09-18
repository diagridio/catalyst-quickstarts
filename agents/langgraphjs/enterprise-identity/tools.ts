/**
 * The agent's tools.
 *
 * Separate from main.ts so the tests can import the real tool without paying
 * for main.ts's module-level work: importing main.ts compiles the graph and
 * builds the model.
 *
 * Two tools, showing the two ways an agent can act for someone. `my_bookings`
 * runs in-process and is handed the caller's subject as an argument.
 * `account_summary` leaves the process, and carries the caller in a token
 * Catalyst mints for that one call.
 */

import { createIdentityFetch } from '@diagrid/agent-core';
import { tool } from '@langchain/core/tools';
import type { StructuredToolInterface } from '@langchain/core/tools';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { z } from 'zod';

export const myBookings = tool(
  ({ subject }: { subject: string }) =>
    `Bookings for ${subject}: ` +
    'Grand Ballroom on March 15th, 9AM-1PM; ' +
    'Rooftop Terrace on March 22nd, 6PM-11PM.',
  {
    name: 'my_bookings',
    description: 'List the bookings that belong to the calling user.',
    schema: z.object({ subject: z.string() }),
  }
);

// --- The outbound half: calling a tool as the user -------------------------
// `my_bookings` above runs in-process, so it trusts whatever subject the agent
// hands it. `account_summary` below leaves the process, and that changes the
// trust story: it takes no subject at all. The calling user travels in a token
// Catalyst mints for this one call, so the CRM establishes who is asking for
// itself rather than believing the agent.

const MCP_SERVER_NAME = 'crm-mcp';

/** The client half of the MCP handshake. Reported to the server on connect. */
const MCP_CLIENT_NAME = 'identity-agent';
const MCP_CLIENT_VERSION = '1.0.0';

// Catalyst's MCP proxy. Reaching a tool through this path is what attaches the
// calling user; calling the CRM directly would not.
const MCP_URL =
  `${process.env['DAPR_HTTP_ENDPOINT'] ?? 'http://localhost:3500'}` +
  `/v1.0/diagrid/mcp/${MCP_SERVER_NAME}`;

/**
 * A `fetch` that carries the calling user, built once for the process.
 *
 * Safe to share across requests: the caller is read at send time, not now, so
 * concurrent requests each carry their own. This is the second of the two
 * identity lines the README points at -- the other is the middleware install
 * in main.ts.
 */
const identityFetch = createIdentityFetch();

export const accountSummary = tool(
  async ({ account_id }: { account_id: string }) => {
    const transport = new StreamableHTTPClientTransport(new URL(MCP_URL), {
      fetch: identityFetch,
      // The sidecar's own API token, which authenticates the AGENT to Catalyst.
      // Orthogonal to the user token: this says which app is calling, and
      // `identityFetch` says which person it is calling for.
      requestInit: {
        headers: { 'dapr-api-token': process.env['DAPR_API_TOKEN'] ?? '' },
      },
    });
    const client = new Client({
      name: MCP_CLIENT_NAME,
      version: MCP_CLIENT_VERSION,
    });

    await client.connect(transport);
    try {
      const answer = await client.callTool({
        name: 'account_summary',
        arguments: { account_id },
      });
      // `callTool` types its result loosely, so the CRM's answer is read
      // through the shape the MCP specification gives a text content block.
      const [block] = answer.content as { type: string; text?: string }[];
      return block?.type === 'text' ? (block.text ?? '') : '';
    } finally {
      await client.close();
    }
  },
  {
    name: 'account_summary',
    description: 'Summarise a CRM account. Runs as the user who invoked the agent.',
    schema: z.object({ account_id: z.string() }),
  }
);

/** Tools keyed by the name the model asks for them under. */
function byName(
  tools: readonly StructuredToolInterface[]
): Record<string, StructuredToolInterface> {
  return Object.fromEntries(tools.map((entry) => [entry.name, entry]));
}

// The graph gets one tool or the other. The offline issuer has no Catalyst
// project behind it, so it cannot reach an MCP server; `my_bookings` keeps the
// whole walkthrough runnable there.
export const localTools: readonly StructuredToolInterface[] = [myBookings];
export const localToolsByName = byName(localTools);

export const catalystTools: readonly StructuredToolInterface[] = [accountSummary];
export const catalystToolsByName = byName(catalystTools);
