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

```bash
export OPENAI_API_KEY="your-key-here"
```

### Run locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=<your-key>
dapr run -f dev-python-pydantic-ai.yaml
```

### Test

```bash
curl -X POST http://localhost:8888/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find decorations for a garden wedding at a medium venue"}'
```
