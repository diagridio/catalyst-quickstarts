# Microsoft Agent Framework (.NET) Quickstart - Event Planner

This quickstart demonstrates how to run a Microsoft Agent Framework agent as a durable Dapr Workflow using the `Diagrid.AI.Microsoft.AgentFramework` .NET package. The agent acts as an **Event Planner** with three tools that it calls in sequence — tool 2 deliberately crashes the process to demonstrate automatic recovery.

## What This Quickstart Demonstrates

- **Microsoft Agent Framework + Dapr Workflows**: Run a .NET agent with durable execution
- **OpenAI via Microsoft.Extensions.AI**: Calls OpenAI directly through the `Microsoft.Extensions.AI.OpenAI` IChatClient
- **Crash Recovery**: Tool 2 crashes the process; on restart, Catalyst resumes the workflow automatically
- **REST API**: Trigger the agent via an HTTP endpoint

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) or later
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd microsoft-dotnet

# Build the project
dotnet build
```

### Set your API key

**macOS/Linux (bash/zsh):**

```bash
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login
diagrid dev run -f dev-dotnet-agent.yaml --project dotnet-agent-qs --approve
```

### 2. Trigger the Agent

From another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:5050/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find a venue in Austin for a company gala"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5050/run' -ContentType 'application/json' -Body '{"prompt": "Find a venue in Austin for a company gala"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The agent will:
1. Call `step_one_search` — finds venues (completes)
2. Call `step_two_compare` — crashes before completing (process exits)

You'll see:

```text
== APP == >>> TOOL 1: Searching venues in 'Austin'...
== APP == >>> TOOL 1 COMPLETE: Found 3 venues
== APP == >>> TOOL 2: Comparing venues...
```

The process exits — this is expected.

## Crash Recovery

Open `Program.cs` and comment out the crash line:

```csharp
// Environment.Exit(1); // 💥 Comment out this line before the second run
```

Restart:

```bash
diagrid dev run -f dev-dotnet-agent.yaml --project dotnet-agent-qs --approve
```

You do **not** need to curl again — the existing workflow resumes automatically:

```text
== APP == >>> TOOL 1: Searching venues in 'Austin'...
== APP == >>> TOOL 1 COMPLETE: Found 3 venues
== APP == >>> TOOL 2: Comparing venues...
== APP == >>> TOOL 2 COMPLETE: Grand Ballroom is the best option
== APP == >>> TOOL 3: Confirming booking...
== APP == >>> TOOL 3 COMPLETE: Booking confirmed for Grand Ballroom
```

## Clean Up

Stop the running application with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete dotnet-agent-qs
```
