# Agent-Orchestrated Customer Support Quickstart

This quickstart demonstrates how to build an multi-agent-orchestrator multi-agent system using Dapr Agents. Unlike the workflow-based multi-agent example, here an **orchestrator agent** (powered by an LLM) dynamically coordinates the triage and expert agents rather than following a predefined workflow sequence.

## What This Quickstart Demonstrates

* **Agent-Based Orchestration**: An LLM-powered orchestrator agent decides which agents to delegate to
* **Dynamic Coordination**: The orchestrator reasons about when to call triage vs expert agents
* **Durable Execution**: All agent state persisted using Dapr Workflows
* **Tool Integration**: Entitlement checking and environment lookup tools
* **PubSub Communication**: Agents communicate via Dapr pub/sub topics
* **Agent Registry**: Agents register themselves for discovery by the orchestrator

## Prerequisites

Before you begin, ensure you have:

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.11+](https://www.python.org/downloads/)
3. [An OpenAI API key](https://platform.openai.com/api-keys)

### Set up your local environment

Navigate to the multi-agent-orchestrator directory:

```bash
cd dapr-agents/multi-agent-orchestrator
```

```bash
# Install dependencies
uv sync
```

## Configuration

### OpenAI API Key

Locate the `agent-llm-provider.yaml` file in the `resources` folder and update it with your OpenAI API key:

```yaml
metadata:
  - name: key
    value: "YOUR_OPENAI_API_KEY"
  - name: model
    value: gpt-4.1-2025-04-14
```

## Running the Quickstart

### 1. Deploy and Run the Agents

Login to Diagrid Catalyst using the following command:

```bash
diagrid login
```

Deploy the agents to Catalyst with managed infrastructure:

```bash
diagrid dev run -f dapr.yaml --project multi-agent-orchestrator-quickstart --approve
```

This starts:
- **Orchestrator agent** on port 8001 — LLM-powered coordinator
- **Triage agent** on port 8002 — checks entitlement and assesses urgency
- **Expert agent** on port 8003 — retrieves environment info and proposes resolutions
- State stores: `agent-workflow` (execution state), `agent-registry` (agent discovery)
- PubSub component for inter-agent communication
- OpenAI conversation component (`agent-llm-provider`)

### 2. Trigger the Orchestrator

From another terminal, trigger the orchestrator agent via REST API:

```bash
curl -i -X POST http://localhost:8001/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Customer: Alice. Issue: My Dapr system fails to start in production."}'
```

The orchestrator agent will:

1. Reason about the task and decide to delegate to the **Triage Agent**
2. The triage agent checks Alice's entitlement and assesses urgency
3. The orchestrator receives the triage result and delegates to the **Expert Agent**
4. The expert agent retrieves environment info and proposes a resolution
5. The orchestrator synthesizes results into a customer-friendly response

### Key Difference from Multi-Agent Workflow

In the **multi-agent workflow** example, the sequence (triage then expert) is hardcoded in a workflow definition. In this **multi-agent-orchestrator** example, the orchestrator agent uses an LLM to dynamically decide which agents to call and in what order. This makes the system more flexible — the orchestrator can skip agents, call them in different orders, or retry based on results.

---

## Monitoring in Catalyst

### Check Workflow Execution

* Navigate to Catalyst dashboard → **Workflows**
* View real-time execution progress and detailed logs
* Inspect how the orchestrator delegates to child agents

### Examine State Storage

The agents use shared state stores:

1. **agent-workflow** — Execution state for all agents (with key prefixes for isolation)
2. **agent-registry** — Agent discovery and metadata

### View Application Architecture

* In Catalyst dashboard → **Application Map**
* See the `support-multi-agent-orchestrator`, `triage-agent`, and `expert-agent` services
* Observe pub/sub connections and state store dependencies

---

## How It Works

The system combines several Dapr building blocks:

1. **Dapr Workflows**: Provides durable execution with state persistence for all agents
2. **PubSub**: Enables asynchronous communication between agents
3. **State Management**: Shared stores with key prefixes for isolation
4. **Agent Registry**: Allows the orchestrator to discover available agents
5. **Tools**:
   * `check_entitlement`: Returns `True` for "Alice", `False` otherwise
   * `get_customer_environment`: Returns mock environment details for the customer

The orchestrator agent:
* Receives tasks via REST API
* Uses LLM reasoning to decide which agents to delegate to
* Coordinates triage and expert agents via pub/sub
* Synthesizes final results into a customer response

---

## Testing with VS Code REST Client

If you use VS Code with the REST Client extension, open `test.rest` and click **"Send Request"** above any request to test the API.
