package io.diagrid.quickstart.springai.eventplanner;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * Ordinary Spring AI usage — no durability code. The {@link ChatClient} is built from the injected
 * {@link ChatClient.Builder}, which lets the dapr-spring-ai {@code DurableAdvisor} attach automatically.
 * Every {@code chatClient...call()} then runs as a Dapr Workflow: the model turns and each tool call
 * are checkpointed activities, so a crash resumes from the last completed step.
 *
 * <p>The three {@link EventPlannerTools} are global {@code @Tool} beans, so the durability layer offers
 * them to this agent automatically — no explicit {@code .defaultTools(...)} needed.
 */
@RestController
public class EventPlannerController {

  private static final String SYSTEM = """
      You are an event planner. Call all three tools in sequence:
      1. First call step_one_search with the city name
      2. Then call step_two_compare with the result from step 1
      3. Finally call step_three_confirm with the result from step 2
      Do NOT skip any steps.""";

  private final ChatClient chatClient;

  public EventPlannerController(ChatClient.Builder builder) {
    this.chatClient = builder.defaultSystem(SYSTEM).build();
  }

  @PostMapping("/run")
  public RunResponse run(@RequestBody RunRequest request) {
    String response = chatClient.prompt().user(request.prompt()).call().content();
    return new RunResponse(response);
  }

  public record RunRequest(String prompt) {}

  public record RunResponse(String response) {}
}
