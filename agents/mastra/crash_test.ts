/**
 * Crash Recovery Test — proves the agent survives its process being killed
 * mid-turn. This is the whole point of running an agent on Dapr Workflows via
 * Catalyst, so it's worth demonstrating rather than taking on faith.
 *
 * Run it twice, with the same command:
 *
 *   diagrid dev run -f dev-crash-test.yaml --approve
 *
 * Run 1 schedules a turn under a workflow ID this script owns, then crashes
 * itself (`process.exit(1)`) partway through — after the first model call and
 * the `checkFlightStatus` tool call have both completed and been checkpointed
 * by Catalyst, but before the second (and final) model call returns. Run 2
 * reconnects to the SAME workflow instance and waits for it to finish.
 *
 * `checkFlightStatus` logs every time it actually runs, and that count is
 * saved to a state file alongside the model-call count. If recovery worked,
 * the tool ran exactly ONCE across both runs — its result was replayed from
 * Catalyst's workflow history on run 2, not recomputed. See README.md for the
 * full walkthrough and what to expect in each run's output.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { Agent } from '@mastra/core/agent';
import { createTool } from '@mastra/core/tools';
import {
  DaprWorkflowAgentRunner,
  type InvokeModelInput,
} from '@diagrid/agent-mastra';
import { z } from 'zod';

import { resolveModel } from './model';

const STATE_FILE = join(tmpdir(), 'diagrid-mastra-crash-state.json');
/** Reusing one thread id across runs is what lets Catalyst resume the same turn. */
const THREAD_ID = 'crash-recovery-demo';
const WORKFLOW_ID = `crash-demo-${THREAD_ID}`;
/** Crash during this model call. 2 = after the first model call and tool call. */
const CRASH_ON_MODEL_CALL = 2;

interface CrashState {
  runCount: number;
  modelCalls: number;
  toolRuns: number;
  crashed: boolean;
}

function loadState(): CrashState {
  if (!existsSync(STATE_FILE)) {
    return { runCount: 0, modelCalls: 0, toolRuns: 0, crashed: false };
  }
  return JSON.parse(readFileSync(STATE_FILE, 'utf8')) as CrashState;
}

function saveState(state: CrashState): void {
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

// Run this file with `rm -f <state file>` first (see README) so run 1 always
// starts clean, the same way every other crash-recovery demo in this repo does.
const startState = loadState();
startState.runCount += 1;
saveState(startState);

const checkFlightStatus = createTool({
  id: 'checkFlightStatus',
  description: 'Check the status of a flight by its flight number.',
  inputSchema: z.object({ flightNumber: z.string().describe('e.g. DL202') }),
  outputSchema: z.object({ flightNumber: z.string(), status: z.string() }),
  execute: ({ flightNumber }) => {
    const state = loadState();
    state.toolRuns += 1;
    saveState(state);
    console.log(`>>> checkFlightStatus ran (total across runs: ${state.toolRuns})`);
    return Promise.resolve({ flightNumber, status: 'on time, gate B12' });
  },
});

async function main(): Promise<void> {
  console.log('='.repeat(60));
  console.log(`RUN #${startState.runCount}`);
  console.log(`State file:      ${STATE_FILE}`);
  console.log(`Model calls:     ${startState.modelCalls} so far`);
  console.log(`Tool runs:       ${startState.toolRuns} so far`);
  console.log(`Already crashed: ${startState.crashed}`);
  console.log('='.repeat(60));

  const agent = new Agent({
    id: 'trip-assistant',
    name: 'trip-assistant',
    instructions:
      'You look up flight statuses. Always use the checkFlightStatus tool to ' +
      'answer, then report the status in one short sentence.',
    model: resolveModel(),
    tools: { checkFlightStatus },
  });

  // Same runner `name` as main.ts. That's what the workflow name and the
  // Catalyst agent registry entry are keyed on, so this demo's crash-recovery
  // run and its happy-path run show up under the one "trip-assistant" agent
  // in Catalyst rather than two unrelated identities.
  const runner = new DaprWorkflowAgentRunner({
    agent,
    name: 'trip-assistant',
    maxIterations: 10,
  });

  try {
    await runner.start();

    // Wrap the runner's own invoker with a counter, so the crash point is
    // decided deterministically by us rather than by how the model happens to
    // behave. `setModelInvoker` is the supported hook for this.
    const realInvoker = runner.modelInvoker;
    runner.setModelInvoker(async (input: InvokeModelInput) => {
      const state = loadState();

      if (state.modelCalls + 1 === CRASH_ON_MODEL_CALL && !state.crashed) {
        state.crashed = true;
        saveState(state);
        console.log(
          `\n>>> Killing the process during model call ${CRASH_ON_MODEL_CALL}, ` +
            'before it returns.\n>>> Run "npm run crash-test" again — Catalyst ' +
            'will resume this workflow.'
        );
        // Un-catchable, like a real crash: the activity never completes, so
        // Catalyst has to recover the instance rather than just retrying a
        // failure.
        process.exit(1);
      }

      state.modelCalls += 1;
      saveState(state);
      console.log(`>>> Model call ${state.modelCalls} (total across runs)`);
      return realInvoker(input);
    });

    // Run 1 schedules the turn under a workflow ID we chose. Run 2 must NOT
    // schedule again — the interrupted instance is still active in Catalyst,
    // which rejects a second schedule with the same ID. Recovery is automatic:
    // the moment this process's worker reconnects, Catalyst redelivers the
    // pending work, so all run 2 has to do is attach and wait.
    const result = startState.crashed
      ? await runner.waitFor(WORKFLOW_ID)
      : await runner.invoke(
          {
            prompt: 'What is the status of flight DL202?',
            threadId: THREAD_ID,
            maxIterations: 10,
            messages: [],
          },
          { workflowId: WORKFLOW_ID }
        );

    const finalState = loadState();
    console.log('\n' + '='.repeat(60));
    console.log(`Status:      ${result.status}`);
    console.log(`Answer:      ${result.text}`);
    console.log(`Model calls: ${finalState.modelCalls} (across all runs)`);
    console.log(`Tool runs:   ${finalState.toolRuns} (across all runs)`);

    if (finalState.runCount > 1) {
      // The actual proof. The turn needs two model calls and one tool call; if
      // recovery replayed history correctly, the work completed before the
      // crash was not redone, so the tool ran exactly once across both runs.
      const toolRedone = finalState.toolRuns > 1;
      console.log(
        toolRedone
          ? '\n❌ checkFlightStatus ran more than once — completed work was recomputed.'
          : '\n✅ Recovery confirmed: checkFlightStatus ran exactly once across ' +
              'both runs.\n   Its result was replayed from Catalyst workflow ' +
              'history, not recomputed.'
      );
    }
    console.log('='.repeat(60));
  } finally {
    await runner.shutdown();
  }
}

await main();
