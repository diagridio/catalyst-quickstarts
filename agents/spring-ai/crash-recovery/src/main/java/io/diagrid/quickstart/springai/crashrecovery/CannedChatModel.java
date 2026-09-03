package io.diagrid.quickstart.springai.crashrecovery;

import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.ToolResponseMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.metadata.ChatGenerationMetadata;
import org.springframework.ai.chat.metadata.ChatResponseMetadata;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.prompt.ChatOptions;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.model.tool.ToolCallingChatOptions;

/**
 * An offline {@link ChatModel} that always plays the same two-turn script: ask for
 * {@code commitReservation}, then report what the tool returned.
 *
 * <p><b>Why this exists.</b> This quickstart is about durable execution, not model quality, and the
 * model is on its critical path: the durability layer runs every LLM call and every tool call as a
 * separate workflow activity, and the model's tool selection is the only thing that reaches
 * {@link SlowBookingTools#commitReservation}, whose sleep is the crash window. So the demo cannot
 * run without a model at all, and shipping a canned one is what lets it run without an account. Set
 * {@code DIAGRID_QUICKSTART_MODEL=openai} to use a real provider instead (see
 * {@link CannedModelConfig}).
 *
 * <p><b>The class name is load-bearing.</b> The agent registry derives what the Catalyst console
 * displays from this type: the simple name becomes the LLM client, and the same name with a trailing
 * {@code ChatModel} stripped and lowercased becomes the provider. So this registers as client
 * {@code CannedChatModel}, provider {@code canned}. Renaming it silently changes what a user sees on
 * the agent page, which is why {@code CannedChatModelTest} pins the name.
 *
 * <p><b>The turn is decided from the conversation, never from a counter.</b> The durability layer
 * hands this model the whole conversation on every invocation, and it runs inside a workflow
 * activity that can be re-entered after a crash. A counter field would reset with the process and
 * ask for the booking a second time after the restart, which is exactly the double-booking this
 * quickstart exists to disprove.
 *
 * <p><b>{@code stream()} is inherited and left alone.</b> {@code ChatModel}'s default body throws
 * {@code UnsupportedOperationException("streaming is not supported")}, which is right here rather
 * than merely tolerable: the durability layer only ever calls {@link #call(Prompt)}, and a durable
 * activity that streamed would have nothing to record. Anyone who later reaches for
 * {@code ChatClient.stream()} gets that message instead of a canned half-answer.
 */
public class CannedChatModel implements ChatModel {

  /** Also what the registry reports as this agent's model, via {@link #getOptions()}. */
  static final String MODEL = "canned-offline";

  static final String DEFAULT_REFERENCE = "ABC123";

  private static final String TOOL = "commitReservation";

  /**
   * The booking reference in {@code CrashRecoveryController}'s user message.
   *
   * <p>The character class is not tidiness. The captured value is concatenated into the JSON tool
   * arguments below and it arrives in an HTTP request body, so a permissive {@code \S+} would let a
   * quote break the JSON and fail tool-argument binding with an error pointing nowhere near here.
   * Restricting the match is cheaper than escaping.
   *
   * <p>{@code CrashRecoveryController} rejects a reference this class cannot match, so the fallback
   * below is unreachable from {@code /crash/run} and the two must stay in step. That check is there
   * rather than here because the fallback is silent: substituting {@code ABC123} for a reference the
   * caller sent would commit a different booking and report success for it, on the step the whole
   * demo builds up to.
   */
  private static final Pattern REFERENCE =
      Pattern.compile("reference\\s+([A-Za-z0-9_-]{1,64})\\.?\\s*$");

  private static final ObjectMapper JSON = new ObjectMapper();

  /**
   * Not the inherited default, which returns a plain {@link ChatOptions} whose model is null.
   *
   * <p>The model string is the reason this override exists: the agent registry reads
   * {@code getDefaultOptions().getModel()} for what the Catalyst console shows, and the inherited
   * default would leave it blank.
   *
   * <p>It is a {@link ToolCallingChatOptions} rather than a plain {@code ChatOptions} because the
   * durability layer's options factory attaches the workflow's tool callbacks <em>only if</em>
   * {@code mutate()} yields a {@code ToolCallingChatOptions.Builder}, and those callbacks are what
   * the agent registry reads back as this agent's per-request tool list. This model ignores the
   * callbacks itself (it names its tool outright), so getting this wrong would not stop the demo:
   * it would quietly shorten what the console reports.
   *
   * <p>The empty callback list is not redundant. Every real Spring AI options class returns a list
   * rather than null here, and the non-durable path hands these options straight to Spring AI's own
   * tool-calling advisor.
   */
  private final ToolCallingChatOptions options =
      ToolCallingChatOptions.builder().model(MODEL).toolCallbacks(List.of()).build();

  @Override
  public ChatOptions getOptions() {
    return this.options;
  }

  @Override
  public ChatResponse call(Prompt prompt) {
    String toolResult = answerFor(prompt);
    boolean toolHasRun = toolResult != null;

    // Turn 2: the tool has already committed the booking, so answer with what it returned. Echoed
    // verbatim rather than restated: commitReservation derives the confirmation code from the
    // reference, so any fixed wording here would have to hardcode a hash and would be wrong for
    // every reference but one.
    //
    // Turn 1: no tool response in the conversation yet, so ask for the booking.
    AssistantMessage message = toolHasRun
        ? AssistantMessage.builder().content(plainText(toolResult)).build()
        : AssistantMessage.builder()
            .content("")
            .toolCalls(List.of(new AssistantMessage.ToolCall(
                "call_commit_1", "function", TOOL,
                "{\"reference\":\"" + reference(prompt) + "\"}")))
            .build();

    // The workflow loops on whether the generation carries tool calls, not on this string, so the
    // finish reason is reported for fidelity rather than control flow.
    Generation generation = new Generation(message,
        ChatGenerationMetadata.builder().finishReason(toolHasRun ? "stop" : "tool_calls").build());
    return new ChatResponse(List.of(generation),
        ChatResponseMetadata.builder().model(MODEL).build());
  }

  /**
   * A tool result as prose, rather than as the JSON Spring AI wrapped it in.
   *
   * <p>Tool return values are serialised to JSON before they re-enter the conversation, so
   * {@code commitReservation}'s String arrives quoted and escaped. A real model reads that and
   * answers in its own words; this one echoes it, so without decoding, the quotes would end up in
   * the {@code result} field of the response the README documents.
   *
   * <p>Anything that is not a JSON string (a tool returning an object, say) is passed through
   * unchanged, which is the most useful thing to show for a tool this model does not know about.
   */
  private static String plainText(String toolResult) {
    if (toolResult == null) {
      return "";
    }
    try {
      JsonNode parsed = JSON.readTree(toolResult);
      return parsed.isTextual() ? parsed.asText() : toolResult;
    } catch (JsonProcessingException e) {
      return toolResult;
    }
  }

  /**
   * What to answer with, or null when the booking has not been asked for yet.
   *
   * <p>The value is JSON-encoded, because that is how Spring AI records a tool's return value and
   * {@link #plainText} decodes it on the way out. The sentinel below matches that encoding.
   *
   * <p><b>The scan fails closed, and stops at the current user turn.</b> Two rules beyond "find the
   * tool result", both of which exist so this model can never ask for a second booking:
   *
   * <ul>
   *   <li>An assistant message carrying tool calls ends the scan even when no result followed it.
   *       We already asked. A tool response that arrived empty, or an activity interrupted between
   *       the call and its result, would otherwise read as "no tool has run" and book again, which
   *       is the double booking this whole quickstart exists to disprove.
   *   <li>The last user message ends the scan, so a second question in one conversation starts the
   *       script over instead of replaying the previous answer forever. This app sends one question
   *       per conversation, but the sibling {@code durable-memory} quickstart does not.
   * </ul>
   */
  private static String answerFor(Prompt prompt) {
    List<Message> messages = prompt.getInstructions();
    for (int i = messages.size() - 1; i >= 0; i--) {
      Message message = messages.get(i);
      if (message instanceof ToolResponseMessage tool && !tool.getResponses().isEmpty()) {
        return tool.getResponses().get(tool.getResponses().size() - 1).responseData();
      }
      if (message instanceof AssistantMessage assistant && !assistant.getToolCalls().isEmpty()) {
        return "\"The booking was requested but the tool returned no result.\"";
      }
      if (message instanceof UserMessage) {
        return null;
      }
    }
    return null;
  }

  /**
   * The booking reference from the last user message, or {@link #DEFAULT_REFERENCE}.
   *
   * <p>Read back rather than fixed because the README invites the reader to change it and the
   * confirmation code is derived from it. A canned model that always asked for {@code ABC123} would
   * hand a reader who booked {@code XYZ789} the code for a booking they did not make, on the step
   * the whole demo builds up to.
   */
  private static String reference(Prompt prompt) {
    List<Message> messages = prompt.getInstructions();
    for (int i = messages.size() - 1; i >= 0; i--) {
      if (messages.get(i) instanceof UserMessage user) {
        Matcher matcher = REFERENCE.matcher(user.getText());
        return matcher.find() ? matcher.group(1) : DEFAULT_REFERENCE;
      }
    }
    return DEFAULT_REFERENCE;
  }
}
