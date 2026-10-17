/**
 * Crash Recovery Test: proves the agent survives its process being killed
 * mid-turn. This is the whole point of running an agent on Dapr Workflows via
 * Catalyst, so it is worth demonstrating rather than taking on faith.
 *
 * Start it with:
 *
 *   diagrid dev run -f dev-crash-test.yaml --approve
 *
 * It serves the same crash-demo contract as every other agent quickstart in
 * this repo, on APP_PORT (default 8001):
 *
 *   GET  /            health check, answers once the runner has started
 *   POST /crash/run   { id, prompt, kill_after_seconds? } runs one turn under
 *                     the workflow instance ID you choose and waits for it
 *   POST /crash/kill  kills this process outright, like a real crash
 *
 * One turn is three steps, each its own checkpointed Dapr activity:
 *
 *   1. Model call 1 asks for the `checkIncidentStatus` tool.
 *   2. `checkIncidentStatus` runs, and deliberately takes CRASH_DELAY_SECONDS.
 *      This is the window the crash lands in.
 *   3. Model call 2 turns the tool's result into the answer.
 *
 * Restart with the same command after the crash and Catalyst hands the run
 * back: the interrupted tool runs again, then model call 2. Model call 1 does
 * not, and that absence is the proof that its recorded result was replayed from
 * Catalyst's workflow history instead of being paid for twice. See README.md
 * for the full walkthrough.
 */

import { writeSync } from 'node:fs';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { setTimeout as sleep } from 'node:timers/promises';

import { Agent } from '@mastra/core/agent';
import { createTool } from '@mastra/core/tools';
import {
  DaprWorkflowAgentRunner,
  WorkflowTimeoutError,
  type InvokeModelInput,
} from '@diagrid/agent-mastra';
import { z } from 'zod';

import { describeModel, resolveModel } from './model';

const APP_PORT = Number(process.env['APP_PORT'] ?? '8001');

// The wait budget for the blocking POST /crash/run. Kept comfortably above step
// 2's default 10s so the first call is still blocked when you kill the app.
// Overridable through CRASH_WAIT_SECONDS, which is how an automated run exercises
// the 202 branch without waiting two minutes for it.
const CRASH_WAIT_SECONDS = Number(process.env['CRASH_WAIT_SECONDS'] ?? '120');

const DEFAULT_PROMPT = 'What is the status of incident INC-4471?';

/**
 * Seconds into step 2's own run at which the app should kill itself, or null
 * when nothing is asked for. Set by noteSelfKill below, then read by
 * checkIncidentStatus both to compose its log line (which has to name the wait
 * the reader actually gets) and to start the timer.
 *
 * A plain module-level value is enough. One armed kill takes the whole process
 * down, so there is nothing to key by run, and the fresh process after the
 * restart starts at null again. That reset is what makes the replay safe: the
 * resumed step 2 re-runs from the start, and it must not arm a second kill when
 * it does.
 *
 * `runId` is only there so the request that recorded the value can clear it
 * again if its run ends without step 2 ever starting (a failed model call, say).
 * Without that, the value would sit here until the next scheduling call and
 * could be consumed by some other run's step 2.
 */
let selfKill: { runId: string; seconds: number } | null = null;

/**
 * Record how far into step 2 this process should kill itself, for step 2 to act
 * on when it actually runs. Recording only: no timer starts here. Pass null to
 * disarm.
 *
 * The timer starts inside the tool rather than at the request, for two reasons.
 * The tool is a durable activity, so it is the one thing that runs on a genuine
 * first execution and not on an attach: an attach to a finished run replays the
 * recorded result instead of re-invoking it. And it starts the clock after model
 * call 1, so the budget is measured against step 2's own sleep instead of having
 * to cover a model round trip of unknown length ahead of it.
 */
function noteSelfKill(runId: string, seconds: number | null): void {
  selfKill = seconds === null ? null : { runId, seconds };
}

/**
 * Write one log line and exit with code 1, with no graceful shutdown.
 *
 * `process.exit`, the same call the earlier version of this demo crashed with:
 * it runs no `finally`, no `runner.shutdown()` and no pending I/O, so the
 * activity in flight never completes and Catalyst has to recover the instance
 * rather than retry a failure. The line goes out through a synchronous write
 * because stdout is a pipe under `diagrid dev run`, and on macOS a pipe write
 * from `console.log` is asynchronous, so it could be lost to the exit right
 * behind it.
 */
function hardExit(line: string): never {
  try {
    writeSync(process.stdout.fd, `${line}\n`);
  } catch {
    // A full pipe must not stop the crash; the line is a courtesy, the exit is the point.
  }
  process.exit(1);
}

/**
 * Kill this process `seconds` from now.
 *
 * What lets the demo run in two terminals instead of three. POST /crash/run
 * blocks for the length of step 2, so the shell that starts a run cannot also
 * stop the app, and the kill has always needed a terminal of its own. Arming it
 * removes that terminal AND the race: the crash lands at a known point inside
 * the window rather than wherever the reader's reflexes put it.
 *
 * `unref()` so the timer can never be the thing holding the process open.
 */
function armSelfKill(seconds: number): void {
  setTimeout(() => {
    hardExit(
      `>>> crash: killing this process ${seconds}s into the run, as asked by kill_after_seconds`
    );
  }, seconds * 1000).unref();
}

// Step 2. The tool is the slow step ON PURPOSE. Model call 1 finishes and
// Catalyst records it before this starts, so the crash lands between two known
// points. After the restart, `>>> Model call 1` must NOT appear again: that
// absence is what proves the replay used the recorded result. Make model call 1
// the slow part instead and the crash lands before anything has completed, the
// run restarts from nothing, and the demo proves nothing at all.
const checkIncidentStatus = createTool({
  id: 'checkIncidentStatus',
  description: 'Check the status of an ongoing incident by its incident ID.',
  inputSchema: z.object({ incidentId: z.string().describe('e.g. INC-4471') }),
  outputSchema: z.object({
    incidentId: z.string(),
    status: z.string(),
    assignee: z.string(),
  }),
  execute: async ({ incidentId }) => {
    // The delay is what makes the crash aimable. Without it the tool finishes in
    // milliseconds and there is no window for POST /crash/kill to land in.
    const delay = Number(process.env['CRASH_DELAY_SECONDS'] ?? '10');
    // Read AND clear, so one recorded request arms exactly one execution. Node
    // runs this on one thread, so the pair cannot interleave with a request.
    const armed = selfKill?.seconds ?? null;
    selfKill = null;
    // Two messages, because the reader's next move differs. Un-armed, the window
    // is theirs to aim at and they have to crash the app themselves. Armed, the
    // app does that for them at a known point, so the instruction would be wrong.
    if (armed !== null) {
      console.log(
        `>>> STEP 2 checkIncidentStatus: Checking ${incidentId} over ~${delay}s, ` +
          `but this process kills itself ${armed}s into the run, as asked by kill_after_seconds. ` +
          'It resumes on restart.'
      );
      // Armed here, where step 2 actually starts, and not at the request. See
      // noteSelfKill for why.
      armSelfKill(armed);
    } else {
      console.log(
        `>>> STEP 2 checkIncidentStatus: Checking ${incidentId} over ~${delay}s. ` +
          'KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.'
      );
    }
    await sleep(delay * 1000);
    console.log(`>>> STEP 2 COMPLETE: ${incidentId} is mitigated, monitoring for recurrence`);
    return {
      incidentId,
      status: 'mitigated, monitoring for recurrence',
      assignee: 'on-call SRE',
    };
  },
});

const model = resolveModel();
console.log(`Model: ${describeModel(model)}`);

const agent = new Agent({
  id: 'sre-agent',
  name: 'sre-agent',
  instructions:
    'You look up incident statuses. Always use the checkIncidentStatus ' +
    'tool to answer, then report the status in one short sentence.',
  model,
  tools: { checkIncidentStatus },
});

// Same runner `name` as main.ts. That is what the workflow name and the
// Catalyst agent registry entry are keyed on, so this demo's crash-recovery run
// and its happy-path run show up under the one "sre-agent" agent in Catalyst
// rather than two unrelated identities.
//
// invokeTimeoutSeconds is the budget runner.waitFor() uses, so CRASH_WAIT_SECONDS
// lands here: past it, waitFor throws WorkflowTimeoutError and /crash/run
// answers 202 instead of blocking further.
const runner = new DaprWorkflowAgentRunner({
  agent,
  name: 'sre-agent',
  maxIterations: 10,
  invokeTimeoutSeconds: CRASH_WAIT_SECONDS,
});

// Wrap the runner's own invoker to log each model call. `setModelInvoker` is the
// supported hook. The number comes from the workflow's own iteration index, not
// a counter in this process: a counter would restart at 1 after the crash and
// print `>>> Model call 1` for what is really the second call, which is exactly
// the line the replay proof says must not reappear.
const realInvoker = runner.modelInvoker;
runner.setModelInvoker((input: InvokeModelInput) => {
  console.log(`>>> Model call ${input.iteration + 1} for run ${input.threadId}`);
  return realInvoker(input);
});

interface CrashResponse {
  id: unknown;
  result: string | null;
  message: string | null;
}

/** The one response shape every crash demo in this repo returns. All three
 * fields are always present: a 200 carries `result`, while a 400, a 202 and a
 * 500 carry `message`. */
function crashResponse(
  res: ServerResponse,
  status: number,
  body: CrashResponse
): void {
  sendJson(res, status, body);
}

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

async function readJson(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(chunk as Buffer);
  }
  const text = Buffer.concat(chunks).toString('utf8');
  return text.trim() === '' ? {} : JSON.parse(text);
}

// Run one agent turn under a workflow instance ID you choose, and block until it
// finishes.
// POST /crash/run
// Body: { "id": "inc-4471", "prompt": "What is the status of incident INC-4471?", "kill_after_seconds": 8 }
// Returns: 200 with the agent's answer, or 202 with the ID if the wait budget elapses
//
// `kill_after_seconds` is optional. Send it and the app crashes itself that many
// seconds into step 2, so the whole demo runs in two terminals with no window to
// aim at; leave it out and you crash the app yourself with POST /crash/kill.
async function crashRun(req: IncomingMessage, res: ServerResponse): Promise<void> {
  let body: Record<string, unknown>;
  try {
    const parsed = await readJson(req);
    body = typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    crashResponse(res, 400, { id: null, result: null, message: 'body must be JSON' });
    return;
  }

  const rawId = body['id'];
  if (typeof rawId !== 'string' || rawId.trim() === '') {
    crashResponse(res, 400, { id: rawId ?? null, result: null, message: 'id is required' });
    return;
  }
  const id = rawId;
  const prompt = typeof body['prompt'] === 'string' ? body['prompt'] : DEFAULT_PROMPT;
  // Anything but a positive whole number arms nothing, without an error: 0, a
  // negative, a string or a fraction all mean "crash it yourself".
  const killAfter = body['kill_after_seconds'];
  const killAfterSeconds =
    typeof killAfter === 'number' && Number.isInteger(killAfter) && killAfter > 0
      ? killAfter
      : null;

  let reachedTerminalState = false;
  try {
    // getWorkflowStatus answers undefined for an ID Catalyst has never seen, so it
    // is the existence check. Payloads are not needed to tell "exists" apart.
    const existing = await runner.getWorkflowStatus(id, false);
    if (existing === undefined) {
      // schedule(), not invoke(): invoke() is schedule() followed by waitFor(),
      // and the self-kill has to be recorded between the two. The wait below is
      // the same one a re-issued request uses.
      await runner.schedule(
        { prompt, threadId: id, maxIterations: 10, messages: [] },
        { workflowId: id }
      );
      // Recorded here and nowhere else: only on the branch that actually
      // scheduled a run, so an attaching call cannot even leave a note behind.
      // Recorded on every scheduling call, and one without the field records
      // null, which disarms: a value left set by an earlier call would otherwise
      // be consumed by this run's step 2 and kill an app that never asked for it.
      noteSelfKill(id, killAfterSeconds);
    } else {
      console.log(`>>> Attaching to the existing run ${id} instead of starting a second one`);
    }

    // Asynchronous all the way down (a gRPC call raced against a timer), so the
    // event loop stays free and POST /crash/kill can still be answered.
    const output = await runner.waitFor(id);
    reachedTerminalState = true;

    // A turn that failed inside the agent loop (a model error, maxIterations)
    // still ends the Dapr workflow as COMPLETED, with the failure in the output's
    // own status. So read that status before trusting `text`.
    if (output.status !== 'completed') {
      const message = `run ${id} ended as ${output.status}` + (output.error ? `: ${output.error}` : '');
      console.log(`>>> Crash-recovery run ${id} ended as ${output.status}`);
      crashResponse(res, 500, { id, result: null, message });
      return;
    }
    // `result` carries the agent's final answer text, matching the `result`
    // field of the other crash demos. The transcript and iteration count stay
    // in the workflow's recorded output in Catalyst.
    crashResponse(res, 200, { id, result: output.text, message: null });
  } catch (error) {
    if (error instanceof WorkflowTimeoutError) {
      // Not a failure: the run is still going. Re-issue the same request with the
      // same ID to attach and collect the result.
      crashResponse(res, 202, {
        id,
        result: null,
        message: `still running as ${id}, re-issue POST /crash/run with the same id to attach`,
      });
      return;
    }
    // waitFor throws for a FAILED or TERMINATED workflow too, naming the status.
    reachedTerminalState = true;
    const message = error instanceof Error ? error.message : String(error);
    console.log(`>>> Error running the crash-recovery run ${id}: ${message}`);
    crashResponse(res, 500, { id, result: null, message });
  } finally {
    // The run is over (or never got going), so a kill it recorded but whose step
    // 2 never started must not outlive it.
    if (reachedTerminalState && selfKill?.runId === id) {
      selfKill = null;
    }
  }
}

// Simulate a crash: kill this process outright. Demo only.
// POST /crash/kill
// Returns: nothing. The process is gone before a response can be written, so the
// caller sees a connection reset.
function crashKill(): void {
  hardExit('>>> /crash/kill: killing this process to simulate a worker crash');
}

const server = createServer((req, res) => {
  // One access-log line per request, the way uvicorn prints them for the Python
  // demos. It is also how Catalyst's first probe through the dev tunnel
  // (GET /dapr/config) becomes visible in the app log.
  res.on('finish', () => console.log(`${req.method} ${req.url} ${res.statusCode}`));

  const path = (req.url ?? '/').split('?')[0];
  if (req.method === 'GET' && path === '/') {
    // Health check. The server only listens once the runner has started, so a
    // 200 here means the workflow runtime is up, not merely that the port is open.
    sendJson(res, 200, { message: 'Health check passed. Everything is running smoothly!' });
  } else if (req.method === 'POST' && path === '/crash/run') {
    void crashRun(req, res);
  } else if (req.method === 'POST' && path === '/crash/kill') {
    crashKill();
  } else {
    sendJson(res, 404, { message: 'Not Found' });
  }
});

await runner.start();
// The runtime connects to Catalyst in the background. Give it a moment before
// accepting requests, so the first one cannot arrive at an unregistered worker.
await sleep(1000);
console.log('Runner started, ready to accept requests');
server.listen(APP_PORT, '0.0.0.0', () => {
  console.log(`Crash demo listening on http://0.0.0.0:${APP_PORT}`);
});
