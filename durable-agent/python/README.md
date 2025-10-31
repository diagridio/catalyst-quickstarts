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
2. Python 3.10 or later
3. An OpenAI API key

### Set up your local environment

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment 
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### OpenAI API Key

Update the `openai.yaml` file with your OpenAI API key:

```yaml
metadata:
  - name: key
    value: "YOUR_OPENAI_API_KEY"
```
 

## Running the Quickstart

### 1. Navigate to the Python Directory

```bash
cd durable-agent/python
```

### 2. Deploy and Run the Agent

Deploy the agent to Catalyst with managed infrastructure:

```bash
diagrid dev run -f dev-python-durable-agent.yaml --project dev-python-durable-agent

```

This starts:
- REST endpoint on port 5001
- Durable workflow engine with state persistence
- Three state stores: execution state, memory state, and registry state
- OpenAI conversation component

### 3. Trigger a Workflow

From another terminal, trigger the Agent via REST API:

```bash
curl -i -X POST http://localhost:8001/start-workflow \
  -H "Content-Type: application/json" \
  -d '{"task": "I want to find flights to London and Paris"}'
```

Optionally, you can trigger the Agent over pubsub. For that you need to get Project URL and API token to publish to the pubsub broker in Catalyst


```
export DAPR_HTTP_ENDPOINT=$(diagrid project get -o json | jq -r '.status.endpoints.http.url')
export PUBLISHER_API_TOKEN=$(diagrid appid get travel-assistant-agent  -o json  | jq -r '.status.apiToken')

curl -i -X POST $DAPR_HTTP_ENDPOINT/v1.0/publish/message-pubsub/travel-assistant-agent \
      -H "Content-Type: application/json" \
      -H "cloudevent.type: TriggerAction" \
      -H "dapr-api-token: $PUBLISHER_API_TOKEN" \
      -d '{"task":"Find flights to Paris"}'
```




The agent will:
1. Process your flight request
2. Execute the `search_flights` tool 
3. Return flight options with pricing
4. Persist all state in Catalyst's managed key-value stores
  
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
 