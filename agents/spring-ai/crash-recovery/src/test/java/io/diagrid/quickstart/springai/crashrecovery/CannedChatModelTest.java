package io.diagrid.quickstart.springai.crashrecovery;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.ChatOptions;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.model.tool.ToolCallingChatOptions;

/**
 * The offline model's contract, which is what the crash-recovery demo runs on by default.
 *
 * <p>Every case here stands for something outside this file that would otherwise break silently:
 * the agent's tool name, the durability layer's tool-callback wiring, and the string the Catalyst
 * console displays as this agent's model.
 */
class CannedChatModelTest {

  private static final String SYSTEM = "You are a travel booking assistant.";

  private final CannedChatModel model = new CannedChatModel();

  /** The conversation as it stands before the tool has run. */
  private static Prompt opening(String userText) {
    return new Prompt(List.of(new SystemMessage(SYSTEM), new UserMessage(userText)));
  }

  /** The conversation as the durability layer rebuilds it after the tool has run. */
  private static Prompt afterTool(String userText, String toolResult) {
    AssistantMessage asked = AssistantMessage.builder()
        .content("")
        .toolCalls(List.of(new AssistantMessage.ToolCall(
            "call_commit_1", "function", "commitReservation", "{\"reference\":\"ABC123\"}")))
        .build();
    ToolResponseMessage answered = ToolResponseMessage.builder()
        .responses(List.of(new ToolResponseMessage.ToolResponse(
            "call_commit_1", "commitReservation", toolResult)))
        .build();
    return new Prompt(List.of(new SystemMessage(SYSTEM), new UserMessage(userText), asked, answered));
  }

  private static AssistantMessage output(ChatResponse response) {
    return response.getResult().getOutput();
  }

  @Test
  void asksForTheBookingToolOnTheFirstTurn() {
    // The model's tool selection is the only path to commitReservation, whose sleep is the crash
    // window. A wrong name here is a demo with nothing to interrupt.
    AssistantMessage message = output(this.model.call(opening("Confirm the booking with reference ABC123.")));

    assertEquals(1, message.getToolCalls().size());
    assertEquals("commitReservation", message.getToolCalls().get(0).name());
  }

  @Test
  void passesTheReferenceFromTheUserMessage() {
    // The README invites the reader to change the reference and commitReservation derives the
    // confirmation code from it, so a fixed argument would show them a code for a booking they
    // did not make.
    AssistantMessage message = output(this.model.call(opening("Confirm the booking with reference XYZ789.")));

    assertEquals("{\"reference\":\"XYZ789\"}", message.getToolCalls().get(0).arguments());
  }

  @Test
  void fallsBackToTheSampleReferenceWhenTheMessageCarriesNone() {
    // Anything outside the reference character class lands here rather than being interpolated
    // into the JSON arguments. ABC123 is both the controller's own default and the body the
    // Catalyst console sends.
    AssistantMessage message = output(this.model.call(opening("Please book something for me.")));

    assertEquals("{\"reference\":\"ABC123\"}", message.getToolCalls().get(0).arguments());
  }

  @Test
  void answersWithTheToolResultOnceTheToolHasRun() {
    // The tool result arrives JSON-encoded, because Spring AI serialises a tool's return value
    // before putting it back in the conversation. A real model reads that and answers in prose, so
    // echoing it raw would put literal quotes in the `result` field the README documents.
    String committed = "\"Booking ABC123 confirmed. Confirmation code: BK-1B84BF9\"";

    AssistantMessage message = output(this.model.call(afterTool("Confirm the booking with reference ABC123.", committed)));

    assertTrue(message.getToolCalls().isEmpty(), "the tool has already run, so it must not be asked for again");
    assertEquals("Booking ABC123 confirmed. Confirmation code: BK-1B84BF9", message.getText());
  }

  @Test
  void passesThroughAToolResultThatIsNotAJsonString() {
    // A tool returning an object rather than a String. Showing it as-is is the most useful thing
    // this model can do with a result it knows nothing about.
    String structured = "{\"code\":\"BK-1B84BF9\"}";

    AssistantMessage message = output(this.model.call(afterTool("Confirm the booking with reference ABC123.", structured)));

    assertEquals(structured, message.getText());
  }

  @Test
  void neverAsksForASecondBookingWhenTheConversationIsReplayed() {
    // THE ONE THAT MATTERS AFTER A CRASH. The durability layer re-enters this model with the
    // recorded conversation, so the post-tool conversation must answer, not book again, however
    // many times it arrives. A counter field would reset with the process and re-book on the
    // restart, which is the failure this quickstart exists to disprove.
    Prompt replayed = afterTool("Confirm the booking with reference ABC123.", "\"Booking ABC123 confirmed.\"");

    assertTrue(output(this.model.call(replayed)).getToolCalls().isEmpty());
    assertTrue(output(this.model.call(replayed)).getToolCalls().isEmpty());
  }

  @Test
  void doesNotBookAgainWhenItsOwnToolCallCameBackEmpty() {
    // Fail closed. A tool response that arrived with nothing in it, or an activity interrupted
    // between the call and its result, must not read as "no tool has run yet": this model has
    // already asked, and asking twice is a second booking.
    AssistantMessage asked = AssistantMessage.builder()
        .content("")
        .toolCalls(List.of(new AssistantMessage.ToolCall(
            "call_commit_1", "function", "commitReservation", "{\"reference\":\"ABC123\"}")))
        .build();
    Prompt interrupted = new Prompt(List.of(
        new SystemMessage(SYSTEM), new UserMessage("Confirm the booking with reference ABC123."), asked));

    assertTrue(output(this.model.call(interrupted)).getToolCalls().isEmpty());
  }

  @Test
  void startsTheScriptOverOnASecondQuestion() {
    // A conversation that continues past an answered booking. This app sends one question per
    // conversation, but the sibling durable-memory quickstart does not, and replaying the old
    // answer forever would be the wrong thing to hand it.
    Prompt secondTurn = new Prompt(List.of(
        new SystemMessage(SYSTEM),
        new UserMessage("Confirm the booking with reference ABC123."),
        AssistantMessage.builder().content("Booking ABC123 confirmed.").build(),
        new UserMessage("Confirm the booking with reference XYZ789.")));

    AssistantMessage message = output(this.model.call(secondTurn));

    assertEquals("{\"reference\":\"XYZ789\"}", message.getToolCalls().get(0).arguments());
  }

  @Test
  void exposesToolCallingOptionsCarryingTheModelName() {
    // The model string is what the agent registry reads for the Catalyst console, and the
    // inherited default would leave it null. The ToolCallingChatOptions type is what lets the
    // durability layer attach the workflow's tool callbacks, which is what the registry reads back
    // as this agent's per-request tool list.
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
