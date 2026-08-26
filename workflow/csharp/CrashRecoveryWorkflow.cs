using System.Threading.Tasks;
using Dapr.Workflow;
using WorkflowApp.Activities;
using WorkflowApp.Models;

namespace WorkflowApp.Workflows
{
    /// <summary>
    /// Crash-recovery demo: a workflow built to be interrupted.
    ///
    /// OrderProcessingWorkflow cannot do this job. Its delays are 2s of payment and 5s of
    /// inventory update, and seven seconds split across two activities is not a window a human
    /// can aim a second terminal at. This workflow runs one instant activity and then one that
    /// takes about 30 seconds, so a kill lands between two known points.
    ///
    /// The activity ORDER is the whole design. The fast notification completes first, so Catalyst
    /// has persisted its result before the slow activity starts. After a restart that notification
    /// is replayed from the recorded result rather than re-executed, and its absence from the log
    /// is what proves durable execution did something. Reverse the two and the crash lands before
    /// anything has completed, the run restarts from nothing, and the demo proves nothing at all.
    /// </summary>
    public class CrashRecoveryWorkflow : Workflow<string, string>
    {
        public override async Task<string> RunAsync(WorkflowContext context, string reference)
        {
            string demoId = context.InstanceId;

            // Fast, and first. See the class comment: this is not an arbitrary ordering.
            await context.CallActivityAsync(
                nameof(NotifyActivity),
                new Notification($"Reservation {demoId} received for {reference}"));

            // Slow. Kill the app while this is running.
            string confirmation = await context.CallActivityAsync<string>(
                nameof(CommitReservationActivity),
                reference);

            await context.CallActivityAsync(
                nameof(NotifyActivity),
                new Notification($"Reservation {demoId} has completed! {confirmation}"));

            return confirmation;
        }
    }
}
