package io.diagrid.quickstart.springai.durablememory;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * A deliberately slow booking tool that opens a window to crash the app mid-call — long enough that
 * the durable call is still in flight and the memory advisor's response phase has not yet run.
 *
 * <p>It is a {@code @Tool} Spring bean so it is rediscovered on a restarted worker and the resumed
 * activity can run it (a per-call tool would be gone after a cold restart). It runs as a durable
 * activity: logs a start marker, sleeps for {@code delaySeconds}, then returns a confirmation code
 * derived from the reference (so a re-attached call returns the same code).
 */
@Component
public class SlowBookingTools {

  private static final Logger LOG = LoggerFactory.getLogger(SlowBookingTools.class);

  private final int delaySeconds;

  public SlowBookingTools(@Value("${crash-recovery.delay-seconds:30}") int delaySeconds) {
    this.delaySeconds = delaySeconds;
  }

  @Tool(name = "commitReservation",
      description = "Commit a travel reservation with the provider and return a confirmation code")
  public String commitReservation(@ToolParam(description = "the booking reference") String reference) {
    LOG.warn(">>> commitReservation({}) — committing over ~{}s. KILL THE APP NOW to test crash"
        + " recovery (POST /crash/kill, or kill -9). It resumes on restart.", reference, delaySeconds);
    try {
      Thread.sleep(delaySeconds * 1000L);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException("commitReservation interrupted", e);
    }
    String code = "BK-" + Integer.toHexString(reference.hashCode()).toUpperCase();
    LOG.info(">>> commitReservation({}) — committed. Confirmation code: {}", reference, code);
    return "Booking " + reference + " confirmed. Confirmation code: " + code;
  }
}
