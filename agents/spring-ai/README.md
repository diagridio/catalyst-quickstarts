# Spring AI Quickstarts

Build **durable [Spring AI](https://docs.spring.io/spring-ai/reference/) agents** on Diagrid Catalyst
using the `io.diagrid:diagrid-spring-ai-starter` package.

The key idea: an ordinary Spring AI app — a `ChatClient` plus `@Tool` beans — becomes **durable across
restarts purely by adding the starter to the classpath**. There is no durability code in your app. With
the starter present, every `ChatClient.call()` runs as a Dapr Workflow: the model turns and each tool
call execute as **checkpointed activities**, so a crash resumes from the last completed step instead of
starting over. On Catalyst the workflow state store is managed for you — no component YAML needed.

## Quickstarts

| Quickstart | What it shows |
|------------|---------------|
| [event-planner](event-planner/) | The drop-in basics: a 3-tool Event Planner agent. Tool 2 crashes the process; on restart the workflow **auto-resumes** from the checkpoint — completed steps are replayed, not re-run. Mirrors the [Microsoft Agent Framework](../microsoft-dotnet/) quickstart. |
| [crash-recovery](crash-recovery/) | The idempotency story: schedules under a **caller-owned instance id**. Kill the app mid-booking and restart it, and the run recovers on its own. Calling again with the same id then **attaches** to that run and returns the same confirmation code instead of booking twice. |
| [durable-memory](durable-memory/) | Where the durability boundary sits: durable chat with a `MessageChatMemoryAdvisor`. Spring AI runs advisors **synchronously**, so the memory advisor's response phase (saving the answer) runs only **after a successful call** — a crash keeps the workflow but not the answer, until you re-attach. |

Start with **event-planner** for the "add the starter, get durability" experience, then
**crash-recovery** to make a side-effecting tool safe to retry, then **durable-memory** to see where
the durability boundary sits — the workflow, not Spring AI's caller-side advisor chain.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [JDK 21](https://adoptium.net/) or later, and [Maven 3.9+](https://maven.apache.org/download.cgi)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

Each quickstart has its own README with the full run steps.

## How durability works

- `diagrid-spring-ai-starter` auto-configures a `DurableAdvisor` (attached to every `ChatClient` built
  from the injected `ChatClient.Builder`) and an in-process Dapr Workflow worker.
- Declaring the client as a `ChatClient` **bean** upgrades that: the starter attaches a *per-agent*
  advisor and names the workflow after the bean (`spring-ai.<beanName>.workflow`) instead of the shared
  `spring-ai.workflow`. **event-planner** and **crash-recovery** do this; **durable-memory** builds its
  client from the injected builder and takes the generic path.
- Each `ChatClient.call()` becomes a Dapr Workflow; the model turn and each `@Tool` call run as
  separate checkpointed activities.
- `@Tool` **beans** (not per-call `.defaultTools(...)`) are rediscovered on the restarted worker, so a
  resumed workflow can run the pending tool activity.
- A durable activity is *at-least-once*: the tool in flight at crash time re-runs on recovery. Make
  side-effecting tools idempotent (key off a business value) — the **crash-recovery** quickstart shows
  the caller-owned-instance-id pattern for exactly this.
- Durability wraps the **workflow** (model + tool activities), **not** Spring AI's caller-side advisor
  chain. `DurableAdvisor` is terminal; an advisor's response phase (chat memory, logging, post-processing)
  runs synchronously *after a successful call* — so it is skipped on a crash/timeout. The
  **durable-memory** quickstart shows this and how re-attaching completes the chain.

## Agent registration

Durability and registration are separate packages. The starter makes an agent durable; a second
dependency, `io.diagrid:diagrid-spring-ai-agent-registry`, is what records it as a Catalyst agent.

The registry records one agent per `ChatClient` **bean**, named after the bean, filed under
`diagrid.spring-ai.registry.app-id`. That app id must match the app's Dapr app id, or Catalyst drops
the record with no error logged. A client built from the injected `ChatClient.Builder` is not a bean
and so is never registered.

**event-planner** wires this up; **crash-recovery** and **durable-memory** do not yet, so they run
durably but register nothing.

The library lives at [diagridio/java-ai](https://github.com/diagridio/java-ai).
