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
 * A deterministic stand-in for a hosted chat model: it plays a canned two-turn conversation — ask
 * for the tool, then answer from its result — so the demo is free, offline and identical on every
 * run. Set {@code OPENAI_API_KEY} and {@code DIAGRID_QUICKSTART_MODEL=openai} for a real provider.
 *
 * <p><b>Note the subject the first turn asks for offline: {@code someone@example.com}, who is
 * nobody.</b> A model does not know who is calling; {@link BookingTools} answers for the subject
 * the filter verified instead.
 */
public class CannedChatModel implements ChatModel {

  static final String MODEL = "canned-offline";

  /** The subject the offline script invents, which the tool then overrides. */
  static final String MODEL_GUESSED_SUBJECT = "someone@example.com";

  static final String ACCOUNT_ID = "ACME-1";

  private static final String OFFLINE_ANSWER =
      "You have two bookings: the Grand Ballroom on March 15th "
          + "(9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM).";

  private static final String CATALYST_ANSWER = "Here is what the CRM returned for " + ACCOUNT_ID + ".";

  /**
   * A {@link ToolCallingChatOptions} rather than a plain {@code ChatOptions}: Spring AI's
   * tool-calling advisor reads the tool callbacks and the tool context off these options.
   */
  private final ToolCallingChatOptions options =
      ToolCallingChatOptions.builder().model(MODEL).toolCallbacks(List.of()).build();

  private final boolean offline;

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

  private AssistantMessage answer() {
    return AssistantMessage.builder().content(offline ? OFFLINE_ANSWER : CATALYST_ANSWER).build();
  }

  /** The first turn: offline it invents a subject; the CRM tool takes none. */
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
