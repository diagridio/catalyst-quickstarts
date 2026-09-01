package io.diagrid.quickstart.springai.crashrecovery;

import java.util.regex.Pattern;

import com.fasterxml.jackson.annotation.JsonProperty;
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
 * The instance id is set per call via {@link DurableAdvisor#INSTANCE_ID_KEY}: that is the attach
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

  /** What a booking reference may contain. Must stay in step with {@link CannedChatModel}. */
  private static final Pattern REFERENCE = Pattern.compile("[A-Za-z0-9_-]{1,64}");

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
  public ResponseEntity<CrashRunResponse> run(@RequestBody CrashRunRequest request) {
    String id = request.id();
    if (id == null || id.isBlank()) {
      return ResponseEntity.badRequest().body(new CrashRunResponse(id, null, "id is required"));
    }

    String reference = request.reference() == null ? "ABC123" : request.reference();
    // Rejected rather than sanitised, because the reference is the demo's subject: the confirmation
    // code is derived from it, and the README sells that code as proof the booking was not redone.
    // The offline model reads the reference back out of the user message below with a character
    // class narrow enough that nothing can break the JSON tool arguments it builds, and anything
    // outside that class would silently fall back to ABC123 — committing a different booking than
    // the caller asked for and reporting success for it. Better to say so.
    if (!REFERENCE.matcher(reference).matches()) {
      return ResponseEntity.badRequest().body(new CrashRunResponse(id, null,
          "reference must be 1-64 characters from A-Z a-z 0-9 _ -"));
    }
    // Recorded before the blocking call below, because that call does not return until the run
    // finishes: recording after it would be recording for a run that is already over. Recording
    // only, though. The timer starts inside the tool, which is the one place that runs on a first
    // execution and not on an attach. See SlowBookingTools#noteSelfKill for why that matters:
    // arming here fired on every call, including the re-issue the 202 below asks for.
    //
    // Recorded on EVERY call, and a call without the field records 0, which DISARMS. That clear is
    // load-bearing, not tidiness. This sample cannot tell a scheduling call from an attaching one,
    // so an attaching call records the field and then never runs the tool that would consume it.
    // Without the clear the value survived to the next run and killed an app that had never asked
    // for it, which a smoke test caught doing exactly that.
    Integer killAfter = request.killAfterSeconds();
    SlowBookingTools.noteSelfKill(killAfter != null && killAfter > 0 ? killAfter : 0);
    try {
      String answer = agent.prompt()
          .user("Confirm the booking with reference " + reference + ".")
          .advisors(a -> a.param(DurableAdvisor.INSTANCE_ID_KEY, id))
          .call()
          .content();
      return ResponseEntity.ok(new CrashRunResponse(id, answer, null));
    } catch (DurableCallTimeoutException e) {
      // Wait budget elapsed (not a failure): the run is still going. Re-issue the same call with the
      // same id to attach and collect the result.
      return ResponseEntity.accepted().body(new CrashRunResponse(e.instanceId(), null,
          "still running as " + e.instanceId() + ", re-issue POST /crash/run with the same id to attach"));
    } catch (Exception e) {
      LOG.error("Error running the crash-recovery booking {}: {}", id, e.getMessage());
      return ResponseEntity.status(500).body(new CrashRunResponse(id, null, e.getMessage()));
    }
  }

  /**
   * Request body of {@code POST /crash/run}. A null reference falls back to ABC123, and one outside
   * {@code [A-Za-z0-9_-]{1,64}} is a 400.
   *
   * <p>{@code kill_after_seconds} is optional. Send it and the app crashes itself that many
   * seconds in, so the whole demo runs in two terminals with no window to aim at; leave it out
   * and nothing changes, and you crash the app yourself from a second terminal with
   * {@code POST /crash/kill}.
   *
   * <p>Safe to send on any call, including a re-issue. Unlike the workflow quickstarts, this sample
   * cannot tell a scheduling call from an attaching one: the instance id goes to
   * {@link DurableAdvisor} and the agent call blocks, so there is no state lookup to branch on.
   * Rather than branch, the field is only recorded here and the timer starts inside the durable
   * tool, which runs on a first execution and not on an attach. See
   * {@link SlowBookingTools#noteSelfKill(int)}.
   */
  public record CrashRunRequest(
      String id,
      String reference,
      @JsonProperty("kill_after_seconds") Integer killAfterSeconds) {
  }

  /**
   * Response body of {@code POST /crash/run}, and the one shape every crash demo in this repo
   * returns. All three fields are always present: a 200 carries {@code result}, while a 202, a 400
   * and a 500 carry {@code message} instead.
   */
  public record CrashRunResponse(String id, String result, String message) {
  }

  /** Simulate a crash: halt the JVM abruptly (skips shutdown hooks), like SIGKILL. Demo only. */
  @PostMapping("/crash/kill")
  public void kill() {
    LOG.warn(">>> /crash/kill: halting the JVM to simulate a worker crash");
    Runtime.getRuntime().halt(137);
  }
}
