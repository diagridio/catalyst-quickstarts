# Diagrid Quickstarts

Get started with [Diagrid](https://diagrid.ws/catalyst-quickstarts) by following these step-by-step quickstarts. Choose a quickstart based on what you want to build.

## Agent Quickstarts

Learn how to build AI-powered durable agents using Diagrid. Create intelligent, stateful agents that maintain conversation memory and execution state across restarts.

### Agent Frameworks

Diagrid works with the following agent frameworks:

| Framework | Description |
|-----------|-------------|
| [Dapr Agents](agents/dapr-agents/) | Native Dapr agent framework with built-in durability, state, and pub/sub for multi-agent orchestration |
| [Mastra](agents/mastra/) | TypeScript agent framework with tool calling, made durable with Diagrid |
| [CrewAI](agents/crewai/) | Multi-agent crews with role-based collaboration, made durable with Diagrid |
| [LangGraph](agents/langgraph/) | Graph-based agent orchestration with conditional routing, made durable with Diagrid |
| [LangGraph.js](agents/langgraphjs/) | Graph-based agent orchestration for TypeScript, with the end user's verified identity propagated to its tools by Diagrid |
| [Strands](agents/strands/) | Model-driven agent framework from AWS with tool use, made durable with Diagrid |
| [Microsoft Agent Framework](agents/microsoft-dotnet/) | Enterprise agent framework from Microsoft, made durable with Diagrid |
| [Spring AI](agents/spring-ai/) | Spring's AI framework for Java, made durable with Diagrid |
| [Google ADK](agents/adk/) | Google's Agent Development Kit, running on OpenAI through LiteLLM, made durable with Diagrid |
| [OpenAI Agents](agents/openai-agents/) | Function tools and agent handoffs from OpenAI, made durable with Diagrid |
| [Pydantic AI](agents/pydantic-ai/) | Type-safe agent framework with structured outputs, made durable with Diagrid |
| [Deep Agents](agents/deepagents/) | Type-safe agent harness with conditional routing, made durable with Diagrid |
| [Claude Agents](agents/claude-agents/) | Anthropic's Claude Agent SDK with tool calling, made durable with Diagrid |
| [Goose](agents/goose/) | The open-source Goose agent with its built-in developer tools, run unmodified from Rust and made durable with Diagrid |

## MCP Quickstarts

Learn how to register MCP (Model Context Protocol) servers with Diagrid and secure them.

| Quickstart | Description | Path |
|------------|--------------|------|
| MCP Authentication & Authorization | Register a local MCP server, authenticate Diagrid to it, and authorize specific tool calls | [mcp-auth/python](mcp-auth/python/) |

## Workflow Quickstart

Learn how to build stateful, long-running, reliable workflows using the Dapr Workflow API. Choose your preferred language to get started.

| Language | Path |
|----------|------|
| C# | [workflow/csharp](workflow/csharp/) |
| Java | [workflow/java](workflow/java/) |
| JavaScript | [workflow/javascript](workflow/javascript/) |
| Python | [workflow/python](workflow/python/) |

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

## Documentation

For full documentation, visit the [Diagrid Quickstarts docs](https://diagrid.ws/catalyst-quickstarts).
