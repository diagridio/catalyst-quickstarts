package io.diagrid.quickstart.springai.crashrecovery;

import io.diagrid.dapr.springai.durable.boot.DurableAdvisor;
import io.diagrid.dapr.springai.durable.client.DurableCallTimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Crash-recovery demo: prove a durable {@code ChatClient.call()} survives a hard kill of the app
 * (which also hosts the in-process workflow worker), and that re-issuing the SAME call with the SAME
 * instance id attaches to the resumed run instead of starting a second booking.
 *
 * <p>Uses the named {@code crashRecoveryAgent} ChatClient bean (see {@link CrashRecoveryAgentConfig}),
 * so the run appears under the per-agent workflow name {@code spring-ai.crashRecoveryAgent.workflow}.
 * The instance id is set per call via {@link DurableAdvisor#INSTANCE_ID_KEY} — that is the attach
 * handle a repeat call re-uses.
 *
 * <pre>
 * # 1. Terminal A — book under an id YOU own. Blocks ~30s while the slow tool "commits".
 * curl "http://localhost:8080/crash/book?id=trip-42&amp;reference=ABC123"
 * # 2. Terminal B — during that window, SIGKILL the app (worker + blocked caller both die):
 * curl -X POST "http://localhost:8080/crash/kill"
 * # 3. Restart the app. The durable runtime resumes instance trip-42.
 * # 4. Terminal A — re-issue the SAME call. It ATTACHES and returns the same confirmation:
 * curl "http://localhost:8080/crash/book?id=trip-42&amp;reference=ABC123"
 * </pre>
 */
@RestController
public class CrashRecoveryController {

  private static final Logger LOG = LoggerFactory.getLogger(CrashRecoveryController.class);

  private final ChatClient agent;

  public CrashRecoveryController(@Qualifier("crashRecoveryAgent") ChatClient agent) {
    this.agent = agent;
  }

  /** Book under a caller-chosen id; a repeat with the same id attaches to the existing run. */
  @GetMapping("/crash/book")
  public ResponseEntity<String> book(
      @RequestParam String id, @RequestParam(defaultValue = "ABC123") String reference) {
    try {
      String answer = agent.prompt()
          .user("Confirm the booking with reference " + reference + ".")
          .advisors(a -> a.param(DurableAdvisor.INSTANCE_ID_KEY, id))
          .call()
          .content();
      return ResponseEntity.ok(answer + "\n");
    } catch (DurableCallTimeoutException e) {
      // Wait budget elapsed (not a failure): the run is still going. Re-issue the same call with the
      // same id to attach and collect the result.
      return ResponseEntity.accepted()
          .body("still running as " + e.instanceId()
              + " — re-issue GET /crash/book?id=" + id + " to attach\n");
    }
  }

  /** Simulate a crash: halt the JVM abruptly (skips shutdown hooks), like SIGKILL. Demo only. */
  @PostMapping("/crash/kill")
  public void kill() {
    LOG.warn(">>> /crash/kill — halting the JVM to simulate a worker crash");
    Runtime.getRuntime().halt(137);
  }
}
