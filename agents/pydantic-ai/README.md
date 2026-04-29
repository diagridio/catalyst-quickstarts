# Pydantic AI - Decoration Planner Agent

This agent is part of the **Event Planning Team** quickstart scenario. It plays the role of **Decoration Planner**, responsible for finding decoration packages based on theme and venue size.

## Role

- **Agent**: `pydantic-ai-agent`
- **Port**: 8008
- **Subscribe topic**: `decorations.requests`
- **Publish topic**: `decorations.results`

## Tools

- `search_decorations(theme, venue_size)` — Searches for decoration packages matching the given theme and venue size.

## Setup

### Prerequisites

- Python 3.12+
- [Dapr CLI](https://docs.dapr.io/getting-started/install-dapr-cli/)
- Redis running locally (for state store and pub/sub)
### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider supported by Pydantic AI.

**macOS/Linux (bash/zsh):**

```bash
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

### Run locally

**macOS/Linux (bash/zsh):**

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=<your-key>
dapr run -f dev-python-pydantic-ai.yaml
```

**Windows (PowerShell):**

```powershell
pip install -r requirements.txt
$env:OPENAI_API_KEY = "<your-key>"
dapr run -f dev-python-pydantic-ai.yaml
```

### Test

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8888/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find decorations for a garden wedding at a medium venue"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8888/agent/run' -ContentType 'application/json' -Body '{"task": "Find decorations for a garden wedding at a medium venue"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

## Crash Recovery Test

The `crash_test.py` file demonstrates durable crash recovery — a capability not offered by Pydantic AI natively. It defines 3 tools where tool 2 crashes with `os._exit(1)`:

1. **step_one_search** — searches for decoration packages (completes successfully)
2. **step_two_compare** — compares packages (crashes before completing)
3. **step_three_confirm** — confirms the selection

### First run — trigger and crash

```bash
diagrid dev run -f dev-crash-test.yaml
```

Wait for `Runner started — ready to accept requests`, then from another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find decorations for a garden wedding theme"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/run' -ContentType 'application/json' -Body '{"prompt": "Find decorations for a garden wedding theme"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

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
