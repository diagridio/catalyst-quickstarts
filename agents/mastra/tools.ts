/**
 * Tools for the SRE Agent.
 *
 * Both are deterministic and offline on purpose — this quickstart is about the
 * *workflow* surviving a crash, not about a real monitoring backend being up.
 */

import { createTool } from '@mastra/core/tools';
import { z } from 'zod';

export const checkServiceHealth = createTool({
  id: 'checkServiceHealth',
  description: "Check a service's current health status.",
  inputSchema: z.object({
    service: z.string().describe('The service name'),
  }),
  outputSchema: z.object({
    service: z.string(),
    status: z.string(),
    latencyMs: z.number(),
    uptimePercent: z.number(),
  }),
  execute: ({ service }) =>
    Promise.resolve({
      service,
      status: 'degraded',
      latencyMs: 842,
      uptimePercent: 99.2,
    }),
});

export const calculateErrorRate = createTool({
  id: 'calculateErrorRate',
  description: 'Calculate an error rate percentage from request and failure counts.',
  inputSchema: z.object({
    totalRequests: z.number(),
    failedRequests: z.number(),
  }),
  outputSchema: z.object({ errorRatePercent: z.number() }),
  execute: ({ totalRequests, failedRequests }) => {
    if (totalRequests === 0) {
      // A tool error is information for the model, not a workflow failure —
      // the adapter reports it back so the model can correct the call.
      throw new Error('Cannot calculate an error rate with zero requests');
    }
    return Promise.resolve({
      errorRatePercent: Math.round((failedRequests / totalRequests) * 10000) / 100,
    });
  },
});

/** All demo tools, keyed the way Mastra's `tools` option expects. */
export const sreTools = { checkServiceHealth, calculateErrorRate };
