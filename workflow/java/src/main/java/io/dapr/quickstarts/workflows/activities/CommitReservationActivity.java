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

  /**
   * Seconds into the run at which {@code POST /crash/run} has armed the app to kill itself, or 0
   * when nothing is armed. Set by {@link #noteSelfKill(int)} and read only to compose the log line
   * in {@link #run}, which has to name the wait the reader actually gets: with a self-kill armed
   * this activity never reaches the end of its sleep, so announcing that sleep on its own puts a
   * number in the log that nothing honours.
   *
   * <p>Static because the writer is a request handler in {@code WorkflowApp} and the reader is this
   * activity, and one armed kill takes the whole JVM down, so there is nothing to key by instance.
   * The fresh process after the restart starts at 0 again, which is right: nothing is armed on the
   * replay.
   *
   * <p>volatile, and an int rather than an Integer: the write happens on a request thread and the
   * read on a workflow worker thread. 0 is unambiguous as "not armed" because the arm site already
   * rejects a non-positive value.
   */
  private static volatile int selfKillSeconds;

  private final int delaySeconds;

  public CommitReservationActivity(@Value("${CRASH_DELAY_SECONDS:30}") int delaySeconds) {
    this.delaySeconds = delaySeconds;
  }

  /**
   * Record that this process will kill itself, so {@link #run} can say so.
   *
   * <p>Called just after the schedule, and this activity cannot normally log before that: the
   * worker has to be handed the work item and run the fast activity first. If it ever did win the
   * race the line would read as though nothing were armed, which is a stale message rather than a
   * broken demo.
   */
  public static void noteSelfKill(int delaySeconds) {
    selfKillSeconds = delaySeconds;
  }

  @Override
  public Object run(WorkflowActivityContext ctx) {
    String reference = ctx.getInput(String.class);
    // Two messages, because the reader's next move differs. Un-armed, the window is theirs to aim
    // at and they have to crash the app themselves. Armed, the app does that for them at a known
    // point, so the instruction would be wrong and the ~delay would be read as the wait.
    int armed = selfKillSeconds;
    if (armed > 0) {
      logger.info("Committing reservation {} over ~{}s, but this process kills itself {}s into the"
          + " run, as asked by kill_after_seconds. It resumes on restart.",
          reference, delaySeconds, armed);
    } else {
      logger.info("Committing reservation {} over ~{}s. KILL THE APP NOW to test crash recovery"
          + " (POST /crash/kill, or kill -9). It resumes on restart.", reference, delaySeconds);
    }

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
