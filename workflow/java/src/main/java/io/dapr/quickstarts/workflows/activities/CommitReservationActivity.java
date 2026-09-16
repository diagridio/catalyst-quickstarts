package io.dapr.quickstarts.workflows.activities;

import io.dapr.workflows.WorkflowActivity;
import io.dapr.workflows.WorkflowActivityContext;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.concurrent.atomic.AtomicInteger;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * A deliberately slow activity that opens the window for the crash-recovery demo.
 *
 * <p>It logs a start marker, sleeps for {@code CRASH_DELAY_SECONDS} (10 by default), then logs a
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
   * Seconds into THIS ACTIVITY's run at which the app should kill itself, or 0 when nothing is
   * asked for. Recorded by the {@code /crash/run} handler in {@code WorkflowApp}, then read and
   * acted on here.
   *
   * <p>Static because the writer is a request handler and the reader is this activity, and one
   * armed kill takes the whole JVM down, so there is nothing to key by instance. The fresh process
   * after the restart starts at 0 again, which is what makes the replay safe: the resumed activity
   * re-runs this from the start and must not arm a second kill when it does.
   *
   * <p>An AtomicInteger because the activity CONSUMES it: {@code getAndSet(0)} reads the value and
   * clears it in one step, so one recorded request arms exactly one execution. 0 is unambiguous as
   * "not armed" because the record site already rejects a non-positive value.
   */
  private static final AtomicInteger selfKillSeconds = new AtomicInteger();

  private final int delaySeconds;

  public CommitReservationActivity(@Value("${CRASH_DELAY_SECONDS:10}") int delaySeconds) {
    this.delaySeconds = delaySeconds;
  }

  /**
   * Record how far into this activity the JVM should halt itself, for {@link #run} to act on when
   * it actually runs. Recording only: no timer starts here. Pass 0 to disarm.
   */
  public static void noteSelfKill(int delaySeconds) {
    selfKillSeconds.set(delaySeconds);
  }

  /**
   * Halt the JVM {@code delaySeconds} from now, on a daemon thread.
   *
   * <p>Armed HERE, at the point this activity actually starts, and not back at the request. The
   * request handler cannot start this clock honestly: between the schedule call and this activity
   * sit the dispatch round-trip and the whole fast activity, so a budget measured from the request
   * has to cover work the reader cannot see or predict. Measured from here it runs against this
   * activity's own sleep, which is the window the README tells them to aim at. That is also what
   * makes the field safe to send on a re-issue: an attaching call never reaches this line.
   *
   * <p>Deliberately the same {@code halt(137)} that {@code /crash/kill} uses: halt skips the
   * shutdown hooks, so this is an abrupt crash rather than a controlled one wearing a crash's name.
   *
   * <p>A daemon thread so the timer can never hold the JVM open if the reader Ctrl+Cs during the
   * countdown.
   */
  private static void armSelfKill(int delaySeconds) {
    Thread timer = new Thread(() -> {
      try {
        Thread.sleep(delaySeconds * 1000L);
      } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        return;
      }
      logger.warn(">>> crash: halting the JVM {}s into the run, as asked by kill_after_seconds",
          delaySeconds);
      Runtime.getRuntime().halt(137);
    }, "crash-self-kill");
    timer.setDaemon(true);
    timer.start();
  }

  @Override
  public Object run(WorkflowActivityContext ctx) {
    String reference = ctx.getInput(String.class);
    // Read AND clear in one step, so one recorded request arms exactly one execution. A call that
    // attaches records the field but never gets here, and leaving the value set would let it leak
    // into the next run in the same process and kill an app that had never asked for it.
    int armed = selfKillSeconds.getAndSet(0);
    // Two messages, because the reader's next move differs. Un-armed, the window is theirs to aim
    // at and they have to crash the app themselves. Armed, the app does that for them at a known
    // point, so the instruction would be wrong and the ~delay would be read as the wait.
    if (armed > 0) {
      logger.info("Committing reservation {} over ~{}s, but this process kills itself {}s into the"
          + " run, as asked by kill_after_seconds. It resumes on restart.",
          reference, delaySeconds, armed);
      armSelfKill(armed);
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
