namespace WorkflowApp.Activities
{
    using System;
    using System.Diagnostics;
    using System.Security.Cryptography;
    using System.Text;
    using System.Threading;
    using System.Threading.Tasks;
    using Dapr.Workflow;
    using Microsoft.Extensions.Logging;

    /// <summary>
    /// A deliberately slow activity that opens the window for the crash-recovery demo.
    ///
    /// It logs a start marker, waits for CRASH_DELAY_SECONDS (10 by default), then logs a commit
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
        /// Seconds into THIS ACTIVITY's run at which the app should kill itself, or 0 when
        /// nothing is asked for. Recorded by the /crash/run handler in Program.cs, then read and
        /// acted on here.
        ///
        /// Static because the writer is a request handler and the reader is this activity, and
        /// one armed kill takes the whole process down, so there is nothing to key by instance.
        /// The fresh process after the restart starts at 0 again, which is what makes the replay
        /// safe: the resumed activity re-runs this from the start and must not arm a second kill
        /// when it does.
        ///
        /// An int rather than an int?: the write happens on a request thread and the read on a
        /// workflow worker thread, and a single int cannot be read half-written the way a
        /// nullable struct's two fields can. 0 is unambiguous as "not armed" because the record
        /// site already rejects a non-positive value.
        /// </summary>
        static int selfKillSeconds;

        readonly ILogger logger;
        readonly int delaySeconds;

        public CommitReservationActivity(ILoggerFactory loggerFactory)
        {
            this.logger = loggerFactory.CreateLogger<CommitReservationActivity>();
            this.delaySeconds = int.TryParse(
                Environment.GetEnvironmentVariable("CRASH_DELAY_SECONDS"), out var seconds)
                ? seconds
                : 10;
        }

        /// <summary>
        /// Record how far into this activity the process should kill itself, for RunAsync to act
        /// on when it actually runs. Recording only: no timer starts here. Pass 0 to disarm.
        /// </summary>
        public static void NoteSelfKill(int delaySeconds) =>
            Interlocked.Exchange(ref selfKillSeconds, delaySeconds);

        /// <summary>
        /// Kill this process <paramref name="delaySeconds"/> from now, on a background task.
        ///
        /// Armed HERE, at the point this activity actually starts, and not back at the request.
        /// The request handler cannot start this clock honestly: between the schedule call and
        /// this activity sit the dispatch round-trip and the whole fast activity, so a budget
        /// measured from the request has to cover work the reader cannot see or predict.
        /// Measured from here it runs against this activity's own delay, which is the window the
        /// README tells them to aim at. That is also what makes the field safe to send on a
        /// re-issue: an attaching call never reaches this line.
        /// </summary>
        static void ArmSelfKill(int delaySeconds)
        {
            // Discarded on purpose: this task is a fuse, not something to await. Nothing can
            // observe its completion, because its last act is to end the process.
            _ = Task.Run(async () =>
            {
                await Task.Delay(TimeSpan.FromSeconds(delaySeconds));
                // Console.WriteLine plus an explicit flush, for the reason /crash/kill gives in
                // Program.cs: the default console logger hands the line to a background thread
                // and the kill beats it, so the one line explaining the death never prints.
                Console.WriteLine($">>> crash: killing this process {delaySeconds}s into the run, as asked by kill_after_seconds");
                Console.Out.Flush();
                // Kill(), matching /crash/kill: Environment.Exit runs the ProcessExit handlers,
                // which makes it a controlled shutdown wearing a crash's name.
                Process.GetCurrentProcess().Kill();
            });
        }

        public override async Task<string> RunAsync(WorkflowActivityContext context, string reference)
        {
            // Read AND clear in one step, so one recorded request arms exactly one execution. A
            // call that attaches records the field but never gets here, and leaving the value set
            // would let it leak into the next run in the same process and kill an app that had
            // never asked for it.
            var armed = Interlocked.Exchange(ref selfKillSeconds, 0);
            // Two messages, because the reader's next move differs. Un-armed, the window is
            // theirs to aim at and they have to crash the app themselves. Armed, the app does
            // that for them at a known point, so the instruction would be wrong and the ~delay
            // would be read as the wait.
            if (armed > 0)
            {
                this.logger.LogInformation(
                    "Committing reservation {reference} over ~{delay}s, but this process kills itself {killAfter}s into the run, as asked by kill_after_seconds. It resumes on restart.",
                    reference,
                    this.delaySeconds,
                    armed);
                ArmSelfKill(armed);
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
