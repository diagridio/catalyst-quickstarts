package io.diagrid.quickstart.springai.crashrecovery;

import io.diagrid.springai.durable.boot.DurableAdvisor;
import io.diagrid.springai.durable.client.DurableCallTimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
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
 * # 1. Terminal A: book under an id YOU own. Blocks ~30s while the slow tool "commits".
 * curl -X POST "http://localhost:8080/crash/run" -H "Content-Type: application/json" \
 *   -d '{"id":"trip-42","reference":"ABC123"}'
 * # 2. Terminal B: during that window, SIGKILL the app (worker and blocked caller both die):
 * curl -X POST "http://localhost:8080/crash/kill"
 * # 3. Restart the app. The durable runtime resumes instance trip-42.
 * # 4. Terminal A: re-issue the SAME call. It ATTACHES and returns the same confirmation:
 * curl -X POST "http://localhost:8080/crash/run" -H "Content-Type: application/json" \
 *   -d '{"id":"trip-42","reference":"ABC123"}'
 * </pre>
 */
@RestController
public class CrashRecoveryController {

  private static final Logger LOG = LoggerFactory.getLogger(CrashRecoveryController.class);

  private final ChatClient agent;

  public CrashRecoveryController(@Qualifier("crashRecoveryAgent") ChatClient agent) {
    this.agent = agent;
  }

  /**
   * Book under a caller-chosen id; a repeat with the same id attaches to the existing run.
   *
   * <p>POST with a JSON body rather than GET with query params, so that this demo and the crash
   * demos in the workflow quickstarts present one command shape rather than two.
   */
  @PostMapping("/crash/run")
  public ResponseEntity<String> run(@RequestBody CrashRunRequest request) {
    String id = request.id();
    String reference = request.reference() == null ? "ABC123" : request.reference();
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
              + ", re-issue POST /crash/run with the same id to attach\n");
    }
  }

  /** Request body of {@code POST /crash/run}. A null reference falls back to ABC123. */
  public record CrashRunRequest(String id, String reference) {
  }

  /** Simulate a crash: halt the JVM abruptly (skips shutdown hooks), like SIGKILL. Demo only. */
  @PostMapping("/crash/kill")
  public void kill() {
    LOG.warn(">>> /crash/kill — halting the JVM to simulate a worker crash");
    Runtime.getRuntime().halt(137);
  }
}
