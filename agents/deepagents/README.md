# Deep Agents - Transportation Planner Agent

This agent plays the role of **Transportation Planner**, responsible for finding transportation options based on event type and guest count.

## Role

- **Agent**: `deepagents-agent`
- **Port**: 8009
- **Subscribe topic**: `transportation.requests`
- **Publish topic**: `transportation.results`

## Tools

- `search_transportation(event_type, guest_count)` — Searches for transportation options matching the given event type and guest count.

## Setup

### Prerequisites

- Python 3.12+
- [Dapr CLI](https://docs.dapr.io/getting-started/install-dapr-cli/)
- Redis running locally (for state store and pub/sub)
### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider supported by Deep Agents.

```bash
export OPENAI_API_KEY="your-key-here"
```

### Run locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=<your-key>
dapr run -f dev-python-deepagents.yaml
```

### Test

```bash
curl -X POST http://localhost:8888/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find transportation for a corporate gala with 200 guests"}'
```

## Crash Recovery Test

The `crash_test.py` file demonstrates durable crash recovery — a capability powered by Dapr Workflows. It defines 3 tools where tool 2 crashes with `os._exit(1)`:

1. **step_one_search** — searches for transportation options (completes successfully)
2. **step_two_compare** — compares options (crashes before completing)
3. **step_three_confirm** — confirms the selection

### First run — trigger and crash

```bash
diagrid dev run -f dev-crash-test.yaml
```

Wait for `Runner started — ready to accept requests`, then from another terminal:

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find transportation for a corporate gala"}'
```

You'll see tool 1 complete and the process crash at tool 2.

### Fix and resume

Open `crash_test.py` and comment out the crash line:

```python
# os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
```

Restart the application:

```bash
diagrid dev run -f dev-crash-test.yaml
```

The workflow **resumes from tool 2** — tool 1 is not re-executed. The Dapr workflow engine replays the saved result from Catalyst instead of re-running the tool.

## Sub-Agent Workflows

The `subagent_workflows.py` file demonstrates a supervisor/sub-agent pattern where a supervisor agent orchestrates two sub-agents (researcher and analyst) that each run as independent Dapr workflow-backed processes communicating over the Agent Protocol.

- **Researcher** — searches the web for information on a topic and returns a summary
- **Analyst** — takes research findings and produces a structured analysis report
- **Supervisor** — orchestrates the researcher and analyst sequentially, then synthesizes their results

### Run

```bash
diagrid dev run -f dev-subagent-workflows.yaml
```

This starts three processes:
- `deepagents-researcher` on port 8001
- `deepagents-analyst` on port 8002
- `deepagents-supervisor` which delegates to the other two

The supervisor automatically runs the research and analysis pipeline on startup and prints the final synthesized response.
