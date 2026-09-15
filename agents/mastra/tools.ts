/**
 * Tools for the Trip Assistant agent.
 *
 * Both are deterministic and offline on purpose — this quickstart is about the
 * *workflow* surviving a crash, not about a third-party API being up.
 */

import { createTool } from '@mastra/core/tools';
import { z } from 'zod';

export const calculate = createTool({
  id: 'calculate',
  description: 'Perform an arithmetic calculation, e.g. to split a bill or total a budget.',
  inputSchema: z.object({
    a: z.number(),
    b: z.number(),
    op: z.enum(['add', 'subtract', 'multiply', 'divide']),
  }),
  outputSchema: z.object({ result: z.number() }),
  execute: ({ a, b, op }) => {
    switch (op) {
      case 'add':
        return Promise.resolve({ result: a + b });
      case 'subtract':
        return Promise.resolve({ result: a - b });
      case 'multiply':
        return Promise.resolve({ result: a * b });
      case 'divide':
        if (b === 0) {
          // A tool error is information for the model, not a workflow failure —
          // the adapter reports it back so the model can correct the call.
          throw new Error('Cannot divide by zero');
        }
        return Promise.resolve({ result: a / b });
    }
  },
});

export const getWeather = createTool({
  id: 'getWeather',
  description: 'Get the current weather for a city.',
  inputSchema: z.object({
    city: z.string().describe('The city name'),
  }),
  outputSchema: z.object({
    city: z.string(),
    summary: z.string(),
    temperatureC: z.number(),
  }),
  execute: ({ city }) =>
    Promise.resolve({ city, summary: 'Sunny', temperatureC: 22 }),
});

/** All demo tools, keyed the way Mastra's `tools` option expects. */
export const tripTools = { calculate, getWeather };
