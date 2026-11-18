# Catalyst Quickstarts

[![E2E quickstart tests](https://github.com/diagridio/catalyst-quickstarts/actions/workflows/e2e-quickstarts.yml/badge.svg)](https://github.com/diagridio/catalyst-quickstarts/actions/workflows/e2e-quickstarts.yml)

[Diagrid](https://diagrid.ws/catalyst-quickstarts) is durable execution for AI agents and workflows, built on Dapr Workflow. An agent or workflow running on Diagrid keeps its state and picks up where it left off after a crash, restart or redeploy, instead of starting over.

These step-by-step quickstarts show how. Choose one based on what you want to build.

## Prerequisites

Each quickstart's README lists the language toolchain it needs. All of them need:

1. **Install the Diagrid CLI.** Follow the [install guide](https://docs.diagrid.io/getting-started/install-cli), or on macOS and Linux run:

   ```bash
   curl -sL https://downloads.diagrid.io/cli/install.sh | bash
   ```

2. **Sign up for Diagrid** at [catalyst.diagrid.io](https://catalyst.diagrid.io/). Diagrid has a permanent free tier.

3. **Log in** from your terminal:

   ```bash
   diagrid login
   ```

## Workflow Quickstart

Learn how to build stateful, long-running, reliable workflows using the Dapr Workflow API. Choose your preferred language to get started.

| Language | Path |
|----------|------|
| C# | [workflow/csharp](workflow/csharp/) |
| Java | [workflow/java](workflow/java/) |
| JavaScript | [workflow/javascript](workflow/javascript/) |
| Python | [workflow/python](workflow/python/) |

## Agent Quickstarts

Learn how to build AI-powered durable agents using Diagrid. Create intelligent, stateful agents that maintain conversation memory and execution state across restarts.

### Agent Frameworks

Diagrid works with the following agent frameworks:

| Framework | Language | Description | SDK |
|-----------|----------|-------------|-----|
| [Dapr Agents](agents/dapr-agents/) | Python | Native Dapr agent framework with built-in durability, state, and pub/sub for multi-agent orchestration | [dapr-agents](https://github.com/dapr/dapr-agents) |
| [Mastra](agents/mastra/) | TypeScript | TypeScript agent framework with tool calling, made durable with Diagrid | [typescript-ai](https://github.com/diagridio/typescript-ai) |
| [CrewAI](agents/crewai/) | Python | Multi-agent crews with role-based collaboration, made durable with Diagrid | [python-ai](https://github.com/diagridio/python-ai) |
| [LangGraph](agents/langgraph/) | Python | Graph-based agent orchestration with conditional routing, made durable with Diagrid | [python-ai](https://github.com/diagridio/python-ai) |
| [LangGraph.js](agents/langgraphjs/) | TypeScript | Graph-based agent orchestration for TypeScript, with the end user's verified identity propagated to its tools by Diagrid | [typescript-ai](https://github.com/diagridio/typescript-ai) |
| [LangChainGo](agents/langchaingo/) | Go | LangChain for Go, with the end user's verified identity propagated to its tools by Diagrid | [go-ai](https://github.com/diagridio/go-ai) |
| [Strands](agents/strands/) | Python | Model-driven agent framework from AWS with tool use, made durable with Diagrid | [python-ai](https://github.com/diagridio/python-ai) |
| [Microsoft Agent Framework](agents/microsoft-dotnet/) | .NET | Enterprise agent framework from Microsoft, made durable with Diagrid | [dotnet-ai](https://github.com/diagridio/dotnet-ai) |
| [Spring AI](agents/spring-ai/) | Java | Spring's AI framework for Java, made durable with Diagrid | [java-ai](https://github.com/diagridio/java-ai) |
| [Google ADK](agents/adk/) | Python | Google's Agent Development Kit, running on OpenAI through LiteLLM, made durable with Diagrid | [python-ai](https://github.com/diagridio/python-ai) |
| [OpenAI Agents](agents/openai-agents/) | Python | Function tools and agent handoffs from OpenAI, made durable with Diagrid | [python-ai](https://github.com/diagridio/python-ai) |
| [Pydantic AI](agents/pydantic-ai/) | Python | Type-safe agent framework with structured outputs, made durable with Diagrid | [python-ai](https://github.com/diagridio/python-ai) |
| [Deep Agents](agents/deepagents/) | Python | Type-safe agent harness with conditional routing, made durable with Diagrid | [python-ai](https://github.com/diagridio/python-ai) |
| [Claude Agents](agents/claude-agents/) | Python | Anthropic's Claude Agent SDK with tool calling, made durable with Diagrid | [python-ai](https://github.com/diagridio/python-ai) |
| [Goose](agents/goose/) | Rust | The open-source Goose agent with its built-in developer tools, run unmodified from Rust and made durable with Diagrid | [rust-ai](https://github.com/diagridio/rust-ai) |

The top-level [dapr-agents](dapr-agents/) directory holds three more Dapr Agents quickstarts: a single [durable agent](dapr-agents/durable-agent/), a [multi-agent workflow](dapr-agents/multi-agent-workflow/) where a predefined workflow coordinates the agents, and a [multi-agent orchestrator](dapr-agents/multi-agent-orchestrator/) where an LLM decides which agent to delegate to.

## MCP Quickstarts

Learn how to register MCP (Model Context Protocol) servers with Diagrid and secure them.

| Quickstart | Description | Path |
|------------|--------------|------|
| MCP Authentication & Authorization | Register a local MCP server, authenticate Diagrid to it, and authorize specific tool calls | [mcp-auth/python](mcp-auth/python/) |

## Dapr API Quickstarts

Learn how to use Dapr's distributed application APIs with Diagrid. Choose an API and your preferred language to get started.

### Pub/Sub

Send and receive messages using Diagrid Pub/Sub Service.

| Language | Path |
|----------|------|
| C# | [pubsub/csharp](pubsub/csharp/) |
| Java | [pubsub/java](pubsub/java/) |
| JavaScript | [pubsub/javascript](pubsub/javascript/) |
| Python | [pubsub/python](pubsub/python/) |

### State Management

Manage key-value pairs using Diagrid KV Store.

| Language | Path |
|----------|------|
| C# | [state/csharp](state/csharp/) |
| Java | [state/java](state/java/) |
| JavaScript | [state/javascript](state/javascript/) |
| Python | [state/python](state/python/) |

### Service Invocation

Implement the request/reply pattern.

| Language | Path |
|----------|------|
| C# | [invocation/csharp](invocation/csharp/) |
| Java | [invocation/java](invocation/java/) |
| JavaScript | [invocation/javascript](invocation/javascript/) |
| Python | [invocation/python](invocation/python/) |

## Repository tools

[tools/qs-tester](tools/qs-tester/) holds the end-to-end tests that run each quickstart's documented commands against Diagrid, and the checks that keep each README in sync with its code. You don't need it to run a quickstart.

## Documentation

For full documentation, visit the [Diagrid quickstarts docs](https://diagrid.ws/catalyst-quickstarts).
