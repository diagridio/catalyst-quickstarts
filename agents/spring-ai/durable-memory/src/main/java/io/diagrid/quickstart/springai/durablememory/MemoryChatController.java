package io.diagrid.quickstart.springai.durablememory;

import io.diagrid.dapr.springai.durable.boot.DurableAdvisor;
import io.diagrid.dapr.springai.durable.client.DurableCallTimeoutException;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Durable chat with memory — the point of this quickstart is <b>what durability does and does not
 * cover</b> when Spring AI runs advisors synchronously.
 *
 * <p>The {@link MessageChatMemoryAdvisor} is a response advisor: it runs its {@code before} phase on
 * the caller thread (retrieve history, add the <b>user</b> message to memory), then the durable call
 * runs as a Dapr Workflow, then it runs its {@code after} phase on the caller thread (add the
 * <b>assistant</b> reply to memory). The {@code after} phase — like every advisor's response phase —
 * only runs if the durable call <b>returns successfully</b>.
 *
 * <p>So the durable workflow (model + tools) survives a crash, but the assistant reply is persisted to
 * memory only on a successful call. Crash mid-call and the conversation keeps the question (saved in
 * {@code before}) but not the answer; re-issue the same instance id, the call attaches and succeeds,
 * and only then does the memory advisor record the answer.
 */
@RestController
public class MemoryChatController {

  private static final Logger LOG = LoggerFactory.getLogger(MemoryChatController.class);

  private static final String SYSTEM = """
      You are a booking assistant that remembers the conversation. When the user asks to book,
      call the commitReservation tool exactly once and report the confirmation code it returns.
      Refer back to details the user shared earlier in this conversation.""";

  private final ChatClient chat;
  private final ChatMemory chatMemory;

  public MemoryChatController(ChatClient.Builder builder, ChatMemory chatMemory) {
    this.chatMemory = chatMemory;
    this.chat =
        builder
            .defaultSystem(SYSTEM)
            .defaultAdvisors(MessageChatMemoryAdvisor.builder(chatMemory).build())
            .build();
  }

  /**
   * One durable turn under a caller-owned instance {@code id} (so a repeat attaches on recovery) and a
   * {@code conversationId} (chat-memory grouping). Blocks on the slow booking tool — the crash window.
   */
  @PostMapping("/chat")
  public ResponseEntity<String> chat(
      @RequestParam String id,
      @RequestParam String conversationId,
      @RequestParam String message) {
    try {
      String answer =
          chat.prompt()
              .user(message)
              .advisors(
                  a ->
                      a.param(DurableAdvisor.INSTANCE_ID_KEY, id)
                          .param(ChatMemory.CONVERSATION_ID, conversationId))
              .call()
              .content();
      return ResponseEntity.ok(answer + "\n");
    } catch (DurableCallTimeoutException e) {
      // Wait budget elapsed (not a failure): the workflow is still running, so the memory advisor's
      // response phase has NOT run yet. Re-issue the same id to attach, succeed, and persist the reply.
      return ResponseEntity.accepted()
          .body("still running as " + e.instanceId()
              + " — re-issue POST /chat with the same id to attach and persist the answer\n");
    }
  }

  /**
   * Dump what the memory advisor has persisted for a conversation — the observable proof. After a
   * crash you see the USER question (saved in {@code before}) but no ASSISTANT answer; after a
   * successful re-attach the ASSISTANT answer appears.
   */
  @GetMapping("/history")
  public List<String> history(@RequestParam String conversationId) {
    return chatMemory.get(conversationId).stream()
        .map(m -> m.getMessageType() + ": " + m.getText())
        .toList();
  }

  /** Simulate a crash: halt the JVM abruptly (skips shutdown hooks), like SIGKILL. Demo only. */
  @PostMapping("/crash/kill")
  public void kill() {
    LOG.warn(">>> /crash/kill — halting the JVM to simulate a worker crash");
    Runtime.getRuntime().halt(137);
  }
}
