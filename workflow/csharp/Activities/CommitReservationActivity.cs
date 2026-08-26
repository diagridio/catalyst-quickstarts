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

        public override async Task<string> RunAsync(WorkflowActivityContext context, string reference)
        {
            this.logger.LogInformation(
                "Committing reservation {reference} over ~{delay}s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.",
                reference,
                this.delaySeconds);

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
