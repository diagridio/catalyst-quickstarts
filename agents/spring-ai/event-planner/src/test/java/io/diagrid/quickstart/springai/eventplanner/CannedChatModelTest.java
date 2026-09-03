package io.diagrid.quickstart.springai.eventplanner;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.ChatOptions;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.model.tool.ToolCallingChatOptions;

/**
 * The offline model's contract, which is what the event-planner demo runs on by default.
 *
 * <p>Every case here stands for something outside this file that would otherwise break silently:
 * the three tool names and their parameter names in {@link EventPlannerTools}, the durability
 * layer's tool-callback wiring, and the string the Catalyst console displays as this agent's model.
 *
 * <p>The case that matters most is {@link #asksForStepTwoAgainWhenItsResultIsMissing()}: it is the
 * conversation the durability layer replays after the crash this quickstart is built around, and
 * the one where this model deliberately behaves differently from its {@code crash-recovery} sibling.
 */
class CannedChatModelTest {

  private static final String SYSTEM = "You are an event planner.";
  private static final String QUESTION = "Find a venue in Austin for a company gala.";

  private static final String STEP_ONE_RESULT =
      "\"Found 3 venues in Austin. Now call step_two_compare.\"";
  private static final String STEP_TWO_RESULT =
      "\"Grand Ballroom is the best option. Now call step_three_confirm.\"";
  private static final String STEP_THREE_RESULT =
      "\"Booking confirmed for Grand Ballroom. All steps complete!\"";

  private final CannedChatModel model = new CannedChatModel();

  /**
   * The conversation as the durability layer rebuilds it: the question, then one asked/answered pair
   * per completed step, in order.
   */
  private static Prompt after(String... toolResults) {
    List<Message> messages = new ArrayList<>();
    messages.add(new SystemMessage(SYSTEM));
    messages.add(new UserMessage(QUESTION));
    for (int i = 0; i < toolResults.length; i++) {
      messages.add(asked(i));
      messages.add(answered(i, toolResults[i]));
    }
    return new Prompt(messages);
  }

  private static AssistantMessage asked(int step) {
    String tool = CannedChatModel.STEPS.get(step);
    return AssistantMessage.builder()
        .content("")
        .toolCalls(List.of(new AssistantMessage.ToolCall("call_" + tool, "function", tool, "{}")))
        .build();
  }

  private static ToolResponseMessage answered(int step, String result) {
    String tool = CannedChatModel.STEPS.get(step);
    return ToolResponseMessage.builder()
        .responses(List.of(new ToolResponseMessage.ToolResponse("call_" + tool, tool, result)))
        .build();
  }

  private static AssistantMessage output(ChatResponse response) {
    return response.getResult().getOutput();
  }

  private static AssistantMessage.ToolCall onlyToolCall(AssistantMessage message) {
    assertEquals(1, message.getToolCalls().size(), "expected exactly one tool call");
    return message.getToolCalls().get(0);
  }

  @Test
  void asksForStepOneOnTheFirstTurn() {
    // The model's tool selection is the only path into EventPlannerTools. A wrong name here is a
    // demo that stops before it starts, with a tool-not-found rather than the crash it is about.
    assertEquals("step_one_search", onlyToolCall(output(this.model.call(after()))).name());
  }

  @Test
  void passesTheCityFromTheUserMessage() {
    // step_one_search echoes the city into its reply and the README invites the reader to change
    // it, so a fixed argument would show them a search they did not ask for.
    assertEquals("{\"city\":\"Austin\"}",
        onlyToolCall(output(this.model.call(after()))).arguments());
  }

  @Test
  void fallsBackToAReadableCityWhenTheMessageCarriesNone() {
    // Reads correctly in the tool's echoed reply ("Found 3 venues in the requested city"), which
    // pasting the whole prompt into the argument would not.
    Prompt vague = new Prompt(List.of(new SystemMessage(SYSTEM), new UserMessage("Plan my gala.")));

    assertEquals("{\"city\":\"the requested city\"}",
        onlyToolCall(output(this.model.call(vague))).arguments());
  }

  @Test
  void asksForStepTwoWithStepOnesResult() {
    // The parameter name is `data`, from EventPlannerTools.stepTwoCompare's @ToolParam. The value is
    // step one's own line, decoded out of the JSON Spring AI wrapped it in.
    AssistantMessage.ToolCall call = onlyToolCall(output(this.model.call(after(STEP_ONE_RESULT))));

    assertEquals("step_two_compare", call.name());
    assertEquals("{\"data\":\"Found 3 venues in Austin. Now call step_two_compare.\"}",
        call.arguments());
  }

  @Test
  void asksForStepThreeWithStepTwosResult() {
    AssistantMessage.ToolCall call =
        onlyToolCall(output(this.model.call(after(STEP_ONE_RESULT, STEP_TWO_RESULT))));

    assertEquals("step_three_confirm", call.name());
    assertEquals("{\"selection\":\"Grand Ballroom is the best option. Now call step_three_confirm.\"}",
        call.arguments());
  }

  @Test
  void answersWithTheLastToolResultOnceAllThreeStepsHaveRun() {
    // Echoed rather than restated, and decoded: the result arrives JSON-encoded because Spring AI
    // serialises a tool's return value before putting it back in the conversation, so passing it on
    // raw would put literal quotes in the `response` field the README documents.
    AssistantMessage message =
        output(this.model.call(after(STEP_ONE_RESULT, STEP_TWO_RESULT, STEP_THREE_RESULT)));

    assertTrue(message.getToolCalls().isEmpty(), "every step has run, so none must be asked for again");
    assertEquals("Booking confirmed for Grand Ballroom. All steps complete!", message.getText());
  }

  @Test
  void asksForStepTwoAgainWhenItsResultIsMissing() {
    // THE ONE THAT MATTERS AFTER THE CRASH, and the reason this model counts results instead of
    // failing closed the way the crash-recovery sibling does. halt(1) inside step_two_compare kills
    // the JVM between the call and its result, so this is exactly what the durability layer replays
    // once the reader comments the halt out and restarts. Asking again is what lets the run finish;
    // treating "asked but unanswered" as done would answer with step one's output and end the demo
    // early, having proved nothing. Safe because these tools are pure — see EventPlannerTools.
    List<Message> interrupted = new ArrayList<>(after(STEP_ONE_RESULT).getInstructions());
    interrupted.add(asked(1));

    assertEquals("step_two_compare",
        onlyToolCall(output(this.model.call(new Prompt(interrupted)))).name());
  }

  @Test
  void keepsAnsweringOnceTheScriptIsFinished() {
    // The durability layer can re-enter this model with a recorded conversation any number of
    // times. A finished script must stay finished rather than starting a fourth call.
    Prompt finished = after(STEP_ONE_RESULT, STEP_TWO_RESULT, STEP_THREE_RESULT);

    assertTrue(output(this.model.call(finished)).getToolCalls().isEmpty());
    assertTrue(output(this.model.call(finished)).getToolCalls().isEmpty());
  }

  @Test
  void startsTheScriptOverOnASecondQuestion() {
    // A conversation that continues past a finished plan. This app sends one question per
    // conversation, but the sibling durable-memory quickstart does not, and replaying the old
    // answer forever would be the wrong thing to hand it.
    List<Message> messages =
        new ArrayList<>(after(STEP_ONE_RESULT, STEP_TWO_RESULT, STEP_THREE_RESULT).getInstructions());
    messages.add(AssistantMessage.builder().content("All steps complete!").build());
    messages.add(new UserMessage("Find a venue in Denver for a launch party."));

    AssistantMessage.ToolCall call = onlyToolCall(output(this.model.call(new Prompt(messages))));

    assertEquals("step_one_search", call.name());
    assertEquals("{\"city\":\"Denver\"}", call.arguments());
  }

  @Test
  void encodesAnArgumentThatWouldOtherwiseBreakTheJson() {
    // These arguments are previous tool results, so their content comes from another component
    // rather than from a pattern this class controls. Concatenating a value with a quote in it —
    // which is how the crash-recovery sibling builds its single argument — would produce invalid
    // JSON and fail tool-argument binding with an error pointing nowhere near here.
    AssistantMessage.ToolCall call =
        onlyToolCall(output(this.model.call(after("\"Found a \\\"budget\\\" venue.\""))));

    assertEquals("{\"data\":\"Found a \\\"budget\\\" venue.\"}", call.arguments());
  }

  @Test
  void passesThroughAToolResultThatIsNotAJsonString() {
    // A tool returning an object rather than a String. Showing it as-is is the most useful thing
    // this model can do with a result it knows nothing about.
    String structured = "{\"venues\":3}";

    assertEquals(structured,
        output(this.model.call(after(STEP_ONE_RESULT, STEP_TWO_RESULT, structured))).getText());
  }

  @Test
  void exposesToolCallingOptionsCarryingTheModelName() {
    // The model string is what the agent registry reads for the Catalyst console, and the inherited
    // default would leave it null. The ToolCallingChatOptions type is what lets the durability layer
    // attach the workflow's tool callbacks, which the registry reads back as this agent's
    // per-request tool list.
    ChatOptions options = this.model.getOptions();

    assertInstanceOf(ToolCallingChatOptions.class, options);
    assertEquals("canned-offline", options.getModel());
    // Not null, which is what the inherited builder would leave here and what the non-durable path
    // hands straight to Spring AI's own tool-calling advisor.
    assertEquals(List.of(), ((ToolCallingChatOptions) options).getToolCallbacks());
  }

  @Test
  void keepsTheClassNameTheAgentRegistryDerivesTheProviderFrom() {
    // The registry strips a trailing "ChatModel" from this type's simple name and lowercases the
    // rest to get the provider string on the Catalyst agent page. Renaming this class silently
    // changes what a user sees there, and nothing else here would notice. Pinned as the whole name
    // rather than by re-implementing the derivation, which lives in the library.
    assertEquals("CannedChatModel", CannedChatModel.class.getSimpleName());
  }
}
