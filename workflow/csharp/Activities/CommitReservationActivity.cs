namespace WorkflowApp.Activities
{
    using System;
    using System.Security.Cryptography;
    using System.Text;
    using System.Threading.Tasks;
    using Dapr.Workflow;
    using Microsoft.Extensions.Logging;

    /// <summary>
    /// A deliberately slow activity that opens the window for the crash-recovery demo.
    ///
    /// It logs a start marker, waits for CRASH_DELAY_SECONDS (30 by default), then logs a commit
    /// marker and returns a confirmation code. The wait is where you kill the app. Killing there
    /// interrupts this activity mid-flight; on restart the durable runtime re-runs this incomplete
    /// activity from the start while NOT re-running any activity that completed before the crash.
    ///
    /// The confirmation code is derived only from the booking reference, so a re-issued call
    /// returns the same code. That is the visible proof the reservation was not made twice.
    /// </summary>
    public class CommitReservationActivity : WorkflowActivity<string, string>
    {
        /// <summary>
        /// Seconds into the run at which POST /crash/run has armed the app to kill itself, or 0
        /// when nothing is armed. Set by NoteSelfKill and read only to compose the log line in
        /// RunAsync, which has to name the wait the reader actually gets: with a self-kill armed
        /// this activity never reaches the end of its delay, so announcing that delay on its own
        /// puts a number in the log that nothing honours.
        ///
        /// Static because the writer is a request handler in Program.cs and the reader is this
        /// activity, and one armed kill takes the whole process down, so there is nothing to key
        /// by instance. The fresh process after the restart starts at 0 again, which is right:
        /// nothing is armed on the replay.
        ///
        /// volatile, and an int rather than an int?: the write happens on a request thread and
        /// the read on a workflow worker thread, and a single int cannot be read half-written the
        /// way a nullable struct's two fields can. 0 is unambiguous as "not armed" because the
        /// arm site already rejects a non-positive value.
        /// </summary>
        static volatile int selfKillSeconds;

        readonly ILogger logger;
        readonly int delaySeconds;

        public CommitReservationActivity(ILoggerFactory loggerFactory)
        {
            this.logger = loggerFactory.CreateLogger<CommitReservationActivity>();
            this.delaySeconds = int.TryParse(
                Environment.GetEnvironmentVariable("CRASH_DELAY_SECONDS"), out var seconds)
                ? seconds
                : 30;
        }

        /// <summary>
        /// Record that this process will kill itself, so RunAsync can say so.
        ///
        /// Called just after the schedule, and this activity cannot normally log before that: the
        /// worker has to be handed the work item and run the fast activity first. If it ever did
        /// win the race the line would read as though nothing were armed, which is a stale
        /// message rather than a broken demo.
        /// </summary>
        public static void NoteSelfKill(int delaySeconds) => selfKillSeconds = delaySeconds;

        public override async Task<string> RunAsync(WorkflowActivityContext context, string reference)
        {
            // Two messages, because the reader's next move differs. Un-armed, the window is
            // theirs to aim at and they have to crash the app themselves. Armed, the app does
            // that for them at a known point, so the instruction would be wrong and the ~delay
            // would be read as the wait.
            var armed = selfKillSeconds;
            if (armed > 0)
            {
                this.logger.LogInformation(
                    "Committing reservation {reference} over ~{delay}s, but this process kills itself {killAfter}s into the run, as asked by kill_after_seconds. It resumes on restart.",
                    reference,
                    this.delaySeconds,
                    armed);
            }
            else
            {
                this.logger.LogInformation(
                    "Committing reservation {reference} over ~{delay}s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.",
                    reference,
                    this.delaySeconds);
            }

            await Task.Delay(TimeSpan.FromSeconds(this.delaySeconds));

            var code = ConfirmationCode(reference);
            this.logger.LogInformation(
                "Committed reservation {reference}. Confirmation code: {code}", reference, code);

            return $"Reservation {reference} confirmed. Confirmation code: {code}";
        }

        /// <summary>
        /// A confirmation code that is a pure function of the booking reference.
        ///
        /// SHA-256 rather than reference.GetHashCode(): .NET randomises string hash codes per
        /// process, so the code would change across the restart and the re-issued call could not
        /// show the reader the same answer.
        /// </summary>
        static string ConfirmationCode(string reference)
        {
            var digest = SHA256.HashData(Encoding.UTF8.GetBytes(reference));
            return "BK-" + Convert.ToHexString(digest)[..8];
        }
    }
}
