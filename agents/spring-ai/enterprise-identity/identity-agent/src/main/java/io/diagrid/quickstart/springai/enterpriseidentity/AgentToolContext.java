package io.diagrid.quickstart.springai.enterpriseidentity;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.ai.chat.model.ToolContext;

/**
 * The channel between the HTTP handler and the tools: Spring AI's tool context. It is filled in by
 * the application from a verified credential and passed to the tool unchanged, so the model never
 * sees it and cannot rewrite it — unlike a message or a tool argument.
 */
final class AgentToolContext {

  /** The verified caller's subject, as the tools read it. */
  static final String USER_SUBJECT = "user_subject";

  /** The tools' answers, in call order: {@code call().content()} returns only the final message. */
  static final String TRANSCRIPT = "transcript";

  private AgentToolContext() {
  }

  static Map<String, Object> forCaller(String subject) {
    Map<String, Object> context = new HashMap<>();
    context.put(USER_SUBJECT, subject);
    // Synchronised: one run may call several tools, and Spring AI may run them on several threads.
    context.put(TRANSCRIPT, Collections.synchronizedList(new ArrayList<String>()));
    return context;
  }

  /**
   * The verified subject in the given context, or the empty string when there is none — never the
   * tool's own {@code subject} argument, so a run without a verified caller answers for nobody.
   */
  static String verifiedSubject(ToolContext context) {
    Object subject = context == null ? null : context.getContext().get(USER_SUBJECT);
    return subject instanceof String text ? text : "";
  }

  static void record(ToolContext context, String answer) {
    transcriptOf(context == null ? Map.of() : context.getContext()).add(answer);
  }

  @SuppressWarnings("unchecked")
  static List<String> transcriptOf(Map<String, Object> context) {
    Object transcript = context.get(TRANSCRIPT);
    // A context not built by forCaller has no transcript, so its answers are discarded.
    return transcript instanceof List
        ? (List<String>) transcript
        : Collections.synchronizedList(new ArrayList<>());
  }
}
