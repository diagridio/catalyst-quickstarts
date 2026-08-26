package io.dapr.quickstarts.workflows.activities;

import io.dapr.workflows.WorkflowActivity;
import io.dapr.workflows.WorkflowActivityContext;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * A deliberately slow activity that opens the window for the crash-recovery demo.
 *
 * <p>It logs a start marker, sleeps for {@code CRASH_DELAY_SECONDS} (30 by default), then logs a
 * commit marker and returns a confirmation code. The sleep is where you kill the app. Killing there
 * interrupts this activity mid-flight; on restart the durable runtime re-runs this incomplete
 * activity from the start while NOT re-running any activity that completed before the crash.
 *
 * <p>The confirmation code is derived only from the booking reference, so a re-issued call returns
 * the <em>same</em> code. That is the visible proof the reservation was not made twice.
 */
@Component
public class CommitReservationActivity implements WorkflowActivity {

  private static final Logger logger = LoggerFactory.getLogger(CommitReservationActivity.class);

  private final int delaySeconds;

  public CommitReservationActivity(@Value("${CRASH_DELAY_SECONDS:30}") int delaySeconds) {
    this.delaySeconds = delaySeconds;
  }

  @Override
  public Object run(WorkflowActivityContext ctx) {
    String reference = ctx.getInput(String.class);
    logger.info("Committing reservation {} over ~{}s. KILL THE APP NOW to test crash recovery"
        + " (POST /crash/kill, or kill -9). It resumes on restart.", reference, delaySeconds);

    try {
      Thread.sleep(delaySeconds * 1000L);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException("Committing reservation " + reference + " was interrupted", e);
    }

    String code = confirmationCode(reference);
    logger.info("Committed reservation {}. Confirmation code: {}", reference, code);
    return "Reservation " + reference + " confirmed. Confirmation code: " + code;
  }

  /**
   * A confirmation code that is a pure function of the booking reference.
   *
   * <p>SHA-256 rather than {@code reference.hashCode()}: the sibling Python and C# quickstarts
   * cannot use their built-in string hash here, because both randomise it per process and the code
   * would change across the restart. Using the same construction in all three keeps the three
   * walkthroughs comparable.
   */
  private static String confirmationCode(String reference) {
    try {
      byte[] digest = MessageDigest.getInstance("SHA-256")
          .digest(reference.getBytes(StandardCharsets.UTF_8));
      return "BK-" + HexFormat.of().withUpperCase().formatHex(digest, 0, 4);
    } catch (NoSuchAlgorithmException e) {
      // Every JVM is required to ship SHA-256, so this cannot happen.
      throw new IllegalStateException("SHA-256 is unavailable", e);
    }
  }
}
