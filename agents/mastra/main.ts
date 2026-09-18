/**
 * SRE Agent — one durable Mastra agent turn on Dapr Workflows, via Catalyst.
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
 * `checkServiceHealth` and `calculateErrorRate` tools, then a second that turns
 * their results into an answer. Each of those steps is a separate checkpointed
 * Dapr activity.
 */

import { Agent } from '@mastra/core/agent';
import { DaprWorkflowAgentRunner } from '@diagrid/agent-mastra';

import { describeModel, resolveModel } from './model';
import { sreTools } from './tools';

const THREAD_ID = 'sre-agent-demo';

async function main(): Promise<void> {
  const model = resolveModel();
  console.log(`Model: ${describeModel(model)}`);

  const agent = new Agent({
    id: 'sre-agent',
    name: 'sre-agent',
    instructions:
      'You are a site reliability engineer. Use the checkServiceHealth tool ' +
      "to check a service's health and the calculateErrorRate tool to " +
      'compute error rates from request counts. Always use your tools ' +
      'rather than guessing.',
    model,
    tools: sreTools,
  });

  const runner = new DaprWorkflowAgentRunner({
    agent,
    name: 'sre-agent',
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
        'checkout-api had 12,400 requests in the last hour with 289 ' +
        "failures — what's the error rate, and what's the service's " +
        'current health status?',
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
