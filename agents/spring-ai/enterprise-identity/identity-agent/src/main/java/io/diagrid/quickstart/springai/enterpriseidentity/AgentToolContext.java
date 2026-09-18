package io.diagrid.quickstart.springai.enterpriseidentity;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.ai.chat.model.ToolContext;

/**
 * The channel between the HTTP handler and the tools: Spring AI's tool context.
 *
 * <p>This is the Java counterpart of LangGraph's
 * {@code config={"configurable": {"user_subject": ...}}}, and the key name is kept so the two
 * quickstarts read as one family. What matters is not the name but the direction: the tool context
 * is filled in by the application from a verified credential and handed to Spring AI, which passes
 * it to the tool unchanged. The model never sees it and cannot rewrite it — unlike a message or a
 * tool argument, which is exactly what {@link BookingTools} substitutes over.
 */
final class AgentToolContext {

  /** The verified caller's subject, as the tools read it. */
  static final String USER_SUBJECT = "user_subject";

  /**
   * The tools' own answers, in call order, so {@code POST /agent/run} can show the conversation.
   *
   * <p>Needed because {@code ChatClient.call().content()} returns only the final assistant message:
   * Spring AI runs the tool calls inside the call, so the intermediate tool results are not
   * available to the caller the way LangGraph's replayed message history makes them. Carrying a
   * mutable list through the tool context is the app's own channel for them, which doubles as a
   * demonstration that the tool context belongs to the application.
   */
  static final String TRANSCRIPT = "transcript";

  private AgentToolContext() {
  }

  /** The tool context for one run on behalf of {@code subject}, with an empty transcript. */
  static Map<String, Object> forCaller(String subject) {
    Map<String, Object> context = new HashMap<>();
    context.put(USER_SUBJECT, subject);
    // Synchronised because a single run may call several tools, and Spring AI is free to run them
    // on more than one thread.
    context.put(TRANSCRIPT, Collections.synchronizedList(new ArrayList<String>()));
    return context;
  }

  /**
   * The verified subject in the given context, or the empty string when there is none.
   *
   * <p>Empty rather than the tool's own {@code subject} argument on purpose: a run invoked without a
   * verified caller must answer for nobody, not for whoever the model guessed. See
   * {@link BookingTools}.
   */
  static String verifiedSubject(ToolContext context) {
    Object subject = context == null ? null : context.getContext().get(USER_SUBJECT);
    return subject instanceof String text ? text : "";
  }

  /** Records a tool's answer so the handler can report it. */
  static void record(ToolContext context, String answer) {
    transcriptOf(context == null ? Map.of() : context.getContext()).add(answer);
  }

  /** The answers recorded so far, in call order. */
  @SuppressWarnings("unchecked")
  static List<String> transcriptOf(Map<String, Object> context) {
    Object transcript = context.get(TRANSCRIPT);
    // A context built by anything other than forCaller carries no transcript — the direct-tool
    // tests, for instance. Discarding their answers beats making every tool null-check.
    return transcript instanceof List
        ? (List<String>) transcript
        : Collections.synchronizedList(new ArrayList<>());
  }
}
