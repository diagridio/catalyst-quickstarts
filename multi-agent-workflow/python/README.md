# Customer Support Multi-Agent Workflow Quickstart

This quickstart demonstrates how to build a durable, multi-agent workflow using Dapr Agents and Workflows.
The workflow acts as a customer support system that triages support tickets and provides troubleshooting resolutions through two cooperating AI agents.

## What This Quickstart Demonstrates

* **Durable Execution**: Workflow state persisted using Dapr Workflows
* **Multi-Agent Orchestration**: Triage and expert agents working in sequence
* **Conversation Memory**: Agents maintain context across executions
* **Tool Integration**: Hardcoded entitlement and environment lookup tools
* **REST API**: Trigger workflows via a single HTTP endpoint

## Prerequisites

Before you begin, ensure you have:

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. [An OpenAI API key](https://platform.openai.com/api-keys)

### Set up your local environment

Navigate to the Python Directory

```bash
cd multi-agent-workflow/python
```

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

Deploy the workflow app to Catalyst with managed infrastructure:

```bash
diagrid dev run -f dev-python-multi-agent-workflow.yaml --project dev-python-multi-agent-workflow
```

This starts:
- REST endpoint on port 5001
- Durable workflow engine with state persistence
- Two state stores: execution state and memory state
- OpenAI conversation component

### 2. Trigger a Workflow

From another terminal, trigger the workflow via REST API:

```bash
curl -i -X POST http://localhost:5001/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"customer": "Alice", "issue": "My Dapr system fails to start in production."}'
```

The workflow will:

1. Run the **Triage Agent** (check entitlement and urgency)
2. Run the **Expert Agent** (retrieve environment info and generate a resolution)
3. Return a customer-ready response with the proposed fix
 
---

## Monitoring in Catalyst

### Check Workflow Execution

* Navigate to Catalyst dashboard → **Workflows**
* View real-time execution progress and detailed logs
* Inspect the sequential flow from triage to expert resolution

### Examine State Storage

The workflow uses two state stores:

1. **statestore** - Execution state (workflow progress, retries)

   * Go to Components → Key-Value Store → `statestore`
   * View workflow execution data

2. **memory-state** - Agent conversation memory

   * See agent reasoning context and history
   * Observe how memory persists across runs

### View Application Architecture

* In Catalyst dashboard → **Application Map**
* See the `customer-support-workflow` service and its dependencies
* Observe connections to state stores and OpenAI component

---

## How It Works

The workflow combines several Dapr building blocks:

1. **Dapr Workflows**: Provides durable execution with state persistence
2. **Agents**: Implement reasoning, tool usage, and contextual understanding
3. **State Management**: Stores execution state and agent memory
4. **Tools**:
   * `check_entitlement`: Returns `True` for “Alice”, `False` otherwise
   * `get_customer_environment`: Returns mock environment details for the customer

The workflow:

* Receives support requests via REST API
* Uses the **Triage Agent** to validate entitlement and urgency
* Uses the **Expert Agent** to analyze environment and generate a resolution
* Returns a formatted message to the customer

---

## Testing with VS Code REST Client

If you use VS Code with the REST Client extension, open `test.rest` and click **“Send Request”** above any request to test the API.
