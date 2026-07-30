package io.diagrid.quickstart.springai.eventplanner;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

/**
 * The Event Planner's three tools, which the agent calls in sequence. These are plain Spring AI
 * {@code @Tool} methods — there is no durability code here. Because the {@code dapr-spring-ai-starter}
 * is on the classpath, each call runs as a checkpointed Dapr Workflow activity.
 *
 * <p><b>Why a {@code @Tool} Spring bean</b> (and not a per-call {@code .defaultTools(new ...)}): the
 * durability layer rediscovers {@code @Tool} beans at startup and offers them to every durable agent.
 * After a crash, the fresh worker re-registers them so the resumed workflow can run the pending
 * activity. A request-scoped tool would be gone after a cold restart.
 *
 * <p><b>Why the tools are side-effect-free</b> (just log + return a string): a durable activity is
 * <em>at-least-once</em>, so the tool that was in flight at crash time re-runs on recovery. Pure tools
 * make that replay harmless — which is why {@code step_two_compare} can crash and safely re-run. A
 * tool with a real side effect (a booking, a payment) must be made idempotent by the application;
 * the sibling <b>crash-recovery</b> quickstart shows how (caller-owned instance id + re-attach).
 */
@Component
public class EventPlannerTools {

  private static final Logger LOG = LoggerFactory.getLogger(EventPlannerTools.class);

  @Tool(name = "step_one_search",
      description = "Search for event venues in a city. This is the first step.")
  public String stepOneSearch(@ToolParam(description = "the city to search in") String city) {
    LOG.info(">>> TOOL 1: Searching venues in '{}'...", city);
    LOG.info(">>> TOOL 1 COMPLETE: Found 3 venues");
    return "Found 3 venues in " + city + ". Now call step_two_compare.";
  }

  @Tool(name = "step_two_compare",
      description = "Compare the venue options. This is the second step.")
  public String stepTwoCompare(@ToolParam(description = "the venues found in step one") String data) {
    LOG.info(">>> TOOL 2: Comparing venues...");
    Runtime.getRuntime().halt(1); // 💥 Comment out this line before the second run — then re-run without re-triggering /run and watch the workflow resume. Use halt(), not System.exit(): halt skips JVM shutdown hooks, so it's an abrupt crash (what we want to simulate) and avoids deadlocking on Spring Boot's graceful shutdown, which would wait on this very request thread.
    LOG.info(">>> TOOL 2 COMPLETE: Grand Ballroom is the best option");
    return "Grand Ballroom is the best option. Now call step_three_confirm.";
  }

  @Tool(name = "step_three_confirm",
      description = "Confirm the venue booking. This is the third and final step.")
  public String stepThreeConfirm(@ToolParam(description = "the selected venue") String selection) {
    LOG.info(">>> TOOL 3: Confirming booking...");
    LOG.info(">>> TOOL 3 COMPLETE: Booking confirmed for Grand Ballroom");
    return "Booking confirmed for Grand Ballroom. All steps complete!";
  }
}
