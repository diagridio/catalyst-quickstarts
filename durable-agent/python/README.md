# Durable Agent Quickstart

This quickstart demonstrates how to build a durable agent using Dapr Agents and Workflows. The agent acts as a travel assistant that can search for flights, maintain conversation memory, and persist state across restarts.

## What This Quickstart Demonstrates

- **Durable Execution**: Agent state persisted using Dapr Workflows
- **Tool Integration**: Flight search with simulated external API calls (50% chance of 20-second delay)
- **State Management**: Multiple state stores for execution, memory, and agent registry
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Conversation Memory**: Maintain context across multiple interactions

## Prerequisites

Before you begin, ensure you have:

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. [An OpenAI API key](https://platform.openai.com/api-keys)

### Set up your local environment

Navigate to the Python Directory

```bash
cd durable-agent/python
```

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment 
source venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### OpenAI API Key

Locate the `openai.yaml` file in the `resources` folder and update it with your OpenAI API key:

```yaml
metadata:
  - name: key
    value: "YOUR_OPENAI_API_KEY"
```

## Running the Quickstart

### 1. Deploy and Run the Agent

Login to Diagrid Catalyst using the following command:

```bash
diagrid login
```

Deploy the agent to Catalyst with managed infrastructure:

```bash
diagrid dev run -f dev-python-durable-agent.yaml --project dev-python-durable-agent

```

This starts:
- REST endpoint on port 5001
- Durable workflow engine with state persistence
- Three state stores: execution state, memory state, and registry state
- OpenAI conversation component

### 2. Trigger a Workflow

Confirm from the logs that "Travel Assistant Agent is running".
From another terminal, trigger the Agent via REST API:

```bash
curl -i -X POST http://localhost:5001/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find me flights and hotels to London and Amsterdam"}'
```

This should call two parallel tool call to find flights to both cities, followed by two parallel tool call to find hotels.

At a high-level, the agent will:
1. Process your flight and hotels request
2. Execute the `search_flights` tool in parallel for both cities
3. Return flight options with pricing to the LLM and plan next steps
4. Execute the `search_hotels` tool in parallel for both cities
5. At every step, persist execution state and conversation history to Catalyst
6. Return flight and hotel options 


See this agent adapting other queries and generating different workflows on-the-fly.

- Search for flights and hotels to a single destination.

```bash
curl -i -X POST http://localhost:5001/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find me flights and hotels to London"}'
```
- Search for flights only to London and Amsterdam


```bash
curl -i -X POST http://localhost:5001/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find me flights only to London and Amsterdam"}'
```

## Monitoring in Catalyst

### Check Workflow Execution

- Navigate to Catalyst dashboard → Workflows
- View real-time execution progress and detailed logs
- Inspect individual workflow steps and timing

### Examine State Storage

The agent uses three separate state stores:

1. **statestore** - Execution state (workflow progress, retries)
   - Go to Components → Key-Value Store → `statestore`
   - View workflow execution state

2. **memory-state** - Conversation memory
   - See conversation history and context
   - Track user preferences across sessions

3. **registry-state** - Agent registry
   - View registered agents and their metadata
   - Track agent discovery information

### View Application Architecture

- In Catalyst dashboard → Application Map
- See the travel-agent service and its dependencies
- Observe state store connections and workflow execution

## How It Works

The durable agent combines several Dapr building blocks:

1. **Dapr Workflows**: Provides durable execution with state persistence
2. **State Management**: Three stores for different concerns (execution, memory, registry)
3. **Conversation API**: OpenAI integration for natural language processing
4. **Actors**: Used internally by workflows for reliable state management

The agent:
- Receives task requests via REST API
- Uses AI to understand user intent
- Calls tools (like flight search) as needed
- Maintains conversation memory across interactions
- Persists execution state for reliability

## Testing with VS Code REST Client

If you use VS Code with the REST Client extension, open `test.rest` and click "Send Request" above any request to test the API.
 