package io.diagrid.quickstart.springai.eventplanner;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Defines the event planner as a {@link ChatClient} bean. This is ordinary Spring AI: the client is
 * still built from the injected {@link ChatClient.Builder}, so the durability layer attaches as it
 * always has, and there is no diagrid API in application code.
 *
 * <p>Being a <em>bean</em> is what gets the agent registered. The agent registry discovers
 * {@code ChatClient} beans and records one agent per bean, named after the bean, so this agent
 * registers as {@code spring-ai-event-planner} under the Dapr app id set in
 * {@code application.properties}.
 *
 * <p>That is why the {@code @Bean} annotation carries an explicit name: the registered agent name is
 * the bean name verbatim. Both the durability layer and the registry derive the per-agent workflow
 * name from that same bean name, so this agent runs as
 * {@code spring-ai.spring-ai-event-planner.workflow} (visible in {@code dapr workflow list}) rather
 * than the generic {@code spring-ai.workflow}, and the name recorded on the agent record is the
 * workflow that actually runs.
 */
@Configuration
public class EventPlannerAgentConfig {

  private static final String SYSTEM = """
      You are an event planner. Call all three tools in sequence:
      1. First call step_one_search with the city name
      2. Then call step_two_compare with the result from step 1
      3. Finally call step_three_confirm with the result from step 2
      Do NOT skip any steps.""";

  @Bean("spring-ai-event-planner")
  ChatClient eventPlanner(ChatClient.Builder builder) {
    return builder.defaultSystem(SYSTEM).build();
  }
}
