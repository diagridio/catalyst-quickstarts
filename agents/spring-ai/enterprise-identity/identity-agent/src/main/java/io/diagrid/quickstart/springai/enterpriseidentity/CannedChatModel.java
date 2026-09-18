package io.diagrid.quickstart.springai.enterpriseidentity;

import java.util.List;
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
 * A deterministic stand-in for a hosted chat model.
 *
 * <p>This quickstart's point is identity, not model quality, so it plays a canned two-turn
 * conversation: ask for the tool, then answer from the tool's result. That keeps the demo free,
 * offline and identical on every run, whatever task is sent. Set {@code OPENAI_API_KEY} and
 * {@code DIAGRID_QUICKSTART_MODEL=openai} to use a real provider instead — see
 * {@link CannedModelConfig}.
 *
 * <p><b>Note the subject the first turn asks for offline: {@code someone@example.com}, who is
 * nobody.</b> A model does not know who is calling and must not be trusted to decide;
 * {@link BookingTools} answers for the subject the filter verified instead. A real provider behaves
 * the same way, which is the point of substituting rather than validating.
 *
 * <p><b>The turn is decided from the conversation, never from a counter.</b> A counter field would
 * reset with the process and ask for the tool a second time; the replayed message history is the
 * only state that always tells the truth. Scoped to the messages after the last user message so a
 * second question in one conversation starts the script over rather than replaying the answer
 * forever.
 *
 * <p>{@code stream()} is inherited and left alone. {@code ChatModel}'s default body throws
 * {@code UnsupportedOperationException}, which is right here rather than merely tolerated: the
 * caller is {@code ChatClient.call()}, and a streamed run would put the tool call on a thread the
 * caller's identity does not reach. See {@link CatalystMcpClient}.
 */
public class CannedChatModel implements ChatModel {

  static final String MODEL = "canned-offline";

  /** The offline script's account-free tool call, and the subject it invents. */
  static final String MODEL_GUESSED_SUBJECT = "someone@example.com";

  static final String ACCOUNT_ID = "ACME-1";

  private static final String OFFLINE_ANSWER =
      "You have two bookings: the Grand Ballroom on March 15th "
          + "(9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM).";

  private static final String CATALYST_ANSWER = "Here is what the CRM returned for " + ACCOUNT_ID + ".";

  /**
   * Not the inherited default, which returns a {@link ChatOptions} whose model is null.
   *
   * <p>A {@link ToolCallingChatOptions} rather than a plain {@code ChatOptions} because Spring AI's
   * tool-calling advisor reads the tool callbacks and the tool context off these options; a plain
   * one would leave the agent with no tools and no context, and the substitution this quickstart
   * demonstrates would never happen.
   */
  private final ToolCallingChatOptions options =
      ToolCallingChatOptions.builder().model(MODEL).toolCallbacks(List.of()).build();

  private final boolean offline;

  /**
   * @param offline whether the agent is on the offline in-process tool rather than the CRM
   */
  public CannedChatModel(boolean offline) {
    this.offline = offline;
  }

  @Override
  public ChatOptions getOptions() {
    return this.options;
  }

  @Override
  public ChatResponse call(Prompt prompt) {
    boolean toolHasRun = toolHasRun(prompt.getInstructions());
    AssistantMessage message = toolHasRun ? answer() : toolCall();
    Generation generation = new Generation(message,
        ChatGenerationMetadata.builder().finishReason(toolHasRun ? "stop" : "tool_calls").build());
    return new ChatResponse(List.of(generation),
        ChatResponseMetadata.builder().model(MODEL).build());
  }

  /** The second turn: report what the tool returned, in the model's own words. */
  private AssistantMessage answer() {
    return AssistantMessage.builder().content(offline ? OFFLINE_ANSWER : CATALYST_ANSWER).build();
  }

  /**
   * The first turn: ask for the tool.
   *
   * <p>Offline it asks {@code my_bookings} for a subject it made up. Against Catalyst it asks
   * {@code account_summary}, which takes no subject — the difference the two tools exist to show.
   */
  private AssistantMessage toolCall() {
    String name = offline ? BookingTools.MY_BOOKINGS : CatalystMcpClient.ACCOUNT_SUMMARY;
    String arguments = offline
        ? "{\"" + BookingTools.SUBJECT_ARGUMENT + "\":\"" + MODEL_GUESSED_SUBJECT + "\"}"
        : "{\"" + CrmTools.ACCOUNT_ID_ARGUMENT + "\":\"" + ACCOUNT_ID + "\"}";
    return AssistantMessage.builder()
        .content("")
        .toolCalls(List.of(new AssistantMessage.ToolCall("call_" + name, "function", name, arguments)))
        .build();
  }

  /** Whether a tool has already answered since the last thing the user said. */
  private static boolean toolHasRun(List<Message> messages) {
    int from = 0;
    for (int i = 0; i < messages.size(); i++) {
      if (messages.get(i) instanceof UserMessage) {
        from = i;
      }
    }
    return messages.subList(from, messages.size()).stream()
        .anyMatch(ToolResponseMessage.class::isInstance);
  }
}
