package io.diagrid.quickstart.springai.eventplanner;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * Ordinary Spring AI usage with no durability code. The {@link ChatClient} is the
 * {@code spring-ai-event-planner} bean defined in {@link EventPlannerAgentConfig}, built there from
 * the injected {@link ChatClient.Builder}, which lets the diagrid-spring-ai {@code DurableAdvisor}
 * attach automatically. Every {@code chatClient...call()} then runs as a Dapr Workflow: the model
 * turns and each tool call are checkpointed activities, so a crash resumes from the last completed
 * step.
 *
 * <p>The three {@link EventPlannerTools} are global {@code @Tool} beans, so the durability layer offers
 * them to this agent automatically, with no explicit {@code .defaultTools(...)} needed.
 */
@RestController
public class EventPlannerController {

  private final ChatClient chatClient;

  public EventPlannerController(ChatClient chatClient) {
    this.chatClient = chatClient;
  }

  @PostMapping("/run")
  public RunResponse run(@RequestBody RunRequest request) {
    String response = chatClient.prompt().user(request.prompt()).call().content();
    return new RunResponse(response);
  }

  public record RunRequest(String prompt) {}

  public record RunResponse(String response) {}
}
