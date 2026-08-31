package io.diagrid.quickstart.springai.crashrecovery;

import java.util.concurrent.atomic.AtomicInteger;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * A deliberately slow booking tool that opens a window for the crash-recovery demo.
 *
 * <p><b>Why a {@code @Tool} Spring bean</b> (not a per-call {@code .defaultTools(new SlowBookingTools())}):
 * the durability layer rediscovers {@code @Tool} beans at startup, so after the app is killed mid-tool
 * the tool is re-registered on the fresh worker and the resumed activity can run it. A request-scoped
 * tool attached per call is registered in memory at call time and is NOT re-registered after a cold
 * restart: the resumed activity would fail to resolve it.
 *
 * <p>The tool runs as a durable activity: it logs a start marker, sleeps for {@code delaySeconds}, then
 * logs a commit marker and returns a confirmation code. The sleep is the window in which you SIGKILL
 * the app (see {@link CrashRecoveryController}). Killing there interrupts this activity mid-flight; on
 * restart the durable runtime re-runs this (incomplete) activity from the start, while NOT re-running
 * any activity that already completed before the crash. The confirmation code is derived from the
 * reference, so a re-attached call returns the <em>same</em> code, visible proof the booking was not
 * redone.
 */
@Component
public class SlowBookingTools {

  private static final Logger LOG = LoggerFactory.getLogger(SlowBookingTools.class);

  /**
   * Seconds into THIS TOOL's run at which the app should kill itself, or 0 when nothing is asked
   * for. Set by {@link #noteSelfKill(int)} on the request thread, read and acted on by
   * {@code commitReservation} on the workflow worker thread.
   *
   * <p>Static because the writer is {@link CrashRecoveryController} and the reader is this tool,
   * and one armed kill takes the whole JVM down, so there is nothing to key by run. The fresh
   * process after the restart starts at 0 again, which is what makes the replay safe: the resumed
   * activity re-runs this tool from the start, and it must not arm a second kill when it does.
   *
   * <p>An AtomicInteger because the tool CONSUMES it: {@code getAndSet(0)} reads the value and
   * clears it in one step, so one recorded request arms exactly one execution. Leaving it set was a
   * real bug. A call that attaches records the field but never runs the tool, so the value survived
   * to the next run in the same process and killed an app that had never asked for it. 0 is
   * unambiguous as "not armed" because the record site already rejects a non-positive value.
   */
  private static final AtomicInteger selfKillSeconds = new AtomicInteger();

  private final int delaySeconds;

  public SlowBookingTools(@Value("${crash-recovery.delay-seconds:30}") int delaySeconds) {
    this.delaySeconds = delaySeconds;
  }

  /**
   * Record how far into the tool this process should kill itself, for {@code commitReservation} to
   * act on when it actually runs. Recording only: no timer starts here. Pass 0 to disarm.
   *
   * <p>Every call to {@code /crash/run} records, and one without {@code kill_after_seconds} records
   * 0. That clear is load-bearing: an attaching call records the field and then never runs the tool
   * that would consume it, so without it the value survived to the next run in the same process and
   * killed an app that had never asked for it.
   *
   * <p>The timer starts inside the tool rather than at the request, and that is what makes
   * {@code kill_after_seconds} safe to send on any call. Unlike the workflow quickstarts this
   * sample cannot tell a scheduling call from an attaching one: the instance id goes to
   * {@code DurableAdvisor} and the agent call blocks, so there is no state lookup to branch on.
   * Arming at the request therefore fired on every call, and a re-issue (which the 202 body, and
   * the README's collect step, both tell the reader to send) killed the app again before it could
   * hand back the answer. The tool is a durable activity, so it is the one thing that runs on a
   * genuine first execution and NOT on an attach: an attach to a finished run replays the recorded
   * result instead of re-invoking it, and an attach to a run still in flight does not re-enter it.
   *
   * <p>It also fixes the clock. Arming at the request meant the budget had to cover the LLM turn
   * that precedes the tool, so a slow provider halted the app before any activity had completed and
   * the replay had nothing to show. Measured from inside the tool, the budget runs against this
   * tool's own sleep.
   */
  public static void noteSelfKill(int delaySeconds) {
    selfKillSeconds.set(delaySeconds);
  }

  /**
   * Halt the JVM {@code delaySeconds} from now, on a daemon thread.
   *
   * <p>What lets the demo run in two terminals instead of three. {@code /crash/run} blocks for the
   * length of this tool, so the shell that starts a run cannot also stop the app, and the kill has
   * always needed a terminal of its own. Arming it here removes that terminal AND the race: the
   * crash lands at a known point inside the window rather than wherever the reader's reflexes put
   * it.
   *
   * <p>The same {@code halt(137)} that {@code /crash/kill} uses, deliberately: halt skips the
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
      LOG.warn(">>> crash: halting the JVM {}s into the run, as asked by kill_after_seconds",
          delaySeconds);
      Runtime.getRuntime().halt(137);
    }, "crash-self-kill");
    timer.setDaemon(true);
    timer.start();
  }

  @Tool(name = "commitReservation",
      description = "Commit a travel reservation with the provider and return a confirmation code")
  public String commitReservation(@ToolParam(description = "the booking reference") String reference) {
    // Two messages, because the reader's next move differs. Un-armed, the window is theirs to aim
    // at and they have to crash the app themselves. Armed, the app does that for them at a known
    // point, so the instruction would be wrong and the ~delay would be read as the wait.
    //
    // Read AND clear in one step, so one recorded request arms exactly one execution. A call that
    // attaches records the field but never gets here, and leaving the value set let it leak into
    // the next run in the same process and kill an app that had never asked for it.
    int armed = selfKillSeconds.getAndSet(0);
    if (armed > 0) {
      LOG.warn(">>> commitReservation({}): committing over ~{}s, but this process kills itself {}s"
          + " into the run, as asked by kill_after_seconds. It resumes on restart.",
          reference, delaySeconds, armed);
      // Armed here, at the point the tool actually starts, and not at the request. See
      // noteSelfKill: this is the only site that runs on a genuine first execution and not on an
      // attach, and the fresh JVM's 0 is what stops the resumed activity arming a second kill.
      armSelfKill(armed);
    } else {
      LOG.warn(">>> commitReservation({}): committing over ~{}s. KILL THE APP NOW to test crash"
          + " recovery (POST /crash/kill, or kill -9). It resumes on restart.",
          reference, delaySeconds);
    }
    try {
      Thread.sleep(delaySeconds * 1000L);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException("commitReservation interrupted", e);
    }
    String code = "BK-" + Integer.toHexString(reference.hashCode()).toUpperCase();
    LOG.info(">>> commitReservation({}): committed. Confirmation code: {}", reference, code);
    return "Booking " + reference + " confirmed. Confirmation code: " + code;
  }
}
