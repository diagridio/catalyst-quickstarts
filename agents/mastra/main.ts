/**
 * Trip Assistant — one durable Mastra agent turn on Dapr Workflows, via Catalyst.
 *
 * The agent's control loop runs as a Dapr Workflow: every model call and every
 * tool execution is a checkpointed activity, so killing this process mid-turn
 * and restarting it resumes from the last completed activity instead of
 * re-running the turn (and re-paying for the LLM calls). See crash_test.ts for
 * a demonstration.
 *
 * Run with Catalyst:
 *   diagrid dev run -f dev-mastra.yaml --approve
 *
 * Expect two iterations for the prompt below: one model call that requests the
 * `calculate` and `getWeather` tools, then a second that turns their results
 * into an answer. Each of those steps is a separate checkpointed Dapr activity.
 */

import { Agent } from '@mastra/core/agent';
import { DaprWorkflowAgentRunner } from '@diagrid/agent-mastra';

import { describeModel, resolveModel } from './model';
import { tripTools } from './tools';

const THREAD_ID = 'trip-assistant-demo';

async function main(): Promise<void> {
  const model = resolveModel();
  console.log(`Model: ${describeModel(model)}`);

  const agent = new Agent({
    id: 'trip-assistant',
    name: 'trip-assistant',
    instructions:
      'You help travelers plan trips. Use the calculate tool for any budget ' +
      "math and the getWeather tool to check the destination's forecast.",
    model,
    tools: tripTools,
  });

  const runner = new DaprWorkflowAgentRunner({
    agent,
    name: 'trip-assistant',
    maxIterations: 10,
  });

  // Opt in to clean shutdown on Ctrl-C. A library must not install
  // process-wide signal handlers on your behalf, so this is explicit.
  const disposeHandlers = runner.registerShutdownHandlers();

  try {
    console.log('Starting the Dapr Workflow runtime...');
    await runner.start();
    console.log(`Registered "${runner.workflowName}".\n`);

    const result = await runner.invoke({
      prompt:
        "I'm splitting a $340 dinner 4 ways in Tokyo tonight — what's my " +
        "share, and what's the weather like there?",
      threadId: THREAD_ID,
      maxIterations: 10,
      messages: [],
    });

    console.log('='.repeat(60));
    console.log(`Status:     ${result.status}`);
    console.log(`Iterations: ${result.iterations}`);
    console.log(`Answer:     ${result.text}`);
    console.log('='.repeat(60));
  } finally {
    disposeHandlers();
    await runner.shutdown();
    console.log('Runtime shut down.');
  }
}

await main();
