package io.diagrid.quickstart.springai.eventplanner;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
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
 * An offline {@link ChatModel} that always plays the same four-turn script: ask for
 * {@code step_one_search}, then {@code step_two_compare}, then {@code step_three_confirm}, then
 * report what the last tool returned.
 *
 * <p><b>Why this exists.</b> This quickstart is about durable execution, not model quality, and the
 * model is on its critical path: the durability layer runs every LLM call and every tool call as a
 * separate workflow activity, and the model's tool selection is the only thing that reaches
 * {@link EventPlannerTools}. So the demo cannot run without a model at all, and shipping a canned
 * one is what lets it run without an account. Set {@code DIAGRID_QUICKSTART_MODEL=openai} to use a
 * real provider instead (see {@link CannedModelConfig}).
 *
 * <p><b>This does not make the quickstart complete offline, and it is not meant to.</b>
 * {@link EventPlannerTools#stepTwoCompare} calls {@code Runtime.getRuntime().halt(1)}
 * unconditionally, so the app dies at step two whatever model is in play — that crash IS the demo,
 * and the README's walkthrough is to comment the line out and restart, watching the workflow resume
 * at step two rather than step one. All this class changes is that none of it needs an API key
 * first. The sibling {@code crash-recovery} quickstart is the same idea with the crash requested
 * over HTTP instead of edited into the source.
 *
 * <p><b>The class name is load-bearing.</b> The agent registry derives what the Catalyst console
 * displays from this type: the simple name becomes the LLM client, and the same name with a trailing
 * {@code ChatModel} stripped and lowercased becomes the provider. So this registers as client
 * {@code CannedChatModel}, provider {@code canned}. Renaming it silently changes what a user sees on
 * the agent page, which is why {@code CannedChatModelTest} pins the name.
 *
 * <p><b>The step is decided from the conversation, never from a counter.</b> The durability layer
 * hands this model the whole conversation on every invocation, and it runs inside a workflow activity
 * that is re-entered after the crash — which here is a certainty, not a possibility. A counter field
 * would reset with the process and restart the script at step one, throwing away the step-one result
 * the workflow had already checkpointed and demonstrating the opposite of the point.
 *
 * <p><b>Why the step is a count of tool results, and not the fail-closed scan the sibling uses.</b>
 * {@code crash-recovery}'s canned model stops its scan at an unanswered tool call, so an interrupted
 * booking is never asked for twice. That rule is right there and would be wrong here. These three
 * tools are pure (they log and return a string, as {@link EventPlannerTools} documents), so there is
 * no side effect to duplicate; and the interrupted one is step two, whose whole purpose is to be
 * re-entered. After the reader comments out the halt and restarts, the durability layer replays a
 * conversation whose step-two call has no result, and this model must ask for step two again for the
 * run to finish. Counting results does that. Failing closed would answer with step one's output, and
 * the demo would end early having proved nothing.
 *
 * <p><b>{@code stream()} is inherited and left alone.</b> {@code ChatModel}'s default body throws
 * {@code UnsupportedOperationException}, which is right here rather than merely tolerated: the
 * durability layer only ever calls {@link #call(Prompt)}, and a durable activity that streamed would
 * have nothing to record.
 */
public class CannedChatModel implements ChatModel {

  /** Also what the registry reports as this agent's model, via {@link #getOptions()}. */
  static final String MODEL = "canned-offline";

  /**
   * The tools, in the order {@link EventPlannerTools} and the agent's system prompt both give them.
   * The names are the {@code @Tool(name = ...)} values, not the Java method names; a mismatch is a
   * tool-not-found at the first turn.
   */
  static final List<String> STEPS =
      List.of("step_one_search", "step_two_compare", "step_three_confirm");

  /** The {@code @ToolParam} name each step binds, positionally matching {@link #STEPS}. */
  private static final List<String> PARAMETERS = List.of("city", "data", "selection");

  static final String DEFAULT_CITY = "the requested city";

  private static final ObjectMapper JSON = new ObjectMapper();

  /**
   * The city in the user's request, as in "Find a venue in Austin for a company gala".
   *
   * <p>Read back from the message rather than fixed because the README invites the reader to change
   * it and {@code step_one_search} echoes it into its reply, so a hardcoded city would show them a
   * search they did not ask for.
   *
   * <p>Deliberately narrow, and anything it does not match falls back to {@link #DEFAULT_CITY}. A
   * permissive pattern would happily capture half a sentence and put it where the reader expects a
   * city; the fallback still reads correctly in the tool's echoed reply, which pasting the whole
   * prompt in would not.
   */
  private static final Pattern CITY =
      Pattern.compile("\\bin\\s+([A-Z][A-Za-z .'-]{0,40}?)(?=\\s+for\\b|[.,!?]|$)");

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
   * the registry reads back as this agent's per-request tool list. This model ignores the callbacks
   * itself (it names its tools outright), so getting this wrong would not stop the demo — it would
   * quietly shorten what the console reports.
   *
   * <p>The empty callback list is not redundant: every real Spring AI options class returns a list
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
    List<String> results = toolResultsForCurrentQuestion(prompt.getInstructions());
    int step = results.size();
    boolean done = step >= STEPS.size();

    AssistantMessage message;
    if (done) {
      // Every step has run. Answer with what the last one returned, echoed verbatim rather than
      // restated: the tools describe their own outcome ("All steps complete!"), and fixed wording
      // here would drift from them the moment one is edited.
      message = AssistantMessage.builder()
          .content(plainText(results.get(results.size() - 1)))
          .build();
    } else {
      // Ask for the next step, passing the previous step's output as its argument, which is what
      // the tool descriptions ask for ("the venues found in step one", "the selected venue"). Step
      // one takes the city from the question instead, having nothing before it.
      String argument = step == 0 ? city(prompt) : plainText(results.get(step - 1));
      message = AssistantMessage.builder()
          .content("")
          .toolCalls(List.of(new AssistantMessage.ToolCall(
              "call_" + STEPS.get(step), "function", STEPS.get(step),
              toolArguments(step, argument))))
          .build();
    }

    // The workflow loops on whether the generation carries tool calls, not on this string, so the
    // finish reason is reported for fidelity rather than control flow.
    Generation generation = new Generation(message,
        ChatGenerationMetadata.builder().finishReason(done ? "stop" : "tool_calls").build());
    return new ChatResponse(List.of(generation),
        ChatResponseMetadata.builder().model(MODEL).build());
  }

  /**
   * The tool results recorded since the last user message, oldest first.
   *
   * <p>Scoped to the current question so that a second question in one conversation starts the
   * script over instead of replaying the previous answer forever. This app sends one question per
   * conversation, but the sibling {@code durable-memory} quickstart does not.
   *
   * <p>Counted rather than matched by name. Which tool a result belongs to is not needed — the
   * script is fixed and the durability layer records results in call order — and matching on names
   * would make this the second place the tool names live.
   */
  private static List<String> toolResultsForCurrentQuestion(List<Message> messages) {
    int from = 0;
    for (int i = 0; i < messages.size(); i++) {
      if (messages.get(i) instanceof UserMessage) {
        from = i;
      }
    }
    List<String> results = new ArrayList<>();
    for (Message message : messages.subList(from, messages.size())) {
      if (message instanceof ToolResponseMessage tool) {
        tool.getResponses().forEach(response -> results.add(response.responseData()));
      }
    }
    return results;
  }

  /**
   * The next call's arguments as JSON.
   *
   * <p>Built with Jackson rather than concatenated, unlike the {@code crash-recovery} sibling: the
   * arguments here are previous tool results, so their content comes from another component rather
   * than from a pattern this class controls. A quote in one would otherwise produce invalid JSON and
   * fail tool-argument binding with an error pointing nowhere near here.
   */
  private static String toolArguments(int step, String value) {
    ObjectNode node = JSON.createObjectNode();
    node.put(PARAMETERS.get(step), value);
    return node.toString();
  }

  /** The city from the last user message, or {@link #DEFAULT_CITY}. */
  private static String city(Prompt prompt) {
    List<Message> messages = prompt.getInstructions();
    for (int i = messages.size() - 1; i >= 0; i--) {
      if (messages.get(i) instanceof UserMessage user) {
        Matcher matcher = CITY.matcher(user.getText());
        return matcher.find() ? matcher.group(1).trim() : DEFAULT_CITY;
      }
    }
    return DEFAULT_CITY;
  }

  /**
   * A tool result as prose, rather than as the JSON Spring AI wrapped it in.
   *
   * <p>Tool return values are serialised before they re-enter the conversation, so these Strings
   * arrive quoted and escaped. A real model reads that and answers in its own words; this one passes
   * it on, so without decoding the quotes would end up in the next tool's argument and in the
   * {@code response} field the README documents.
   *
   * <p>Anything that is not a JSON string (a tool returning an object, say) is passed through
   * unchanged, which is the most useful thing to show for a result this model knows nothing about.
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
}
